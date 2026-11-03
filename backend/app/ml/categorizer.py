"""Transaction categorizer: TF-IDF (character n-grams) + Logistic Regression.

Why character n-grams: bank descriptions are short and messy
("UPI/SWIGGY/482910", "swiggy order 1234"), so sub-word pieces like "swi",
"wig", "ggy" generalise better than whole words.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.pipeline import Pipeline

ML_DIR = Path(__file__).resolve().parent
MODEL_PATH = ML_DIR / "categorizer.joblib"
METRICS_PATH = ML_DIR / "metrics.json"
TRAINING_CSV = ML_DIR.parent / "data" / "training.csv"

_model: Pipeline | None = None


def build_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4),
                                  lowercase=True, min_df=2, sublinear_tf=True)),
        ("clf", LogisticRegression(max_iter=1000, C=5.0)),
    ])


def load_training_rows(path: Path = TRAINING_CSV) -> tuple[list[str], list[str], list[str]]:
    """Returns (descriptions, categories, merchants)."""
    if path.exists():
        with open(path, newline="") as f:
            rows = [(r["description"], r["category"], r.get("merchant", "")) for r in csv.DictReader(f)]
    else:
        from app.data.generate import make_training_set
        rows = make_training_set()
    return [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows]


def train(save: bool = True) -> dict:
    """Train and evaluate two ways, optionally save model + metrics.

    - accuracy_seen_merchants: random 80/20 split (same merchants in train and test).
    - accuracy_unseen_merchants: whole merchants held out (GroupShuffleSplit). This is
      the honest number: it measures whether the model generalises to new shops.
    """
    X, y, groups = load_training_rows()
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    pred = build_pipeline().fit(X_tr, y_tr).predict(X_te)
    seen_acc = float(accuracy_score(y_te, pred))

    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    tr_idx, te_idx = next(gss.split(X, y, groups))
    Xg_tr, yg_tr = [X[i] for i in tr_idx], [y[i] for i in tr_idx]
    Xg_te, yg_te = [X[i] for i in te_idx], [y[i] for i in te_idx]
    g_pred = build_pipeline().fit(Xg_tr, yg_tr).predict(Xg_te)
    metrics = {
        "accuracy": round(float(accuracy_score(yg_te, g_pred)), 4),
        "accuracy_unseen_merchants": round(float(accuracy_score(yg_te, g_pred)), 4),
        "accuracy_seen_merchants": round(seen_acc, 4),
        "n_train": len(Xg_tr),
        "n_test": len(Xg_te),
        "per_class": classification_report(yg_te, g_pred, output_dict=True, zero_division=0),
    }
    # Final model is refit on all data.
    model = build_pipeline().fit(X, y)
    if save:
        joblib.dump(model, MODEL_PATH)
        METRICS_PATH.write_text(json.dumps(metrics, indent=2))
    global _model
    _model = model
    return metrics


def get_model() -> Pipeline:
    """Load the saved model, training one on the fly if it is missing."""
    global _model
    if _model is None:
        if MODEL_PATH.exists():
            _model = joblib.load(MODEL_PATH)
        else:
            train(save=True)
    assert _model is not None
    return _model


def predict(descriptions: list[str]) -> list[tuple[str, float]]:
    """Return (category, confidence) for each description."""
    if not descriptions:
        return []
    model = get_model()
    probs = model.predict_proba(descriptions)
    classes = model.classes_
    out = []
    for row in probs:
        i = int(row.argmax())
        out.append((str(classes[i]), round(float(row[i]), 3)))
    return out


def get_metrics() -> dict:
    if METRICS_PATH.exists():
        return json.loads(METRICS_PATH.read_text())
    return train(save=True)
