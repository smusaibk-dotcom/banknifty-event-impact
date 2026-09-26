from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "constituent_regimes.csv"
)

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

OUTPUT_FILE = PROCESSED_DIR / "constituent_regimes.csv"


def amend_regime_boundaries(
    regimes: pd.DataFrame,
) -> pd.DataFrame:
    """Apply the verified constituent-regime boundary corrections."""

    regimes = regimes.copy()

    regimes["start_snapshot_date"] = pd.to_datetime(
        regimes["start_snapshot_date"]
    )

    regimes["end_snapshot_date"] = pd.to_datetime(
        regimes["end_snapshot_date"]
    )

    corrections = {
        "R1": {
            "start_snapshot_date": pd.Timestamp("2023-01-02"),
            "end_snapshot_date": pd.Timestamp("2024-09-29"),
        },
        "R2": {
            "start_snapshot_date": pd.Timestamp("2024-09-30"),
            "end_snapshot_date": pd.Timestamp("2025-12-30"),
        },
        "R3": {
            "start_snapshot_date": pd.Timestamp("2025-12-31"),
        },
    }

    for regime_id, values in corrections.items():
        mask = regimes["regime_id"].eq(regime_id)

        if not mask.any():
            raise ValueError(
                f"Expected regime {regime_id} was not found."
            )

        for column, value in values.items():
            regimes.loc[mask, column] = value

    return regimes


def validate_regime_boundaries(
    regimes: pd.DataFrame,
) -> None:
    """Validate the corrected regime boundaries."""

    regimes = regimes.sort_values("start_snapshot_date")

    if regimes["regime_id"].duplicated().any():
        raise ValueError("Duplicate regime IDs found.")

    if (
        regimes["start_snapshot_date"]
        > regimes["end_snapshot_date"]
    ).any():
        raise ValueError(
            "A regime starts after its end date."
        )

    expected_boundaries = {
        "R1": (
            pd.Timestamp("2023-01-02"),
            pd.Timestamp("2024-09-29"),
        ),
        "R2": (
            pd.Timestamp("2024-09-30"),
            pd.Timestamp("2025-12-30"),
        ),
        "R3": (
            pd.Timestamp("2025-12-31"),
            None,
        ),
    }

    for regime_id, (expected_start, expected_end) in (
        expected_boundaries.items()
    ):
        row = regimes.loc[
            regimes["regime_id"] == regime_id
        ].iloc[0]

        if expected_start is not None:
            if row["start_snapshot_date"] != expected_start:
                raise ValueError(
                    f"{regime_id} start boundary is incorrect."
                )

        if expected_end is not None:
            if row["end_snapshot_date"] != expected_end:
                raise ValueError(
                    f"{regime_id} end boundary is incorrect."
                )

    # Consecutive regimes must meet exactly at the boundary.
    ordered = regimes.sort_values(
        "start_snapshot_date"
    ).reset_index(drop=True)

    for i in range(len(ordered) - 1):
        current_end = ordered.loc[
            i, "end_snapshot_date"
        ]

        next_start = ordered.loc[
            i + 1, "start_snapshot_date"
        ]

        if current_end >= next_start:
            raise ValueError(
                "Regime boundaries overlap."
            )


def main() -> None:
    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    regimes = pd.read_csv(RAW_FILE)

    amended_regimes = amend_regime_boundaries(
        regimes
    )

    validate_regime_boundaries(
        amended_regimes
    )

    amended_regimes.to_csv(
        OUTPUT_FILE,
        index=False,
    )


if __name__ == "__main__":
    main()