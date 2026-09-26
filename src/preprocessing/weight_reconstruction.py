from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

WEIGHT_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "index_weightage"
    / "constituent_weights_raw.csv"
)

STOCK_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "constituent_stocks_raw.csv"
)

REGIME_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "index_weightage"
    / "constituent_regimes.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "index_weightage"
)

DAILY_OUTPUT_FILE = (
    OUTPUT_DIR
    / "daily_weight_reconstruction.csv"
)

VALIDATION_OUTPUT_FILE = (
    OUTPUT_DIR
    / "weight_reconstruction_validation.csv"
)

START_DATE = pd.Timestamp("2023-01-01")
END_DATE = pd.Timestamp("2026-08-31")

WEIGHT_SUM_TARGET = 100.0
WEIGHT_SUM_TOLERANCE = 0.05


# ============================================================
# LOAD DATA
# ============================================================

def load_data() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    weights = pd.read_csv(WEIGHT_FILE)
    stocks = pd.read_csv(STOCK_FILE)
    regimes = pd.read_csv(REGIME_FILE)

    weights["date"] = pd.to_datetime(weights["date"])
    stocks["date"] = pd.to_datetime(stocks["date"])

    regimes["start_snapshot_date"] = pd.to_datetime(
        regimes["start_snapshot_date"]
    )

    regimes["end_snapshot_date"] = pd.to_datetime(
        regimes["end_snapshot_date"]
    )

    return weights, stocks, regimes


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_input_columns(
    weights: pd.DataFrame,
    stocks: pd.DataFrame,
    regimes: pd.DataFrame,
) -> None:

    required_weight_columns = {
        "date",
        "symbol",
        "weightage_pct",
    }

    required_stock_columns = {
        "date",
        "symbol",
        "close",
    }

    required_regime_columns = {
        "regime_id",
        "start_snapshot_date",
        "end_snapshot_date",
        "constituent_count",
    }

    missing_weights = (
        required_weight_columns
        - set(weights.columns)
    )

    missing_stocks = (
        required_stock_columns
        - set(stocks.columns)
    )

    missing_regimes = (
        required_regime_columns
        - set(regimes.columns)
    )

    if missing_weights:
        raise ValueError(
            "Missing columns in weight file: "
            f"{sorted(missing_weights)}"
        )

    if missing_stocks:
        raise ValueError(
            "Missing columns in stock file: "
            f"{sorted(missing_stocks)}"
        )

    if missing_regimes:
        raise ValueError(
            "Missing columns in regime file: "
            f"{sorted(missing_regimes)}"
        )


# ============================================================
# OFFICIAL WEIGHTS
# ============================================================

def get_official_weights(
    weights: pd.DataFrame,
    date: pd.Timestamp,
) -> pd.Series:

    data = weights.loc[
        weights["date"] == date,
        ["symbol", "weightage_pct"],
    ].copy()

    if data.empty:
        raise ValueError(
            f"No official weights found for "
            f"{date.date()}."
        )

    if data["symbol"].duplicated().any():
        raise ValueError(
            f"Duplicate symbols found for "
            f"{date.date()}."
        )

    data["weightage_pct"] = pd.to_numeric(
        data["weightage_pct"],
        errors="coerce",
    )

    if data["weightage_pct"].isna().any():
        raise ValueError(
            f"Invalid weight values found for "
            f"{date.date()}."
        )

    if (data["weightage_pct"] <= 0).any():
        raise ValueError(
            f"Non-positive weights found for "
            f"{date.date()}."
        )

    weight_sum = data["weightage_pct"].sum()

    if not np.isclose(
        weight_sum,
        WEIGHT_SUM_TARGET,
        atol=WEIGHT_SUM_TOLERANCE,
    ):
        raise ValueError(
            f"Weight sum on {date.date()} = "
            f"{weight_sum:.6f}."
        )

    return (
        data
        .set_index("symbol")["weightage_pct"]
        .astype(float)
    )


# ============================================================
# STOCK PRICE PREPARATION
# ============================================================

def prepare_prices(
    stocks: pd.DataFrame,
    symbols: set[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:

    data = stocks.loc[
        stocks["date"].between(
            start_date,
            end_date,
        )
        & stocks["symbol"].isin(symbols),
        ["date", "symbol", "close"],
    ].copy()

    data["close"] = pd.to_numeric(
        data["close"],
        errors="coerce",
    )

    if data["close"].isna().any():
        raise ValueError(
            "Invalid or missing close prices found "
            f"between {start_date.date()} and "
            f"{end_date.date()}."
        )

    duplicate_mask = data.duplicated(
        subset=["date", "symbol"],
        keep=False,
    )

    if duplicate_mask.any():
        duplicates = data.loc[
            duplicate_mask,
            ["date", "symbol"],
        ].drop_duplicates()

        raise ValueError(
            "Duplicate stock-price records found:\n"
            f"{duplicates.to_string(index=False)}"
        )

    prices = (
        data
        .pivot(
            index="date",
            columns="symbol",
            values="close",
        )
        .sort_index()
    )

    missing_symbols = (
        symbols - set(prices.columns)
    )

    if missing_symbols:
        raise ValueError(
            "Missing stock-price columns: "
            f"{sorted(missing_symbols)}"
        )

    prices = prices[
        sorted(symbols)
    ]

    return prices


# ============================================================
# PRICE COVERAGE
# ============================================================

def validate_price_coverage(
    prices: pd.DataFrame,
    symbols: set[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> None:

    interval = prices.loc[
        start_date:end_date,
        sorted(symbols),
    ]

    if interval.empty:
        raise ValueError(
            f"No prices available between "
            f"{start_date.date()} and "
            f"{end_date.date()}."
        )

    missing = interval.isna()

    if missing.any().any():
        missing_counts = missing.sum()

        details = (
            missing_counts[
                missing_counts > 0
            ]
            .to_dict()
        )

        raise ValueError(
            "Missing close prices during "
            f"{start_date.date()} → "
            f"{end_date.date()}: "
            f"{details}"
        )

    if (interval <= 0).any().any():
        raise ValueError(
            "Non-positive close prices detected."
        )


# ============================================================
# DAILY BACKWARD RECONSTRUCTION
# ============================================================

def reconstruct_from_anchor(
    prices: pd.DataFrame,
    anchor_weights: pd.Series,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    """
    Reconstruct weights backward from the official end-date anchor.

    The end_date itself is NOT returned as a reconstructed observation.
    The earlier endpoint IS reconstructed so that it can be validated
    against its official weight.

    Formula:

        G_i,t = Close_i,t / Close_i,t-1

        w_i,t-1 =
            (w_i,t / G_i,t)
            ----------------
            sum_j(w_j,t / G_j,t)
    """

    symbols = list(anchor_weights.index)

    interval_prices = prices.loc[
        start_date:end_date,
        symbols,
    ].copy()

    dates = (
        interval_prices
        .index
        .sort_values()
    )

    if start_date not in dates:
        raise ValueError(
            f"Start date {start_date.date()} "
            "missing from prices."
        )

    if end_date not in dates:
        raise ValueError(
            f"End date {end_date.date()} "
            "missing from prices."
        )

    current_weights = (
        anchor_weights
        .astype(float)
        .copy()
    )

    records = []

    # --------------------------------------------------------
    # Walk backward day by day.
    #
    # The official end-date anchor is NOT added here.
    # --------------------------------------------------------

    for i in range(
        len(dates) - 1,
        0,
        -1,
    ):
        current_date = dates[i]
        previous_date = dates[i - 1]

        current_prices = (
            interval_prices
            .loc[current_date, symbols]
        )

        previous_prices = (
            interval_prices
            .loc[previous_date, symbols]
        )

        price_ratio = (
            current_prices
            / previous_prices
        )

        if (price_ratio <= 0).any():
            raise ValueError(
                f"Invalid price ratio between "
                f"{previous_date.date()} and "
                f"{current_date.date()}."
            )

        unnormalized_weights = (
            current_weights
            / price_ratio
        )

        normalization_factor = (
            unnormalized_weights.sum()
        )

        if normalization_factor <= 0:
            raise ValueError(
                f"Invalid normalization factor on "
                f"{previous_date.date()}."
            )

        previous_weights = (
            unnormalized_weights
            / normalization_factor
            * 100.0
        )

        current_weights = previous_weights

        for symbol in symbols:
            records.append(
                {
                    "date": previous_date,
                    "symbol": symbol,
                    "reconstructed_weight": (
                        current_weights[symbol]
                    ),
                }
            )

    return pd.DataFrame(records)


# ============================================================
# VALIDATION AT OFFICIAL EARLIER ANCHOR
# ============================================================

def validate_reconstructed_endpoint(
    reconstructed: pd.DataFrame,
    official_weights: pd.Series,
    earlier_date: pd.Timestamp,
    later_anchor: pd.Timestamp,
    regime_id: str,
) -> tuple[pd.DataFrame, dict]:

    endpoint = reconstructed.loc[
        reconstructed["date"] == earlier_date,
        ["date", "symbol", "reconstructed_weight"],
    ].copy()

    if endpoint.empty:
        raise ValueError(
            f"No reconstructed data found for "
            f"{earlier_date.date()}."
        )

    endpoint = endpoint.set_index("symbol")

    reconstructed_symbols = set(
        endpoint.index
    )

    official_symbols = set(
        official_weights.index
    )

    if reconstructed_symbols != official_symbols:
        raise ValueError(
            f"Constituent mismatch at "
            f"{earlier_date.date()}."
        )

    endpoint["official_weight"] = (
        official_weights
    )

    endpoint["weight_error"] = (
        endpoint["reconstructed_weight"]
        - endpoint["official_weight"]
    )

    endpoint["abs_weight_error"] = (
        endpoint["weight_error"].abs()
    )

    endpoint["error_pct_of_official"] = np.where(
        endpoint["official_weight"] != 0,
        (
            endpoint["abs_weight_error"]
            / endpoint["official_weight"].abs()
            * 100.0
        ),
        np.nan,
    )

    errors = endpoint[
        "weight_error"
    ]

    validation_record = {
        "regime_id": regime_id,
        "later_anchor": later_anchor,
        "earlier_anchor": earlier_date,
        "constituent_count": len(endpoint),
        "mae": errors.abs().mean(),
        "rmse": np.sqrt(
            np.mean(errors ** 2)
        ),
        "max_abs_error": errors.abs().max(),
        "correlation": (
            endpoint["reconstructed_weight"]
            .corr(
                endpoint["official_weight"]
            )
        ),
        "reconstructed_weight_sum": (
            endpoint["reconstructed_weight"]
            .sum()
        ),
        "official_weight_sum": (
            endpoint["official_weight"]
            .sum()
        ),
        "status": "validated",
    }

    endpoint = (
        endpoint
        .reset_index()
        .rename(
            columns={
                "index": "symbol"
            }
        )
    )

    endpoint["date"] = earlier_date
    endpoint["regime_id"] = regime_id
    endpoint["later_anchor"] = later_anchor

    endpoint = endpoint[
        [
            "regime_id",
            "later_anchor",
            "date",
            "symbol",
            "reconstructed_weight",
            "official_weight",
            "weight_error",
            "abs_weight_error",
            "error_pct_of_official",
        ]
    ]

    return endpoint, validation_record


# ============================================================
# PROCESS ONE REGIME
# ============================================================

def process_regime(
    regime: pd.Series,
    weights: pd.DataFrame,
    stocks: pd.DataFrame,
) -> tuple[
    list[pd.DataFrame],
    list[dict],
]:

    regime_id = regime["regime_id"]

    regime_start = pd.Timestamp(
        regime["start_snapshot_date"]
    )

    regime_end = pd.Timestamp(
        regime["end_snapshot_date"]
    )

    # --------------------------------------------------------
    # Official weight observations belonging to this regime.
    # --------------------------------------------------------

    regime_dates = (
        weights.loc[
            (
                weights["date"]
                >= regime_start
            )
            & (
                weights["date"]
                <= regime_end
            ),
            "date",
        ]
        .drop_duplicates()
        .sort_values()
        .tolist()
    )

    if len(regime_dates) < 2:
        raise ValueError(
            f"Regime {regime_id} does not contain "
            "at least two official weight observations."
        )

    reconstructed_parts: list[pd.DataFrame] = []
    validation_records: list[dict] = []

    # --------------------------------------------------------
    # Consecutive official observations define each
    # independent reconstruction interval.
    # --------------------------------------------------------

    for i in range(
        len(regime_dates) - 1
    ):

        earlier_date = regime_dates[i]
        later_date = regime_dates[i + 1]

        print(
            f"    {regime_id}: "
            f"{earlier_date.date()} → "
            f"{later_date.date()}"
        )

        earlier_weights = (
            get_official_weights(
                weights,
                earlier_date,
            )
        )

        later_weights = (
            get_official_weights(
                weights,
                later_date,
            )
        )

        earlier_symbols = set(
            earlier_weights.index
        )

        later_symbols = set(
            later_weights.index
        )

        if earlier_symbols != later_symbols:
            raise ValueError(
                "Constituent universe changed "
                "inside a stable regime: "
                f"{regime_id}, "
                f"{earlier_date.date()} → "
                f"{later_date.date()}."
            )

        symbols = later_symbols

        prices = prepare_prices(
            stocks,
            symbols,
            earlier_date,
            later_date,
        )

        validate_price_coverage(
            prices,
            symbols,
            earlier_date,
            later_date,
        )

        # ----------------------------------------------------
        # Reconstruct backward from the LATER official anchor.
        # ----------------------------------------------------

        reconstructed = reconstruct_from_anchor(
            prices=prices,
            anchor_weights=later_weights,
            start_date=earlier_date,
            end_date=later_date,
        )

        # ----------------------------------------------------
        # Reconstruct backward from the LATER official anchor.
        #
        # The later anchor itself is NOT included in the
        # reconstructed series because it will be added to the
        # final daily dataset separately as an OFFICIAL value.
        #
        # Validation is performed ONLY at the EARLIER endpoint.
        # ----------------------------------------------------

        reconstructed_parts.append(
            reconstructed
        )

        _, metrics = (
            validate_reconstructed_endpoint(
                reconstructed=reconstructed,
                official_weights=earlier_weights,
                earlier_date=earlier_date,
                later_anchor=later_date,
                regime_id=regime_id,
            )
        )

        validation_records.append(
            metrics
        )

        print(
            f"        MAE = "
            f"{metrics['mae']:.8f} | "
            f"RMSE = "
            f"{metrics['rmse']:.8f} | "
            f"MAX = "
            f"{metrics['max_abs_error']:.8f}"
        )

    return (
        reconstructed_parts,
        validation_records,
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print("=" * 70)
    print(
        "NIFTY BANK DAILY WEIGHT RECONSTRUCTION"
    )
    print("=" * 70)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # 1. Load
    # --------------------------------------------------------

    print("\n[1/5] Loading data...")

    weights, stocks, regimes = load_data()

    validate_input_columns(
        weights,
        stocks,
        regimes,
    )

    print(
        f"Official snapshots : "
        f"{weights['date'].nunique()}"
    )

    print(
        f"Regimes            : "
        f"{len(regimes)}"
    )

    # --------------------------------------------------------
    # 2. Process regimes
    # --------------------------------------------------------

    print(
        "\n[2/5] Processing constituent regimes..."
    )

    all_reconstructed = []
    all_validation = []

    for _, regime in regimes.sort_values(
        "start_snapshot_date"
    ).iterrows():

        print(
            f"\n  Regime {regime['regime_id']} "
            f"({int(regime['constituent_count'])} "
            f"constituents)"
        )

        reconstructed, validation = (
            process_regime(
                regime,
                weights,
                stocks,
            )
        )

        all_reconstructed.extend(
            reconstructed
        )

        all_validation.extend(
            validation
        )

    if not all_reconstructed:
        raise RuntimeError(
            "No reconstruction intervals produced."
        )

    # --------------------------------------------------------
    # 3. Combine reconstructed observations
    # --------------------------------------------------------

    print(
        "\n[3/5] Combining reconstructed observations..."
    )

    reconstructed_output = pd.concat(
        all_reconstructed,
        ignore_index=True,
    )

    reconstructed_output = (
        reconstructed_output
        .drop_duplicates(
            subset=[
                "date",
                "symbol",
            ],
            keep="first",
        )
        .sort_values(
            [
                "date",
                "symbol",
            ]
        )
        .reset_index(drop=True)
    )

    reconstructed_output["weight"] = (
        reconstructed_output[
            "reconstructed_weight"
        ]
    )

    reconstructed_output["weight_source"] = (
        "RECONSTRUCTED"
    )

    reconstructed_output = (
        reconstructed_output[
            [
                "date",
                "symbol",
                "weight",
                "weight_source",
            ]
        ]
    )

    # --------------------------------------------------------
    # 4. Add official monthly observations
    #
    # IMPORTANT:
    # Official observations are preserved exactly as published.
    # They are NOT normalized and NOT replaced by reconstructed
    # values.
    # --------------------------------------------------------

    print(
        "\n[4/5] Adding official monthly observations..."
    )

    official_output = (
        weights[
            [
                "date",
                "symbol",
                "weightage_pct",
            ]
        ]
        .copy()
        .rename(
            columns={
                "weightage_pct": "weight",
            }
        )
    )

    official_output["weight_source"] = (
        "OFFICIAL"
    )

    official_output = (
        official_output[
            [
                "date",
                "symbol",
                "weight",
                "weight_source",
            ]
        ]
    )

    # Official observations must win over reconstructed
    # observations if the same date + symbol appears in both.
    daily_output = pd.concat(
        [
            official_output,
            reconstructed_output,
        ],
        ignore_index=True,
    )

    daily_output = (
        daily_output
        .drop_duplicates(
            subset=[
                "date",
                "symbol",
            ],
            keep="first",
        )
        .sort_values(
            [
                "date",
                "symbol",
            ]
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # Final daily-output validation
    # --------------------------------------------------------

    # One record per date + constituent.
    if daily_output.duplicated(
        subset=["date", "symbol"]
    ).any():

        duplicates = (
            daily_output.loc[
                daily_output.duplicated(
                    subset=[
                        "date",
                        "symbol",
                    ],
                    keep=False,
                )
            ]
            .sort_values(
                [
                    "date",
                    "symbol",
                ]
            )
        )

        raise ValueError(
            "Duplicate date + symbol records found "
            "in final daily output:\n"
            f"{duplicates.to_string(index=False)}"
        )

    # Every official snapshot date must be present.
    official_dates = set(
        weights["date"].unique()
    )

    final_dates = set(
        daily_output["date"].unique()
    )

    missing_official_dates = (
        official_dates - final_dates
    )

    if missing_official_dates:
        raise ValueError(
            "Official snapshot dates missing from "
            "final daily output: "
            f"{sorted(missing_official_dates)}"
        )

    # Every official value must remain exactly unchanged.
    official_check = official_output.merge(
        daily_output,
        on=[
            "date",
            "symbol",
        ],
        how="left",
        suffixes=(
            "_expected",
            "_actual",
        ),
        validate="one_to_one",
    )

    if not np.allclose(
        official_check["weight_expected"],
        official_check["weight_actual"],
        rtol=0.0,
        atol=1e-12,
    ):
        raise ValueError(
            "Official weights were altered in the "
            "final daily output."
        )

    # Reconstructed rows must sum to 100%.
    reconstructed_rows = (
        daily_output[
            daily_output["weight_source"]
            == "RECONSTRUCTED"
        ]
    )

    reconstructed_sums = (
        reconstructed_rows
        .groupby("date")["weight"]
        .sum()
    )

    if not np.allclose(
        reconstructed_sums.values,
        100.0,
        atol=1e-8,
    ):
        bad_dates = (
            reconstructed_sums[
                ~np.isclose(
                    reconstructed_sums,
                    100.0,
                    atol=1e-8,
                )
            ]
        )

        raise ValueError(
            "Reconstructed daily weights do not "
            "sum to 100%:\n"
            f"{bad_dates.to_string()}"
        )

    # --------------------------------------------------------
    # 5. Save outputs
    # --------------------------------------------------------

    print(
        "\n[5/5] Saving outputs..."
    )

    validation_output = pd.DataFrame(
        all_validation
    )

    validation_output = (
        validation_output
        .sort_values(
            [
                "later_anchor",
                "earlier_anchor",
            ]
        )
        .reset_index(drop=True)
    )

    daily_output.to_csv(
        DAILY_OUTPUT_FILE,
        index=False,
    )

    validation_output.to_csv(
        VALIDATION_OUTPUT_FILE,
        index=False,
    )

    print(
        "\n" + "=" * 70
    )

    print(
        "RECONSTRUCTION COMPLETE"
    )

    print(
        "=" * 70
    )

    print(
        f"\nDaily rows: "
        f"{len(daily_output):,}"
    )

    print(
        f"Daily dates: "
        f"{daily_output['date'].nunique():,}"
    )

    print(
        f"Official rows: "
        f"{(daily_output['weight_source'] == 'OFFICIAL').sum():,}"
    )

    print(
        f"Reconstructed rows: "
        f"{(daily_output['weight_source'] == 'RECONSTRUCTED').sum():,}"
    )

    print(
        f"Validation intervals: "
        f"{len(validation_output):,}"
    )

    print(
        "\nDaily output:"
    )

    print(
        DAILY_OUTPUT_FILE
    )

    print(
        "\nValidation output:"
    )

    print(
        VALIDATION_OUTPUT_FILE
    )

    print(
        "\nValidation summary:"
    )

    print(
        validation_output[
            [
                "regime_id",
                "earlier_anchor",
                "later_anchor",
                "constituent_count",
                "mae",
                "rmse",
                "max_abs_error",
                "correlation",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()