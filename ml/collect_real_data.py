"""
Export labeled diagnostics from MongoDB and merge with the original
training CSV, then retrain the model.

Usage:
  cd backend
  python ml/collect_real_data.py

Requirements:
  - MongoDB running with diagnostics that have user_label set
  - .env file with MONGODB_URL
"""

import os
import sys
import json
import asyncio
import pandas as pd
import numpy as np
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

MONGO_URL        = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME          = os.getenv("DATABASE_NAME", "vehicle_diagnostic")
ORIGINAL_CSV     = os.path.join(os.path.dirname(__file__), "cleaned_data.csv")
REAL_DATA_CSV    = os.path.join(os.path.dirname(__file__), "real_data.csv")
COMBINED_CSV     = os.path.join(os.path.dirname(__file__), "combined_data.csv")

SENSOR_FEATURES = [
    "ENGINE_RPM", "SPEED", "ENGINE_LOAD", "ENGINE_COOLANT_TEMP",
    "THROTTLE_POS", "MAF", "FUEL_PRESSURE", "INTAKE_MANIFOLD_PRESSURE",
    "AIR_INTAKE_TEMP", "BAROMETRIC_PRESSURE", "FUEL_LEVEL",
    "SHORT_TERM_FUEL_TRIM_BANK_1", "LONG_TERM_FUEL_TRIM_BANK_2",
    "SHORT_TERM_FUEL_TRIM_BANK_2", "ENGINE_RUNTIME", "EQUIV_RATIO",
]


async def export_labeled_diagnostics():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Only fetch diagnostics that have been labeled by the user
    cursor = db.diagnostics.find(
        {"user_label": {"$exists": True}},
        {"sensor_data": 1, "user_label": 1, "_id": 0}
    )
    docs = await cursor.to_list(length=None)
    client.close()

    if not docs:
        print("No labeled diagnostics found in MongoDB.")
        print("Label some diagnostics first via PATCH /diagnostics/{id}/label")
        return 0

    rows = []
    for doc in docs:
        row = {}
        sensor_data = doc.get("sensor_data", {})
        for feat in SENSOR_FEATURES:
            # Try exact match and case-insensitive match
            val = sensor_data.get(feat) or sensor_data.get(feat.lower())
            row[feat] = float(val) if val is not None else np.nan
        row["HAS_FAULT"] = int(doc["user_label"])
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(REAL_DATA_CSV, index=False)
    print(f"Exported {len(df)} labeled diagnostics → {REAL_DATA_CSV}")
    print(f"Fault distribution:\n{df['HAS_FAULT'].value_counts()}")
    return len(df)


def merge_and_retrain(n_real: int):
    if n_real == 0:
        print("Nothing to merge. Retraining on original data only.")
        combined_path = ORIGINAL_CSV
    else:
        print(f"\nMerging original data with {n_real} real-world samples ...")
        original = pd.read_csv(ORIGINAL_CSV)

        # Rename columns to match our feature names
        original.rename(columns={
            "BAROMETRIC_PRESSURE(KPA)": "BAROMETRIC_PRESSURE",
            "TERM_FUEL_TRIM_BANK_1": "SHORT_TERM_FUEL_TRIM_BANK_1",
        }, inplace=True)
        original = original.loc[:, ~original.columns.duplicated()]

        real = pd.read_csv(REAL_DATA_CSV)

        # Real data gets 3x weight — it's from actual cars, more valuable
        real_weighted = pd.concat([real] * 3, ignore_index=True)

        # Align columns — keep only shared columns + HAS_FAULT
        shared_cols = list(set(original.columns) & set(real_weighted.columns))
        combined = pd.concat(
            [original[shared_cols], real_weighted[shared_cols]],
            ignore_index=True
        )
        combined.to_csv(COMBINED_CSV, index=False)
        print(f"Combined dataset: {combined.shape}")
        print(f"Fault distribution:\n{combined['HAS_FAULT'].value_counts()}")
        combined_path = COMBINED_CSV

    # Run the training script with the combined data
    import subprocess
    result = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "train_model.py")],
        env={**os.environ, "TRAIN_DATA_PATH": combined_path},
    )
    return result.returncode


if __name__ == "__main__":
    n = asyncio.run(export_labeled_diagnostics())
    code = merge_and_retrain(n)
    sys.exit(code)
