from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "constituent_regime_members.csv"
)

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

OUTPUT_FILE = (
    PROCESSED_DIR / "constituent_regime_members.csv"
)


def amend_regime_member_dates(
    members: pd.DataFrame,
) -> pd.DataFrame:
    """Amend only the incorrect R1 start snapshot date."""

    members = members.copy()

    members["start_snapshot_date"] = pd.to_datetime(
        members["start_snapshot_date"]
    )

    r1_mask = members["regime_id"].eq("R1")

    if not r1_mask.any():
        raise ValueError("R1 was not found in regime members.")

    members.loc[
        r1_mask,
        "start_snapshot_date",
    ] = pd.Timestamp("2023-01-02")

    return members


def validate_regime_members(
    members: pd.DataFrame,
) -> None:
    """Validate that only the intended amendment was made."""

    expected_counts = {
        "R1": 12,
        "R2": 12,
        "R3": 14,
    }

    actual_counts = (
        members.groupby("regime_id")["symbol"]
        .nunique()
        .to_dict()
    )

    if actual_counts != expected_counts:
        raise ValueError(
            "Unexpected regime member counts: "
            f"{actual_counts}"
        )

    if members.duplicated(
        subset=["regime_id", "symbol"]
    ).any():
        raise ValueError(
            "Duplicate regime_id + symbol records found."
        )

    expected_start_dates = {
        "R1": pd.Timestamp("2023-01-02"),
        "R2": pd.Timestamp("2024-09-30"),
        "R3": pd.Timestamp("2025-12-31"),
    }

    for regime_id, expected_date in expected_start_dates.items():

        dates = members.loc[
            members["regime_id"] == regime_id,
            "start_snapshot_date",
        ].unique()

        if len(dates) != 1 or dates[0] != expected_date:
            raise ValueError(
                f"Incorrect start date for {regime_id}: "
                f"{dates}"
            )


def main() -> None:

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    members = pd.read_csv(RAW_FILE)

    required_columns = {
        "regime_id",
        "start_snapshot_date",
        "symbol",
    }

    missing_columns = (
        required_columns - set(members.columns)
    )

    if missing_columns:
        raise ValueError(
            "Missing required columns: "
            f"{sorted(missing_columns)}"
        )

    amended_members = amend_regime_member_dates(
        members
    )

    validate_regime_members(
        amended_members
    )

    amended_members.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print(
        "Regime member amendment complete."
    )
    print(
        f"Saved to: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()