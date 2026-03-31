"""
Retrain the OBD fault detection model using all sensor features
that exist in both the training data AND the mobile app's OBD polling.

Features: 17 real sensor readings — no car-specific one-hot columns,
no time columns, no metadata. Pure sensor physics.

Run:
  cd backend
  python ml/train_model.py
"""

import pandas as pd
import numpy as np
import os
import json
import joblib
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    classification_report, confusion_matrix,
    accuracy_score, roc_auc_score, f1_score
)

# ── Config ────────────────────────────────────────────────────────────────────

DATA_PATH  = os.environ.get(
    "TRAIN_DATA_PATH",
    os.path.join(os.path.dirname(__file__), "cleaned_data.csv")
)
MODEL_PATH = os.path.join(os.path.dirname(__file__), "obd_model.joblib")
META_PATH  = os.path.join(os.path.dirname(__file__), "..", "model_metadata.json")

# All sensor features present in training data AND polled by the app.
# Excludes: car make/model one-hots, time columns (MIN/HOURS/etc.),
#           CAR_YEAR, ENGINE_POWER — these are not available from OBD2 in real time.
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

# Some column names differ slightly between CSV and what we want
COLUMN_MAP = {
    "BAROMETRIC_PRESSURE(KPA)": "BAROMETRIC_PRESSURE",
    "TERM_FUEL_TRIM_BANK_1": "SHORT_TERM_FUEL_TRIM_BANK_1",
}

TARGET = "HAS_FAULT"

# ── Load & prepare data ───────────────────────────────────────────────────────

print(f"Loading {DATA_PATH} ...")
df = pd.read_csv(DATA_PATH)
print(f"  Raw shape: {df.shape}")

# Normalise column names
df.rename(columns=COLUMN_MAP, inplace=True)

# Drop duplicate columns that may appear after rename (keep first)
df = df.loc[:, ~df.columns.duplicated()]

# Keep only features that actually exist in this CSV
available = [f for f in FEATURES if f in df.columns]
missing   = [f for f in FEATURES if f not in df.columns]
if missing:
    print(f"  ⚠ Features not in CSV (will be skipped): {missing}")

FEATURES = available
print(f"  Using {len(FEATURES)} features: {FEATURES}")

# Drop rows where target or any feature is NaN
df = df.dropna(subset=FEATURES + [TARGET])
print(f"  After dropping NaN rows: {df.shape}")

X = df[FEATURES].astype(float)
y = df[TARGET].astype(int)

print(f"\nTarget distribution:\n{y.value_counts(normalize=True).round(3)}")

# ── Feature engineering ───────────────────────────────────────────────────────
# Derived features that capture cross-sensor fault patterns

X = X.copy()
X["RPM_LOAD_RATIO"]     = X["ENGINE_RPM"] / (X["ENGINE_LOAD"].replace(0, 1))
X["TEMP_RPM_RATIO"]     = X["ENGINE_COOLANT_TEMP"] / (X["ENGINE_RPM"].replace(0, 1))
X["THROTTLE_LOAD_DIFF"] = X["THROTTLE_POS"] - X["ENGINE_LOAD"]

stft1 = X["SHORT_TERM_FUEL_TRIM_BANK_1"].values if "SHORT_TERM_FUEL_TRIM_BANK_1" in X.columns else np.zeros(len(X))
ltft2 = X["LONG_TERM_FUEL_TRIM_BANK_2"].values  if "LONG_TERM_FUEL_TRIM_BANK_2"  in X.columns else np.zeros(len(X))
X["FUEL_TRIM_TOTAL"] = stft1 + ltft2

ait = X["AIR_INTAKE_TEMP"].values if "AIR_INTAKE_TEMP" in X.columns else X["ENGINE_COOLANT_TEMP"].values
X["INTAKE_TEMP_DIFF"] = X["ENGINE_COOLANT_TEMP"].values - ait

print(f"\nFinal feature count: {len(X.columns)}")

# ── Train / test split ────────────────────────────────────────────────────────

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(f"Train: {X_train.shape}  Test: {X_test.shape}")

# ── Model ─────────────────────────────────────────────────────────────────────

pipeline = Pipeline([
    ("scaler", StandardScaler()),
    ("clf", GradientBoostingClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        min_samples_leaf=15,
        max_features="sqrt",
        random_state=42,
    )),
])

print("\nTraining Gradient Boosting model ...")
pipeline.fit(X_train, y_train)

# ── Evaluate ──────────────────────────────────────────────────────────────────

y_pred  = pipeline.predict(X_test)
y_proba = pipeline.predict_proba(X_test)[:, 1]

print("\n─── Evaluation ───────────────────────────────────────────────────────")
print(f"Accuracy : {accuracy_score(y_test, y_pred):.4f}")
print(f"F1 Score : {f1_score(y_test, y_pred):.4f}")
print(f"ROC-AUC  : {roc_auc_score(y_test, y_proba):.4f}")
print("\nClassification Report:")
print(classification_report(y_test, y_pred, target_names=["Healthy", "Fault"]))
print("Confusion Matrix:")
print(confusion_matrix(y_test, y_pred))

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_scores = cross_val_score(pipeline, X, y, cv=cv, scoring="roc_auc")
print(f"\n5-Fold CV ROC-AUC: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

clf = pipeline.named_steps["clf"]
importances = pd.DataFrame({
    "Feature": X.columns,
    "Importance": clf.feature_importances_,
}).sort_values("Importance", ascending=False)
print("\nFeature Importances:")
print(importances.to_string(index=False))

# ── Save model ────────────────────────────────────────────────────────────────

joblib.dump(pipeline, MODEL_PATH)
print(f"\nModel saved → {MODEL_PATH}")

# ── Save metadata — default values used when a sensor is not available ────────
# Use training medians so missing sensors don't skew predictions.

medians = X_train[FEATURES].median().to_dict()
# Derived feature defaults
medians["RPM_LOAD_RATIO"]     = medians["ENGINE_RPM"] / max(medians.get("ENGINE_LOAD", 1), 1)
medians["TEMP_RPM_RATIO"]     = medians["ENGINE_COOLANT_TEMP"] / max(medians["ENGINE_RPM"], 1)
medians["THROTTLE_LOAD_DIFF"] = medians["THROTTLE_POS"] - medians.get("ENGINE_LOAD", 0)
medians["FUEL_TRIM_TOTAL"]    = (
    medians.get("SHORT_TERM_FUEL_TRIM_BANK_1", 0) +
    medians.get("LONG_TERM_FUEL_TRIM_BANK_2", 0)
)
medians["INTAKE_TEMP_DIFF"]   = (
    medians["ENGINE_COOLANT_TEMP"] - medians.get("AIR_INTAKE_TEMP", medians["ENGINE_COOLANT_TEMP"])
)

# Store the ordered feature list so the route knows the exact column order
medians["__feature_order__"] = list(X.columns)

with open(META_PATH, "w") as f:
    json.dump(medians, f, indent=4)
print(f"Metadata saved → {META_PATH}")
print("\nDone! Restart the backend to load the new model.")
