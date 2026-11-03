"""FastAPI app for the Personal Finance Agent.

Stateless by design: the browser holds the user's transactions and sends
them with each request. Nothing is stored on the server, so one visitor's
data can never be seen by another.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.agent import llm
from app.agent.agent import run_agent
from app.data.generate import make_sample_statement
from app.ml import categorizer
from app.ml.forecast import forecast_next_month
from app.parsing import MAX_ROWS, ParseError, parse_csv

MAX_UPLOAD_BYTES = 1_000_000
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "20"))

@asynccontextmanager
async def lifespan(_app: FastAPI):
    categorizer.get_model()  # load (or train) the model once at startup
    yield


app = FastAPI(title="Personal Finance Agent", version="1.0.0", lifespan=lifespan)

# Only the configured frontend origins may call the API from a browser.
_origins = [o.strip() for o in os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_origins,
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

# Tiny in-memory rate limiter, so a public demo can't burn the LLM quota.
_hits: dict[str, deque] = defaultdict(deque)


def _rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= RATE_LIMIT_PER_MIN:
        raise HTTPException(429, "Too many requests, wait a minute.")
    q.append(now)


class Transaction(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    description: str = Field(max_length=200)
    amount: float
    category: Optional[str] = None
    confidence: Optional[float] = None


class ChatTurn(BaseModel):
    role: str
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    transactions: List[Transaction] = Field(max_length=MAX_ROWS)
    history: List[ChatTurn] = Field(default_factory=list, max_length=20)


def _categorize(txns: list[dict]) -> list[dict]:
    """Fill in category for expenses using the ML model; positives are Income."""
    todo = [t for t in txns if not t.get("category")]
    spend = [t for t in todo if t["amount"] < 0]
    for t, (cat, conf) in zip(spend, categorizer.predict([t["description"] for t in spend])):
        t["category"], t["confidence"] = cat, conf
    for t in todo:
        if t["amount"] >= 0:
            t["category"], t["confidence"] = "Income", 1.0
    return txns


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "llm": "configured" if llm.is_configured() else "offline"}


@app.get("/api/model")
def model_info() -> dict:
    m = categorizer.get_metrics()
    return {"type": "TF-IDF char n-grams + Logistic Regression",
            "accuracy_unseen_merchants": m["accuracy_unseen_merchants"],
            "accuracy_seen_merchants": m["accuracy_seen_merchants"],
            "n_train": m["n_train"], "n_test": m["n_test"]}


@app.get("/api/sample")
def sample() -> dict:
    return {"transactions": _categorize(make_sample_statement())}


@app.post("/api/upload")
async def upload(request: Request, file: UploadFile = File(...)) -> dict:
    _rate_limit(request)
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (max 1 MB).")
    try:
        text = raw.decode("utf-8-sig")
        txns = parse_csv(text)
    except UnicodeDecodeError:
        raise HTTPException(400, "File must be a UTF-8 CSV.")
    except ParseError as e:
        raise HTTPException(400, str(e))
    return {"transactions": _categorize(txns)}


@app.post("/api/forecast")
def forecast(txns: List[Transaction]) -> dict:
    if len(txns) > MAX_ROWS:
        raise HTTPException(413, "Too many transactions.")
    return forecast_next_month(_categorize([t.model_dump() for t in txns]))


@app.post("/api/chat")
def chat(req: ChatRequest, request: Request) -> dict:
    _rate_limit(request)
    txns = _categorize([t.model_dump() for t in req.transactions])
    return run_agent(req.message, txns, [h.model_dump() for h in req.history])


if __name__ == "__main__":
    import uvicorn

    # Local default is loopback only. A hosting platform (e.g. Render) sets
    # HOST=0.0.0.0 inside its container, behind its own HTTPS proxy.
    uvicorn.run("app.main:app", host=os.getenv("HOST", "127.0.0.1"),
                port=int(os.getenv("PORT", "8000")))
