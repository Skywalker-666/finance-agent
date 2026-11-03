"""The finance agent: an LLM tool-calling loop with an offline fallback.

Online mode (LLM_API_KEY set):
  1. Send the question + tool schemas to the LLM.
  2. If it asks for tools, run them on the user's data and send results back.
  3. Repeat (max MAX_STEPS) until the LLM writes a final answer.

Offline mode (no key): a small keyword router picks tools and writes a
template answer. The app still works end-to-end, and tests need no network.
"""
from __future__ import annotations

import json
import re
from datetime import date

from app.agent import llm
from app.agent.tools import CATEGORIES, TOOL_SPECS, run_tool

MAX_STEPS = 5

SYSTEM_PROMPT = """You are a careful personal-finance assistant.
You answer questions about the user's own bank transactions using ONLY the tools provided.
Rules:
- Always call a tool to get numbers; never invent amounts.
- Amounts are Indian Rupees; format like Rs 12,345.
- If a chart would help, call make_chart.
- Keep answers short: 2-4 sentences, then one practical tip if relevant.
- You give general budgeting observations, not professional financial advice.
Today is {today}. The data covers {start} to {end}."""


def _fmt(x: float) -> str:
    return f"Rs {x:,.0f}"


def _step(name: str, args: dict, result: dict) -> dict:
    preview = json.dumps(result)[:300]
    return {"tool": name, "args": args, "result_preview": preview}


def run_agent(question: str, txns: list[dict], history: list[dict] | None = None) -> dict:
    if not txns:
        return {"answer": "Upload a statement (or load the sample data) first, then ask me anything about it.",
                "steps": [], "charts": [], "mode": "none"}
    if llm.is_configured():
        try:
            return _run_online(question, txns, history or [])
        except llm.LLMError as e:
            result = _run_offline(question, txns)
            result["notice"] = f"LLM unavailable, used offline mode ({e})"
            return result
    return _run_offline(question, txns)


def _run_online(question: str, txns: list[dict], history: list[dict]) -> dict:
    dates = sorted(t["date"] for t in txns)
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT.format(
        today=date.today().isoformat(), start=dates[0], end=dates[-1])}]
    for h in history[-6:]:  # short memory of the conversation
        if h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str):
            messages.append({"role": h["role"], "content": h["content"][:2000]})
    messages.append({"role": "user", "content": question})

    steps, charts = [], []
    for _ in range(MAX_STEPS):
        msg = llm.chat(messages, tools=TOOL_SPECS)
        calls = msg.get("tool_calls") or []
        if not calls:
            return {"answer": msg.get("content") or "", "steps": steps, "charts": charts, "mode": "llm"}
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
        for call in calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = run_tool(name, args, txns)
            if "chart" in result:
                charts.append(result["chart"])
            steps.append(_step(name, args, result))
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})
    return {"answer": "I needed too many steps for that one. Try a more specific question.",
            "steps": steps, "charts": charts, "mode": "llm"}


def _find_category(q: str) -> str | None:
    ql = q.lower()
    for c in CATEGORIES:
        if c.lower() in ql or c.split(" ")[0].lower() in ql:
            return c
    return None


def _run_offline(question: str, txns: list[dict]) -> dict:
    q = question.lower()
    steps, charts = [], []

    def call(name: str, **args) -> dict:
        res = run_tool(name, args, txns)
        steps.append(_step(name, args, res))
        if "chart" in res:
            charts.append(res["chart"])
        return res

    amount_match = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(k)?", q)
    if any(w in q for w in ("afford", "buy", "purchase")) and amount_match:
        amount = float(amount_match.group(1).replace(",", "")) * (1000 if amount_match.group(2) else 1)
        r = call("check_affordability", amount=amount)
        verdict = "Yes, that fits" if r["affordable"] else "That would be a stretch"
        answer = (f"{verdict}. Expected savings next month are {_fmt(r['expected_savings_next_month'])}, "
                  f"leaving {_fmt(r['left_after_purchase'])} after a {_fmt(amount)} purchase.")
    elif any(w in q for w in ("forecast", "predict", "next month", "expect")):
        r = call("forecast")
        top = list(r["expected_spend_by_category"].items())[:3]
        answer = (f"Next month I expect about {_fmt(r['expected_total_spend'])} in spending and "
                  f"{_fmt(r['expected_savings'])} in savings. Biggest: "
                  + ", ".join(f"{c} {_fmt(v)}" for c, v in top) + ".")
    elif any(w in q for w in ("merchant", "shop", "store", "top ")):
        cat = _find_category(q)
        r = call("top_merchants", n=5, **({"category": cat} if cat else {}))
        answer = "Top places by spend: " + "; ".join(
            f"{m['merchant']} ({_fmt(m['spent'])}, {m['visits']} visits)" for m in r["top"]) + "."
    elif any(w in q for w in ("month", "trend", "over time")):
        cat = _find_category(q)
        r = call("spending_summary", **({"category": cat} if cat else {}))
        call("make_chart", kind="by_month", **({"category": cat} if cat else {}))
        months = list(r["by_month"].items())
        answer = (f"Spending went from {_fmt(months[0][1])} in {months[0][0]} to "
                  f"{_fmt(months[-1][1])} in {months[-1][0]}." if len(months) > 1 else
                  f"Total spend: {_fmt(r['total_spent'])}.")
    else:
        cat = _find_category(q)
        r = call("spending_summary", **({"category": cat} if cat else {}))
        call("make_chart", kind="by_category")
        if cat:
            answer = f"You spent {_fmt(r['total_spent'])} on {cat} across {r['transaction_count']} transactions."
        else:
            top = list(r["by_category"].items())[:3]
            answer = (f"You spent {_fmt(r['total_spent'])} in total. Top categories: "
                      + ", ".join(f"{c} {_fmt(v)}" for c, v in top) + ".")
    return {"answer": answer, "steps": steps, "charts": charts, "mode": "offline"}
