"""Next-month spending forecast per category.

Simple and explainable on purpose: fit a straight line (least squares) to
each category's monthly totals and blend it with the recent average, so one
odd month does not swing the prediction too much.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

TREND_WEIGHT = 0.6  # 60% trend line, 40% average of the last 3 months


def monthly_totals(transactions: list[dict]) -> dict[str, dict[str, float]]:
    """{category: {"YYYY-MM": total_spent}} for expenses only (amount < 0)."""
    out: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for t in transactions:
        if t["amount"] < 0:
            out[t["category"]][t["date"][:7]] += -t["amount"]
    return {c: dict(m) for c, m in out.items()}


def _all_months(transactions: list[dict]) -> list[str]:
    return sorted({t["date"][:7] for t in transactions})


def forecast_category(series: list[float]) -> float:
    if not series:
        return 0.0
    if len(series) < 3:
        return float(np.mean(series))
    x = np.arange(len(series))
    slope, intercept = np.polyfit(x, series, 1)
    trend = slope * len(series) + intercept
    recent = float(np.mean(series[-3:]))
    return float(max(0.0, TREND_WEIGHT * trend + (1 - TREND_WEIGHT) * recent))


def forecast_next_month(transactions: list[dict]) -> dict:
    months = _all_months(transactions)
    totals = monthly_totals(transactions)
    by_category = {}
    for cat, m in totals.items():
        series = [m.get(month, 0.0) for month in months]  # missing month = 0 spend
        by_category[cat] = round(forecast_category(series), 2)

    income_by_month: dict[str, float] = defaultdict(float)
    for t in transactions:
        if t["amount"] > 0:
            income_by_month[t["date"][:7]] += t["amount"]
    income_series = [income_by_month.get(m, 0.0) for m in months]
    expected_income = round(float(np.mean(income_series)), 2) if income_series else 0.0
    total = round(sum(by_category.values()), 2)
    return {
        "months_of_history": len(months),
        "expected_spend_by_category": dict(sorted(by_category.items(), key=lambda kv: -kv[1])),
        "expected_total_spend": total,
        "expected_income": expected_income,
        "expected_savings": round(expected_income - total, 2),
        "method": "least-squares trend blended with 3-month average",
    }
