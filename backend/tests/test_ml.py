from app.data.generate import make_sample_statement
from app.ml import categorizer
from app.ml.forecast import forecast_category, forecast_next_month


def test_categorizer_accuracy_is_high():
    metrics = categorizer.train(save=False)
    assert metrics["accuracy_seen_merchants"] > 0.95
    assert metrics["accuracy_unseen_merchants"] > 0.85  # shops the model never saw


def test_categorizer_handles_unseen_noise():
    preds = [c for c, _ in categorizer.predict([
        "UPI/SWIGGY/000111", "pos uber bangalore", "NETFLIX.COM SUBSCRIPTION", "apollo pharmacy 99",
    ])]
    assert preds == ["Food & Dining", "Transport", "Entertainment", "Health"]


def test_forecast_follows_trend():
    assert forecast_category([100, 200, 300, 400]) > 400 * 0.9
    assert forecast_category([]) == 0.0
    assert forecast_category([50]) == 50.0


def test_forecast_never_negative():
    assert forecast_category([900, 300, 10, 0]) >= 0.0


def test_forecast_next_month_shape():
    txns = make_sample_statement()
    for t in txns:
        t["category"] = "Income" if t["amount"] > 0 else "Food & Dining"
    f = forecast_next_month(txns)
    assert f["months_of_history"] == 6
    assert f["expected_income"] == 85000.0
    assert f["expected_savings"] == round(f["expected_income"] - f["expected_total_spend"], 2)
