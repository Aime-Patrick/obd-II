"""
Generate Figure 5.1 (Learning Curve) and Figure 5.2 (Confusion Matrix)
for the SmartDriveX OBD fault detection model.

Run from the backend directory:
  cd backend
  python ml/generate_figures.py

Output files:
  backend/ml/figure_5_1_learning_curve.png
  backend/ml/figure_5_2_confusion_matrix.png
"""

import os
import numpy as np
import pandas as pd
import joblib
import matplotlib.pyplot as plt
from sklearn.model_selection import learning_curve, StratifiedKFold, train_test_split
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay

# ── Paths ─────────────────────────────────────────────────────────────────────

BASE_DIR   = os.path.dirname(__file__)
DATA_PATH  = os.path.join(BASE_DIR, "cleaned_data.csv")
MODEL_PATH = os.path.join(BASE_DIR, "obd_model.joblib")
OUT_DIR    = BASE_DIR  # save figures alongside the model

# ── Features (must match train_model.py exactly) ──────────────────────────────

FEATURES = [
    "ENGINE_RPM",
    "SPEED",
    "ENGINE_LOAD",
    "ENGINE_COOLANT_TEMP",
    "THROTTLE_POS",
    "MAF",
    "FUEL_PRESSURE",
    "INTAKE_MANIFOLD_PRESSURE",
    "AIR_INTAKE_TEMP",
    "BAROMETRIC_PRESSURE",
    "FUEL_LEVEL",
    "SHORT_TERM_FUEL_TRIM_BANK_1",
    "LONG_TERM_FUEL_TRIM_BANK_2",
    "SHORT_TERM_FUEL_TRIM_BANK_2",
    "ENGINE_RUNTIME",
    "EQUIV_RATIO",
    "TIMING_ADVANCE",
]

COLUMN_MAP = {
    "BAROMETRIC_PRESSURE(KPA)": "BAROMETRIC_PRESSURE",
    "TERM_FUEL_TRIM_BANK_1": "SHORT_TERM_FUEL_TRIM_BANK_1",
}

TARGET = "HAS_FAULT"

# ── Load data ─────────────────────────────────────────────────────────────────

print(f"Loading data from {DATA_PATH} ...")
df = pd.read_csv(DATA_PATH)
df.rename(columns=COLUMN_MAP, inplace=True)
df = df.loc[:, ~df.columns.duplicated()]

available = [f for f in FEATURES if f in df.columns]
df = df.dropna(subset=available + [TARGET])

X = df[available].astype(float).copy()
y = df[TARGET].astype(int)

# Derived features (same as train_model.py)
X["RPM_LOAD_RATIO"]     = X["ENGINE_RPM"] / (X["ENGINE_LOAD"].replace(0, 1))
X["TEMP_RPM_RATIO"]     = X["ENGINE_COOLANT_TEMP"] / (X["ENGINE_RPM"].replace(0, 1))
X["THROTTLE_LOAD_DIFF"] = X["THROTTLE_POS"] - X["ENGINE_LOAD"]

stft1 = X["SHORT_TERM_FUEL_TRIM_BANK_1"].values if "SHORT_TERM_FUEL_TRIM_BANK_1" in X.columns else np.zeros(len(X))
ltft2 = X["LONG_TERM_FUEL_TRIM_BANK_2"].values  if "LONG_TERM_FUEL_TRIM_BANK_2"  in X.columns else np.zeros(len(X))
X["FUEL_TRIM_TOTAL"] = stft1 + ltft2

ait = X["AIR_INTAKE_TEMP"].values if "AIR_INTAKE_TEMP" in X.columns else X["ENGINE_COOLANT_TEMP"].values
X["INTAKE_TEMP_DIFF"] = X["ENGINE_COOLANT_TEMP"].values - ait

print(f"Dataset ready: {X.shape[0]} samples, {X.shape[1]} features")

# ── Load trained model ────────────────────────────────────────────────────────

print(f"Loading model from {MODEL_PATH} ...")
pipeline = joblib.load(MODEL_PATH)

# ── Train/test split (same seed as training) ──────────────────────────────────

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(f"Train: {X_train.shape}  Test: {X_test.shape}")

# ── FIGURE 5.1: Learning Curve ────────────────────────────────────────────────

print("\nGenerating Figure 5.1: Learning Curve ...")

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

train_sizes, train_scores, val_scores = learning_curve(
    pipeline, X_train, y_train,
    train_sizes=np.linspace(0.05, 1.0, 15),
    cv=cv,
    scoring="accuracy",
    n_jobs=-1,
)

train_mean = train_scores.mean(axis=1)
train_std  = train_scores.std(axis=1)
val_mean   = val_scores.mean(axis=1)
val_std    = val_scores.std(axis=1)

plt.figure(figsize=(8, 5))
plt.plot(train_sizes, train_mean, "o-", color="steelblue",   label="Training Accuracy")
plt.plot(train_sizes, val_mean,   "s--", color="darkorange", label="Validation Accuracy")
plt.fill_between(train_sizes, train_mean - train_std, train_mean + train_std,
                 alpha=0.12, color="steelblue")
plt.fill_between(train_sizes, val_mean - val_std, val_mean + val_std,
                 alpha=0.12, color="darkorange")
plt.xlabel("Training Set Size", fontsize=12)
plt.ylabel("Accuracy", fontsize=12)
plt.title("Figure 5.1: Gradient Boosting Classifier — Learning Curve", fontsize=13)
plt.legend(fontsize=11)
plt.ylim(0.6, 1.05)
plt.grid(True, linestyle="--", alpha=0.6)
plt.tight_layout()

fig51_path = os.path.join(OUT_DIR, "figure_5_1_learning_curve.png")
plt.savefig(fig51_path, dpi=300)
plt.show()
print(f"Saved: {fig51_path}")

# ── FIGURE 5.2: Confusion Matrix ──────────────────────────────────────────────

print("\nGenerating Figure 5.2: Confusion Matrix ...")

y_pred = pipeline.predict(X_test)
cm = confusion_matrix(y_test, y_pred)

disp = ConfusionMatrixDisplay(
    confusion_matrix=cm,
    display_labels=["Healthy", "Fault"],
)

fig, ax = plt.subplots(figsize=(6, 5))
disp.plot(ax=ax, colorbar=True, cmap="Blues", values_format=".0f")
ax.set_title("Figure 5.2: Confusion Matrix — Gradient Boosting Classifier", fontsize=13)
plt.tight_layout()

fig52_path = os.path.join(OUT_DIR, "figure_5_2_confusion_matrix.png")
plt.savefig(fig52_path, dpi=300)
plt.show()
print(f"Saved: {fig52_path}")

print("\nDone! Both figures saved to backend/ml/")
