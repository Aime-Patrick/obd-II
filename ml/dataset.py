"""Shared OBD training dataset loading (matches train_model.py)."""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

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
DEFAULT_DATA_PATH = os.path.join(os.path.dirname(__file__), "cleaned_data.csv")
RANDOM_STATE = 42
TEST_SIZE = 0.2


def default_data_path() -> str:
    return os.environ.get("TRAIN_DATA_PATH", DEFAULT_DATA_PATH)


def load_training_frame(data_path: str | None = None) -> tuple[pd.DataFrame, pd.Series]:
    """Load CSV, engineer features, return X and y."""
    path = data_path or default_data_path()
    df = pd.read_csv(path)
    df.rename(columns=COLUMN_MAP, inplace=True)
    df = df.loc[:, ~df.columns.duplicated()]

    available = [f for f in FEATURES if f in df.columns]
    df = df.dropna(subset=available + [TARGET])

    X = df[available].astype(float).copy()
    y = df[TARGET].astype(int)

    X["RPM_LOAD_RATIO"] = X["ENGINE_RPM"] / X["ENGINE_LOAD"].replace(0, 1)
    X["TEMP_RPM_RATIO"] = X["ENGINE_COOLANT_TEMP"] / X["ENGINE_RPM"].replace(0, 1)
    X["THROTTLE_LOAD_DIFF"] = X["THROTTLE_POS"] - X["ENGINE_LOAD"]

    stft1 = (
        X["SHORT_TERM_FUEL_TRIM_BANK_1"].values
        if "SHORT_TERM_FUEL_TRIM_BANK_1" in X.columns
        else np.zeros(len(X))
    )
    ltft2 = (
        X["LONG_TERM_FUEL_TRIM_BANK_2"].values
        if "LONG_TERM_FUEL_TRIM_BANK_2" in X.columns
        else np.zeros(len(X))
    )
    X["FUEL_TRIM_TOTAL"] = stft1 + ltft2

    ait = (
        X["AIR_INTAKE_TEMP"].values
        if "AIR_INTAKE_TEMP" in X.columns
        else X["ENGINE_COOLANT_TEMP"].values
    )
    X["INTAKE_TEMP_DIFF"] = X["ENGINE_COOLANT_TEMP"].values - ait

    return X, y


def train_test_split_frame(
    X: pd.DataFrame,
    y: pd.Series,
    *,
    random_state: int = RANDOM_STATE,
    test_size: float = TEST_SIZE,
):
    return train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
