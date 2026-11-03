"""Synthetic data generator.

Creates two things, both 100% fake (no real bank data is ever needed):
  1. A labelled training set of bank-statement descriptions -> category,
     used to train the transaction categorizer.
  2. A realistic 6-month sample statement for demos.

Run:  python -m app.data.generate
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent

# Merchant name pools per category. Descriptions are built from these with
# bank-style noise (UPI refs, POS prefixes, city names) so the model has to
# learn patterns, not memorise exact strings.
MERCHANTS: dict[str, list[str]] = {
    "Food & Dining": ["SWIGGY", "ZOMATO", "DOMINOS PIZZA", "STARBUCKS", "MCDONALDS",
                      "CAFE COFFEE DAY", "HALDIRAMS", "BURGER KING", "KFC", "CHAAYOS",
                      "BARBEQUE NATION", "SUBWAY", "BEHROUZ BIRYANI", "FAASOS"],
    "Groceries": ["BIGBASKET", "BLINKIT", "ZEPTO", "DMART", "RELIANCE FRESH",
                  "MORE SUPERMARKET", "SPENCERS", "JIOMART", "NATURES BASKET",
                  "SWIGGY INSTAMART", "LOCAL KIRANA STORE"],
    "Transport": ["UBER", "OLA CABS", "RAPIDO", "INDIAN OIL", "HP PETROL PUMP",
                  "BHARAT PETROLEUM", "METRO RAIL", "FASTAG RECHARGE", "IRCTC",
                  "NAMMA YATRI", "PARKING CHARGES"],
    "Shopping": ["AMAZON", "FLIPKART", "MYNTRA", "AJIO", "NYKAA", "DECATHLON",
                 "CROMA", "RELIANCE DIGITAL", "IKEA", "MEESHO", "LIFESTYLE STORES",
                 "WESTSIDE"],
    "Bills & Utilities": ["AIRTEL POSTPAID", "JIO RECHARGE", "BESCOM ELECTRICITY",
                          "TATA POWER", "ACT FIBERNET", "VI POSTPAID", "MAHANAGAR GAS",
                          "WATER BOARD", "BSNL BROADBAND", "CREDIT CARD BILL PAYMENT"],
    "Entertainment": ["NETFLIX", "SPOTIFY", "BOOKMYSHOW", "HOTSTAR", "PRIME VIDEO",
                      "PVR CINEMAS", "INOX", "STEAM GAMES", "YOUTUBE PREMIUM",
                      "SONYLIV"],
    "Health": ["APOLLO PHARMACY", "PHARMEASY", "1MG", "MEDPLUS", "CULT FIT",
               "PRACTO", "MAX HOSPITAL", "FORTIS HEALTHCARE", "NETMEDS",
               "DR LAL PATHLABS"],
    "Rent": ["HOUSE RENT", "NOBROKER RENT PAY", "RENT TO LANDLORD", "PG RENT",
             "FLAT MAINTENANCE", "SOCIETY MAINTENANCE"],
    "Travel": ["MAKEMYTRIP", "GOIBIBO", "INDIGO AIRLINES", "AIR INDIA", "OYO ROOMS",
               "CLEARTRIP", "AIRBNB", "TAJ HOTELS", "REDBUS", "YATRA"],
    "Education": ["UDEMY", "COURSERA", "BYJUS", "UNACADEMY", "SCHOOL FEES",
                  "COLLEGE FEES", "AMAZON KINDLE", "LEETCODE PREMIUM",
                  "SAPNA BOOK HOUSE", "TUITION FEES"],
}
# Local, unbranded merchants whose names carry a category word. Real statements
# are full of these, and they are what lets the model handle shops it never saw.
LOCAL_PREFIXES = ["SHARMA", "GUPTA", "SRI LAKSHMI", "NEW", "CITY", "ROYAL", "OM SAI",
                  "BALAJI", "PATEL", "GREEN", "STAR", "KRISHNA", "A1", "JAI HIND"]
LOCAL_SUFFIXES: dict[str, list[str]] = {
    "Food & Dining": ["RESTAURANT", "DHABA", "CAFE", "BIRYANI HOUSE", "SWEETS", "BAKERY", "FOOD COURT"],
    "Groceries": ["SUPERMARKET", "KIRANA", "GENERAL STORE", "PROVISION STORE", "VEGETABLES", "MART"],
    "Transport": ["FUEL STATION", "PETROL PUMP", "AUTO SERVICE", "CAB SERVICE", "TRAVELS TAXI"],
    "Shopping": ["FASHION", "GARMENTS", "FOOTWEAR", "ELECTRONICS", "MOBILE SHOP", "BOUTIQUE"],
    "Bills & Utilities": ["ELECTRICITY BOARD", "BROADBAND", "GAS AGENCY", "MOBILE RECHARGE", "DTH RECHARGE"],
    "Entertainment": ["CINEMAS", "MULTIPLEX", "GAMING ZONE", "BOWLING", "STREAMING SUBSCRIPTION"],
    "Health": ["MEDICAL STORE", "PHARMACY", "CLINIC", "HOSPITAL", "DIAGNOSTICS", "DENTAL CARE"],
    "Rent": ["RENT", "PG HOSTEL RENT", "APARTMENT RENT", "MAINTENANCE CHARGES"],
    "Travel": ["HOTEL", "RESORT", "TOURS AND TRAVELS", "AIRLINES", "GUEST HOUSE", "HOLIDAYS"],
    "Education": ["ACADEMY", "COACHING CENTRE", "BOOK DEPOT", "SCHOOL", "INSTITUTE", "TUITION CLASSES"],
}
for _cat, _sufs in LOCAL_SUFFIXES.items():
    MERCHANTS[_cat] = MERCHANTS[_cat] + [f"{p} {s}" for p in LOCAL_PREFIXES for s in _sufs]

INCOME_SOURCES = ["SALARY ACME TECH PVT LTD", "NEFT SALARY CREDIT", "FREELANCE PAYMENT",
                  "INTEREST CREDIT", "REFUND"]

CITIES = ["BANGALORE", "MUMBAI", "DELHI", "PUNE", "HYDERABAD", "CHENNAI", ""]

# Typical amount range (INR) per category, used for the sample statement.
AMOUNTS: dict[str, tuple[int, int]] = {
    "Food & Dining": (120, 900), "Groceries": (200, 2500), "Transport": (60, 1500),
    "Shopping": (300, 5000), "Bills & Utilities": (300, 2500),
    "Entertainment": (149, 800), "Health": (150, 3000), "Rent": (18000, 18000),
    "Travel": (1500, 9000), "Education": (400, 4000),
}
# How many times per month each category typically shows up.
MONTHLY_FREQ: dict[str, tuple[int, int]] = {
    "Food & Dining": (8, 14), "Groceries": (4, 8), "Transport": (6, 12),
    "Shopping": (2, 5), "Bills & Utilities": (3, 5), "Entertainment": (2, 4),
    "Health": (0, 2), "Rent": (1, 1), "Travel": (0, 1), "Education": (0, 1),
}


def noisy_description(merchant: str, rng: random.Random) -> str:
    """Wrap a merchant name in bank-statement style noise."""
    city = rng.choice(CITIES)
    ref = rng.randint(100000, 999999)
    templates = [
        f"UPI/{merchant}/{ref}",
        f"UPI-{merchant}-PAYMENT-{ref}",
        f"POS {merchant} {city}".strip(),
        f"{merchant} {city}".strip(),
        f"DEBIT CARD {merchant} {ref}",
        f"NEFT {merchant} REF{ref}",
        f"{merchant.lower()} order {ref}",
        f"{merchant.title()}",
    ]
    return rng.choice(templates)


def make_training_set(n_per_category: int = 300, seed: int = 7) -> list[tuple[str, str, str]]:
    """Rows of (description, category, merchant). Merchant is kept so evaluation
    can hold out whole merchants the model has never seen."""
    rng = random.Random(seed)
    rows = []
    for category, merchants in MERCHANTS.items():
        for _ in range(n_per_category):
            merchant = rng.choice(merchants)
            rows.append((noisy_description(merchant, rng), category, merchant))
    rng.shuffle(rows)
    return rows


def _add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def make_sample_statement(months: int = 6, seed: int = 11, end: date | None = None) -> list[dict]:
    """A fake statement covering the last `months` full months.

    Like a real person, the user has a few favourite shops per category (one
    landlord), and spending drifts up ~4%/month so the forecast has a trend.
    """
    rng = random.Random(seed)
    end = end or date.today().replace(day=1) - timedelta(days=1)  # last day of last month
    first_month = _add_months(end.replace(day=1), -(months - 1))
    favourites = {c: rng.sample(ms, 1 if c == "Rent" else min(4, len(ms)))
                  for c, ms in MERCHANTS.items()}
    salary = INCOME_SOURCES[0]
    rows: list[dict] = []
    for m in range(months):
        month_start = _add_months(first_month, m)
        drift = 1 + 0.04 * m
        rows.append({"date": month_start.isoformat(), "description": f"NEFT {salary}", "amount": 85000.0})
        for category, (lo, hi) in MONTHLY_FREQ.items():
            for _ in range(rng.randint(lo, hi)):
                day = rng.randint(1, 28)
                a_lo, a_hi = AMOUNTS[category]
                amount = round(rng.uniform(a_lo, a_hi) * (1 if category == "Rent" else drift), 2)
                rows.append({
                    "date": month_start.replace(day=day).isoformat(),
                    "description": noisy_description(rng.choice(favourites[category]), rng),
                    "amount": -amount,
                })
    rows.sort(key=lambda r: r["date"])
    return rows


def main() -> None:
    train = make_training_set()
    with open(DATA_DIR / "training.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["description", "category", "merchant"])
        w.writerows(train)
    sample = make_sample_statement()
    with open(DATA_DIR / "sample_statement.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "description", "amount"])
        w.writeheader()
        w.writerows(sample)
    print(f"wrote {len(train)} training rows and {len(sample)} sample transactions to {DATA_DIR}")


if __name__ == "__main__":
    main()
