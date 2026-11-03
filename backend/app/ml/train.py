"""Train the categorizer and print evaluation metrics.

Run:  python -m app.ml.train
"""
from app.ml.categorizer import train


def main() -> None:
    metrics = train(save=True)
    print(f"accuracy, seen merchants:   {metrics['accuracy_seen_merchants']:.2%}")
    print(f"accuracy, unseen merchants: {metrics['accuracy_unseen_merchants']:.2%} "
          f"(train={metrics['n_train']}, test={metrics['n_test']})")
    for cat, m in metrics["per_class"].items():
        if isinstance(m, dict) and "f1-score" in m and cat not in ("macro avg", "weighted avg"):
            print(f"  {cat:<18} f1={m['f1-score']:.2f}")


if __name__ == "__main__":
    main()
