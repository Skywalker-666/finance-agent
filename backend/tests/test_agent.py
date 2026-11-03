import json

import pytest

from app.agent import agent, llm
from app.agent.tools import run_tool
from app.data.generate import make_sample_statement
from app.main import _categorize


@pytest.fixture()
def txns():
    return _categorize(make_sample_statement())


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)


def test_unknown_tool_and_bad_args_do_not_crash(txns):
    assert "error" in run_tool("drop_tables", {}, txns)
    assert "error" in run_tool("check_affordability", {"amount": "lots"}, txns)
    # Unexpected arguments are dropped, not passed through.
    assert "total_spent" in run_tool("spending_summary", {"sql": "DROP TABLE x"}, txns)


def test_offline_affordability(txns):
    r = agent.run_agent("Can I afford a 5k trip?", txns)
    assert r["mode"] == "offline"
    assert r["steps"][0]["tool"] == "check_affordability"
    assert r["steps"][0]["args"]["amount"] == 5000


def test_offline_summary_returns_chart(txns):
    r = agent.run_agent("How much did I spend?", txns)
    assert r["charts"] and r["charts"][0]["type"] == "pie"


def test_offline_category_filter(txns):
    r = agent.run_agent("How much on groceries?", txns)
    assert r["steps"][0]["args"] == {"category": "Groceries"}


def test_empty_data():
    assert agent.run_agent("hi", [])["mode"] == "none"


def test_online_loop_runs_tools(txns, monkeypatch):
    """Fake LLM: first asks for a tool, then answers. Checks the loop wiring."""
    monkeypatch.setenv("LLM_API_KEY", "test")
    replies = iter([
        {"content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {
            "name": "forecast", "arguments": json.dumps({})}}]},
        {"content": "You should save about Rs 20,000."},
    ])
    seen = []

    def fake_chat(messages, tools=None, timeout=30.0):
        seen.append(messages[-1])
        return next(replies)

    monkeypatch.setattr(llm, "chat", fake_chat)
    r = agent.run_agent("forecast please", txns)
    assert r["mode"] == "llm"
    assert r["steps"][0]["tool"] == "forecast"
    assert seen[1]["role"] == "tool"
    assert r["answer"].startswith("You should save")


def test_online_failure_falls_back(txns, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test")

    def boom(*a, **k):
        raise llm.LLMError("HTTP 500")

    monkeypatch.setattr(llm, "chat", boom)
    r = agent.run_agent("total spend", txns)
    assert r["mode"] == "offline" and "notice" in r


def test_merchant_name_strips_bank_noise():
    from app.agent.tools import merchant_name
    assert merchant_name("UPI/SWIGGY/482910") == "SWIGGY"
    assert merchant_name("swiggy order 1234") == "SWIGGY"
    assert merchant_name("POS UBER BANGALORE") == "UBER"


def test_top_merchants_groups_same_shop(txns):
    top = run_tool("top_merchants", {"n": 20}, txns)["top"]
    names = [m["merchant"] for m in top]
    assert len(names) == len(set(names))
    assert all(m["visits"] >= 1 for m in top)


def test_sample_covers_last_six_full_months():
    from datetime import date
    from app.data.generate import _add_months
    months = sorted({t["date"][:7] for t in make_sample_statement()})
    last = _add_months(date.today().replace(day=1), -1)
    assert len(months) == 6 and months[-1] == last.isoformat()[:7]


def _fake_llm(monkeypatch, tool: str):
    monkeypatch.setenv("LLM_API_KEY", "test")
    replies = iter([
        {"content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {
            "name": tool, "arguments": "{}"}}]},
        {"content": "Done."},
    ])
    monkeypatch.setattr(llm, "chat", lambda messages, tools=None, timeout=30.0: next(replies))


def test_online_adds_chart_when_llm_skips_it(txns, monkeypatch):
    _fake_llm(monkeypatch, "top_merchants")
    r = agent.run_agent("Where did I spend the most?", txns)
    assert r["charts"] and r["charts"][0]["type"] == "pie"
    assert r["steps"][-1]["tool"] == "make_chart"  # visible, not hidden


def test_online_trend_question_gets_monthly_chart(txns, monkeypatch):
    _fake_llm(monkeypatch, "spending_summary")
    r = agent.run_agent("How is my food spending trending by month?", txns)
    assert r["charts"][0]["type"] == "bar"
    assert r["steps"][-1]["args"] == {"kind": "by_month", "category": "Food & Dining"}


def test_online_affordability_gets_no_chart(txns, monkeypatch):
    _fake_llm(monkeypatch, "forecast")
    r = agent.run_agent("Can I afford to spend 15000 on a trip?", txns)
    assert r["charts"] == []
