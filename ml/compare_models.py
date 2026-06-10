"""
Compare candidate classifiers for OBD-II binary fault detection.

Produces Table 5.5:1 metrics for the thesis and saves:
  - model_comparison.json
  - model_comparison.csv
  - model_comparison.md
  - figure_5_5_model_comparison.png

Run:
  cd backend
  python ml/compare_models.py
"""

from __future__ import annotations

import json
import os
import sys
import time

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import numpy as np

try:
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

from dataset import default_data_path, load_training_frame, train_test_split_frame

OUT_DIR = os.path.dirname(__file__)
RANDOM_STATE = 42


def build_candidates() -> dict[str, Pipeline]:
    """Four classifiers from thesis §3.4 — same scaler for all."""
    return {
        "Decision Tree": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", DecisionTreeClassifier(
                max_depth=12,
                min_samples_leaf=20,
                random_state=RANDOM_STATE,
            )),
        ]),
        "Random Forest": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", RandomForestClassifier(
                n_estimators=200,
                max_depth=12,
                min_samples_leaf=10,
                random_state=RANDOM_STATE,
                n_jobs=-1,
            )),
        ]),
        "Support Vector Machine (RBF)": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", SVC(
                kernel="rbf",
                C=1.0,
                gamma="scale",
                probability=True,
                random_state=RANDOM_STATE,
            )),
        ]),
        "Gradient Boosting": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", GradientBoostingClassifier(
                n_estimators=300,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
                min_samples_leaf=15,
                max_features="sqrt",
                random_state=RANDOM_STATE,
            )),
        ]),
    }


def evaluate_model(name: str, pipeline: Pipeline, X_train, X_test, y_train, y_test) -> dict:
    start = time.perf_counter()
    pipeline.fit(X_train, y_train)
    train_seconds = time.perf_counter() - start

    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]

    return {
        "model": name,
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, y_proba)),
        "train_seconds": round(train_seconds, 2),
    }


def select_winner(rows: list[dict]) -> str:
    """Highest F1; tie-breaker ROC-AUC then lower train time."""
    ranked = sorted(
        rows,
        key=lambda r: (r["f1"], r["roc_auc"], -r["train_seconds"]),
        reverse=True,
    )
    return ranked[0]["model"]


def save_markdown_table(rows: list[dict], winner: str, path: str) -> None:
    lines = [
        "# Table 5.5:1 — Comparison of ML Models for OBD-II Fault Detection",
        "",
        "| Model | Accuracy | Precision | Recall | F1-Score | ROC-AUC | Train (s) | Selected |",
        "|-------|----------|-----------|--------|----------|---------|-----------|----------|",
    ]
    for r in rows:
        selected = "Yes" if r["model"] == winner else ""
        lines.append(
            f"| {r['model']} "
            f"| {r['accuracy']:.1%} "
            f"| {r['precision']:.2f} "
            f"| {r['recall']:.2f} "
            f"| {r['f1']:.2f} "
            f"| {r['roc_auc']:.3f} "
            f"| {r['train_seconds']:.1f} "
            f"| {selected} |"
        )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def save_bar_chart(rows: list[dict], path: str) -> bool:
    if not HAS_MPL:
        return False

    models = [r["model"] for r in rows]
    metrics = {
        "Accuracy": [r["accuracy"] for r in rows],
        "F1-Score": [r["f1"] for r in rows],
        "ROC-AUC": [r["roc_auc"] for r in rows],
    }

    x = np.arange(len(models))
    width = 0.25
    fig, ax = plt.subplots(figsize=(10, 5))

    for i, (label, values) in enumerate(metrics.items()):
        ax.bar(x + i * width, values, width, label=label)

    ax.set_ylabel("Score")
    ax.set_title("Figure 5.5: Model Comparison — OBD-II Fault Detection")
    ax.set_xticks(x + width)
    ax.set_xticklabels(models, rotation=15, ha="right")
    ax.set_ylim(0.85, 1.02)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()
    return True


def main() -> None:
    data_path = default_data_path()
    if not os.path.exists(data_path):
        raise FileNotFoundError(
            f"Training data not found: {data_path}\n"
            "Run: python ml/preprocess_data.py (archive → cleaned_data.csv)"
        )

    print(f"Loading {data_path} ...")
    X, y = load_training_frame(data_path)
    X_train, X_test, y_train, y_test = train_test_split_frame(X, y)
    print(f"Samples: {len(X)}  Features: {X.shape[1]}")
    print(f"Train: {len(X_train)}  Test: {len(X_test)}")
    print(f"Fault rate: {y.mean():.1%}\n")

    results: list[dict] = []
    for name, pipeline in build_candidates().items():
        print(f"Training {name} ...")
        row = evaluate_model(name, pipeline, X_train, X_test, y_train, y_test)
        results.append(row)
        print(
            f"  Acc={row['accuracy']:.4f}  F1={row['f1']:.4f}  "
            f"ROC-AUC={row['roc_auc']:.4f}  ({row['train_seconds']}s)"
        )

    winner = select_winner(results)
    results_sorted = sorted(results, key=lambda r: r["f1"], reverse=True)

    json_path = os.path.join(OUT_DIR, "model_comparison.json")
    csv_path = os.path.join(OUT_DIR, "model_comparison.csv")
    md_path = os.path.join(OUT_DIR, "model_comparison.md")
    fig_path = os.path.join(OUT_DIR, "figure_5_5_model_comparison.png")

    payload = {
        "data_path": data_path,
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "feature_count": int(X.shape[1]),
        "random_state": RANDOM_STATE,
        "selected_model": winner,
        "results": results_sorted,
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    pd.DataFrame(results_sorted).to_csv(csv_path, index=False)
    save_markdown_table(results_sorted, winner, md_path)
    if save_bar_chart(results_sorted, fig_path):
        print(f"Saved: {fig_path}")
    else:
        print("Skipped chart (install matplotlib to generate figure_5_5_model_comparison.png)")

    print(f"\nSelected model: {winner}")
    print(f"Saved: {json_path}")
    print(f"Saved: {csv_path}")
    print(f"Saved: {md_path}")


if __name__ == "__main__":
    main()
