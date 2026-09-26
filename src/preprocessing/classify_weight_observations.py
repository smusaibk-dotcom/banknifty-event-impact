from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "index_weightage"
    / "constituent_weights_raw.csv"
)

OUTPUT_FILE = INPUT_FILE


# ---------------------------------------------------------------------------
# Official Nifty Bank rebalancing implementation dates
# ---------------------------------------------------------------------------

REBALANCE_EFFECTIVE_DATES = {
    "2023-03-31",
    "2023-09-29",
    "2024-03-28",
    "2024-09-30",
    "2025-03-28",
    "2025-09-30",
    "2026-03-30",
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    required_columns = {
        "date",
        "symbol",
        "weightage_pct",
    }

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

    df["weight_observation_type"] = "MONTH_END"

    df.loc[
        df["date"].isin(REBALANCE_EFFECTIVE_DATES),
        "weight_observation_type",
    ] = "REBALANCE_EFFECTIVE"

    df = (
        df.sort_values(["date", "symbol"])
        .reset_index(drop=True)
    )

    df.to_csv(OUTPUT_FILE, index=False)

    print("\nWeight observation classification completed.")
    print(f"Output: {OUTPUT_FILE}")

    print("\nObservation type counts:")
    print(
        df["weight_observation_type"]
        .value_counts()
        .sort_index()
    )

    print("\nRebalance observations:")
    rebalance_df = df[
        df["weight_observation_type"] == "REBALANCE_EFFECTIVE"
    ]

    print(
        rebalance_df[
            ["date", "symbol", "weightage_pct"]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()