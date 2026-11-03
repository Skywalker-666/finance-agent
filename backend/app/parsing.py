"""Parse a bank-statement CSV into normalised transactions.

Accepts common header names, e.g.:
  date, description, amount             (negative = spend)
  Date, Narration, Withdrawal, Deposit  (typical Indian bank export)
"""
from __future__ import annotations

import csv
import io
from datetime import datetime

MAX_ROWS = 5000

DATE_KEYS = ("date", "txn date", "transaction date", "value date")
DESC_KEYS = ("description", "narration", "details", "particulars", "remarks")
AMOUNT_KEYS = ("amount",)
DEBIT_KEYS = ("debit", "withdrawal", "withdrawal amt.", "withdrawal amount", "dr")
CREDIT_KEYS = ("credit", "deposit", "deposit amt.", "deposit amount", "cr")
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%b-%Y", "%m/%d/%Y")


class ParseError(ValueError):
    pass


def _pick(header: dict[str, str], keys: tuple[str, ...]) -> str | None:
    for k in keys:
        if k in header:
            return header[k]
    return None


def _num(s: str | None) -> float:
    if s is None:
        return 0.0
    s = s.replace(",", "").replace("₹", "").replace("Rs", "").strip()
    return float(s) if s else 0.0


def _date(s: str) -> str:
    s = s.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    raise ParseError(f"unrecognised date '{s[:20]}'")


def parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ParseError("empty file")
    header = {h.strip().lower(): h for h in reader.fieldnames if h}
    date_col = _pick(header, DATE_KEYS)
    desc_col = _pick(header, DESC_KEYS)
    amount_col = _pick(header, AMOUNT_KEYS)
    debit_col, credit_col = _pick(header, DEBIT_KEYS), _pick(header, CREDIT_KEYS)
    if not date_col or not desc_col or not (amount_col or debit_col or credit_col):
        raise ParseError("CSV needs a date column, a description column, and amount (or debit/credit) columns")

    out = []
    for i, row in enumerate(reader, start=2):
        if i - 1 > MAX_ROWS:
            raise ParseError(f"too many rows (max {MAX_ROWS})")
        if not (row.get(date_col) or "").strip():
            continue
        try:
            if amount_col:
                amount = _num(row.get(amount_col))
            else:
                amount = _num(row.get(credit_col)) - _num(row.get(debit_col))
            out.append({"date": _date(row[date_col]),
                        "description": (row.get(desc_col) or "").strip()[:200],
                        "amount": round(amount, 2)})
        except (ValueError, KeyError) as e:
            raise ParseError(f"row {i}: {e}") from e
    if not out:
        raise ParseError("no transactions found")
    out.sort(key=lambda t: t["date"])
    return out
