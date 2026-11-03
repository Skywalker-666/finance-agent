import pytest
from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    main._hits.clear()


def test_health():
    assert client.get("/api/health").json() == {"status": "ok", "llm": "offline"}


def test_sample_is_categorized():
    txns = client.get("/api/sample").json()["transactions"]
    assert len(txns) > 100
    assert all(t["category"] for t in txns)


def test_upload_bank_style_csv():
    csv_text = ("Date,Narration,Withdrawal,Deposit\n"
                "01/09/2026,SALARY CREDIT,,50000\n"
                "03/09/2026,UPI/ZOMATO/123,450,\n")
    r = client.post("/api/upload", files={"file": ("s.csv", csv_text, "text/csv")})
    assert r.status_code == 200
    txns = r.json()["transactions"]
    assert txns[0]["category"] == "Income"
    assert txns[1]["amount"] == -450 and txns[1]["category"] == "Food & Dining"


def test_upload_rejects_bad_csv():
    r = client.post("/api/upload", files={"file": ("s.csv", "foo,bar\n1,2\n", "text/csv")})
    assert r.status_code == 400


def test_upload_rejects_large_file():
    big = "date,description,amount\n" + "2026-01-01,x,-1\n" * 80_000
    r = client.post("/api/upload", files={"file": ("s.csv", big, "text/csv")})
    assert r.status_code == 413


def test_chat_end_to_end():
    txns = client.get("/api/sample").json()["transactions"]
    r = client.post("/api/chat", json={"message": "forecast next month", "transactions": txns})
    assert r.status_code == 200
    assert r.json()["steps"][0]["tool"] == "forecast"


def test_chat_validates_input():
    r = client.post("/api/chat", json={"message": "", "transactions": []})
    assert r.status_code == 422


def test_rate_limit(monkeypatch):
    monkeypatch.setattr(main, "RATE_LIMIT_PER_MIN", 2)
    body = {"message": "hi", "transactions": []}
    codes = [client.post("/api/chat", json=body).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
