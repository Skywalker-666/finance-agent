"""Tools the agent can call.

Each tool is a plain Python function over the user's transactions plus a
JSON schema the LLM sees. Tools take structured arguments (dates, a
category name, a number) rather than free-form SQL, so the model can never
run an arbitrary query.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Callable

from app.data.generate import CITIES, MERCHANTS
from app.ml.forecast import forecast_next_month

CATEGORIES = list(MERCHANTS.keys())


def _filter(txns: list[dict], start_date: str | None, end_date: str | None,
            category: str | None) -> list[dict]:
    out = []
    for t in txns:
        if start_date and t["date"] < start_date:
            continue
        if end_date and t["date"] > end_date:
            continue
        if category and t["category"].lower() != category.lower():
            continue
        out.append(t)
    return out


def spending_summary(txns: list[dict], start_date: str | None = None,
                     end_date: str | None = None, category: str | None = None) -> dict:
    rows = _filter(txns, start_date, end_date, category)
    by_cat: dict[str, float] = defaultdict(float)
    by_month: dict[str, float] = defaultdict(float)
    income = 0.0
    for t in rows:
        if t["amount"] < 0:
            by_cat[t["category"]] += -t["amount"]
            by_month[t["date"][:7]] += -t["amount"]
        else:
            income += t["amount"]
    total = sum(by_cat.values())
    return {
        "period": {"start": start_date or (rows[0]["date"] if rows else None),
                   "end": end_date or (rows[-1]["date"] if rows else None)},
        "total_spent": round(total, 2),
        "total_income": round(income, 2),
        "by_category": {k: round(v, 2) for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1])},
        "by_month": {k: round(v, 2) for k, v in sorted(by_month.items())},
        "transaction_count": len(rows),
    }


_NOISE = re.compile(
    r"\b(UPI|POS|NEFT|IMPS|DEBIT CARD|PAYMENT|ORDER|REF\d*|"
    + "|".join(c for c in CITIES if c) + r")\b|\d+|[/\-_.*]", re.IGNORECASE)


def merchant_name(description: str) -> str:
    """'UPI/SWIGGY/482910' and 'swiggy order 1234' -> 'SWIGGY'."""
    name = re.sub(r"\s+", " ", _NOISE.sub(" ", description)).strip().upper()
    return name or description.upper()


def top_merchants(txns: list[dict], n: int = 5, category: str | None = None) -> dict:
    rows = _filter(txns, None, None, category)
    spend: dict[str, float] = defaultdict(float)
    count: dict[str, int] = defaultdict(int)
    for t in rows:
        if t["amount"] < 0:
            key = merchant_name(t["description"])
            spend[key] += -t["amount"]
            count[key] += 1
    n = max(1, min(int(n), 20))
    top = sorted(spend.items(), key=lambda kv: -kv[1])[:n]
    return {"top": [{"merchant": m, "spent": round(s, 2), "visits": count[m]} for m, s in top]}


def forecast(txns: list[dict]) -> dict:
    return forecast_next_month(txns)


def check_affordability(txns: list[dict], amount: float) -> dict:
    f = forecast_next_month(txns)
    savings = f["expected_savings"]
    left_after = round(savings - float(amount), 2)
    return {
        "purchase_amount": float(amount),
        "expected_savings_next_month": savings,
        "left_after_purchase": left_after,
        "affordable": left_after >= 0,
        "share_of_savings_pct": round(100 * float(amount) / savings, 1) if savings > 0 else None,
    }


def make_chart(txns: list[dict], kind: str = "by_category", start_date: str | None = None,
               end_date: str | None = None, category: str | None = None) -> dict:
    """Return a chart spec; the frontend draws it."""
    s = spending_summary(txns, start_date, end_date, category)
    if kind == "by_month":
        data = [{"label": k, "value": v} for k, v in s["by_month"].items()]
        return {"chart": {"type": "bar", "title": f"Monthly spend{' - ' + category if category else ''}",
                          "data": data}}
    data = [{"label": k, "value": v} for k, v in s["by_category"].items()]
    return {"chart": {"type": "pie", "title": "Spend by category", "data": data}}


_DATE = {"type": "string", "description": "ISO date YYYY-MM-DD"}
_CAT = {"type": "string", "enum": CATEGORIES, "description": "Spending category"}

TOOL_SPECS: list[dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "spending_summary",
        "description": "Total spend and income, broken down by category and month, optionally filtered by date range and category.",
        "parameters": {"type": "object", "properties": {
            "start_date": _DATE, "end_date": _DATE, "category": _CAT}}}},
    {"type": "function", "function": {
        "name": "top_merchants",
        "description": "Merchants/descriptions where the most money was spent.",
        "parameters": {"type": "object", "properties": {
            "n": {"type": "integer", "minimum": 1, "maximum": 20}, "category": _CAT}}}},
    {"type": "function", "function": {
        "name": "forecast",
        "description": "ML forecast of next month's spending per category, expected income and savings.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "check_affordability",
        "description": "Whether a planned purchase of `amount` (INR) fits within next month's expected savings.",
        "parameters": {"type": "object", "properties": {"amount": {"type": "number"}},
                       "required": ["amount"]}}},
    {"type": "function", "function": {
        "name": "make_chart",
        "description": "Draw a chart for the user. kind=by_category (pie) or by_month (bar).",
        "parameters": {"type": "object", "properties": {
            "kind": {"type": "string", "enum": ["by_category", "by_month"]},
            "start_date": _DATE, "end_date": _DATE, "category": _CAT}}}},
]

TOOLS: dict[str, Callable[..., dict]] = {
    "spending_summary": spending_summary,
    "top_merchants": top_merchants,
    "forecast": forecast,
    "check_affordability": check_affordability,
    "make_chart": make_chart,
}


def run_tool(name: str, args: dict, txns: list[dict]) -> dict:
    """Run a tool safely: unknown tools and bad arguments become error results, not crashes."""
    fn = TOOLS.get(name)
    if fn is None:
        return {"error": f"unknown tool {name}"}
    allowed = TOOL_SPECS[[s["function"]["name"] for s in TOOL_SPECS].index(name)]["function"]["parameters"]["properties"]
    clean = {k: v for k, v in (args or {}).items() if k in allowed}
    try:
        return fn(txns, **clean)
    except (TypeError, ValueError) as e:
        return {"error": f"bad arguments for {name}: {e}"}
