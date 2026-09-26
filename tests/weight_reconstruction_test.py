from __future__ import annotations

from pathlib import Path

import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

WEIGHTS_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "index_weightage"
    / "constituent_weights_raw.csv"
)

STOCKS_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "constituent_stocks_raw.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "index_weightage"
)

DAILY_WEIGHTS_FILE = (
    OUTPUT_DIR
    / "daily_weight_reconstruction.csv"
)

VALIDATION_FILE = (
    OUTPUT_DIR
    / "daily_weight_reconstruction_validation.csv"
)


# ------------------------------------------------------------
# First validation window
# ------------------------------------------------------------

START_ANCHOR = pd.Timestamp("2026-07-31")
END_ANCHOR = pd.Timestamp("2026-08-31")


# ============================================================
# LOAD DATA
# ============================================================

def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load official monthly weights and daily stock prices."""

    weights = pd.read_csv(
        WEIGHTS_FILE,
        parse_dates=["date"],
    )

    stocks = pd.read_csv(
        STOCKS_FILE,
        parse_dates=["date"],
    )

    return weights, stocks


# ============================================================
# GET OFFICIAL ANCHOR
# ============================================================

def get_official_weights(
    weights: pd.DataFrame,
    target_date: pd.Timestamp,
) -> pd.DataFrame:
    """Return official NIFTY Bank weights for one anchor date."""

    result = weights.loc[
        weights["date"] == target_date
    ].copy()

    if result.empty:
        raise ValueError(
            f"No official NIFTY Bank weights found "
            f"for {target_date.date()}."
        )

    return result[
        [
            "date",
            "symbol",
            "weightage_pct",
        ]
    ].copy()


# ============================================================
# GET STOCK PRICES
# ============================================================

def get_prices(
    stocks: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    symbols: set[str],
) -> pd.DataFrame:
    """
    Get daily constituent closing prices for the
    reconstruction period.

    Only symbols belonging to the active NIFTY Bank
    universe are retained.
    """

    result = stocks.loc[
        stocks["symbol"].isin(symbols)
        & (stocks["date"] >= start_date)
        & (stocks["date"] <= end_date)
    ].copy()

    if result.empty:
        raise ValueError(
            "No constituent stock prices found "
            "for the requested period."
        )

    result = result[
        [
            "date",
            "symbol",
            "close",
        ]
    ]

    # --------------------------------------------------------
    # Duplicate-date protection
    # --------------------------------------------------------

    duplicates = result.duplicated(
        subset=["date", "symbol"],
        keep=False,
    )

    if duplicates.any():

        duplicate_rows = result.loc[
            duplicates
        ]

        raise ValueError(
            "Duplicate stock-price records found "
            "for date/symbol combinations:\n"
            f"{duplicate_rows}"
        )

    return result


# ============================================================
# VALIDATE PRICE COVERAGE
# ============================================================

def validate_price_coverage(
    prices: pd.DataFrame,
    symbols: set[str],
) -> None:
    """Ensure every active constituent has prices on every date."""

    pivot = prices.pivot(
        index="date",
        columns="symbol",
        values="close",
    )

    missing = pivot.loc[
        :,
        sorted(symbols),
    ].isna()

    if missing.any().any():

        missing_records = []

        for date_value, row in missing.iterrows():

            missing_symbols = (
                row[row]
                .index
                .tolist()
            )

            if missing_symbols:

                missing_records.append(
                    (
                        date_value.date(),
                        missing_symbols,
                    )
                )

        raise ValueError(
            "Missing closing prices detected "
            "for active NIFTY Bank constituents:\n"
            f"{missing_records}"
        )


# ============================================================
# BACKWARD RECONSTRUCTION
# ============================================================

def reconstruct_backward(
    anchor_weights: pd.DataFrame,
    prices: pd.DataFrame,
) -> pd.DataFrame:
    """
    Reconstruct daily NIFTY Bank weights backwards.

    Starting from the known end-date weights:

        w(i,t)

    and using:

        G(i,t) = P(i,t) / P(i,t-1)

    calculate:

        w(i,t-1) =
            [w(i,t) / G(i,t)]
            /
            sum_j[w(j,t) / G(j,t)]

    The process is repeated recursively until the
    beginning of the validation window is reached.
    """

    symbols = set(
        anchor_weights["symbol"]
    )

    price_table = prices.pivot(
        index="date",
        columns="symbol",
        values="close",
    )

    price_table = price_table[
        sorted(symbols)
    ].sort_index()

    # --------------------------------------------------------
    # Start from known official weights.
    # --------------------------------------------------------

    current_weights = (
        anchor_weights
        .set_index("symbol")[
            "weightage_pct"
        ]
        .astype(float)
    )

    records = []

    # Store the official anchor itself.
    records.append(
        {
            "date": END_ANCHOR,
            **current_weights.to_dict(),
        }
    )

    trading_dates = list(
        price_table.index
    )

    # We move from the final trading date
    # backward one trading day at a time.
    trading_dates = sorted(
        trading_dates,
        reverse=True,
    )

    for i in range(
        len(trading_dates) - 1
    ):

        current_date = trading_dates[i]
        previous_date = trading_dates[i + 1]

        # ----------------------------------------------------
        # Price ratio:
        #
        # G_i,t = P_i,t / P_i,t-1
        # ----------------------------------------------------

        current_prices = (
            price_table.loc[
                current_date
            ]
        )

        previous_prices = (
            price_table.loc[
                previous_date
            ]
        )

        price_growth = (
            current_prices
            / previous_prices
        )

        # ----------------------------------------------------
        # Reverse the weights.
        # ----------------------------------------------------

        reverse_unscaled = (
            current_weights
            / price_growth
        )

        denominator = (
            reverse_unscaled
            .sum()
        )

        previous_weights = (
            reverse_unscaled
            / denominator
            * 100.0
        )

        current_weights = (
            previous_weights
        )

        records.append(
            {
                "date": previous_date,
                **current_weights.to_dict(),
            }
        )

        # Stop once we reach our starting anchor.
        if previous_date <= START_ANCHOR:
            break

    # --------------------------------------------------------
    # Convert wide format to long format.
    # --------------------------------------------------------

    reconstructed = pd.DataFrame(
        records
    )

    reconstructed = (
        reconstructed
        .sort_values("date")
        .reset_index(drop=True)
    )

    reconstructed = (
        reconstructed
        .melt(
            id_vars="date",
            var_name="symbol",
            value_name="reconstructed_weightage_pct",
        )
    )

    return reconstructed


# ============================================================
# VALIDATE ENDPOINT
# ============================================================

def validate_endpoint(
    reconstructed: pd.DataFrame,
    official_weights: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compare reconstructed starting-anchor weights
    against the official NSE weights.
    """

    reconstructed_start = reconstructed.loc[
        reconstructed["date"] == START_ANCHOR
    ].copy()

    if reconstructed_start.empty:
        raise ValueError(
            f"No reconstructed weights found for "
            f"{START_ANCHOR.date()}."
        )

    official = official_weights[
        [
            "symbol",
            "weightage_pct",
        ]
    ].rename(
        columns={
            "weightage_pct":
                "official_weightage_pct"
        }
    )

    result = reconstructed_start.merge(
        official,
        on="symbol",
        how="outer",
        indicator=True,
    )

    if not (
        result["_merge"] == "both"
    ).all():

        mismatches = result.loc[
            result["_merge"] != "both",
            "symbol",
        ].tolist()

        raise ValueError(
            "Constituent mismatch at validation "
            f"anchor: {mismatches}"
        )

    result = result.drop(
        columns="_merge"
    )

    result["error_pct_points"] = (
        result["reconstructed_weightage_pct"]
        - result["official_weightage_pct"]
    )

    result["absolute_error"] = (
        result["error_pct_points"]
        .abs()
    )

    return result


# ============================================================
# SUMMARY
# ============================================================

def print_summary(
    validation: pd.DataFrame,
    reconstructed: pd.DataFrame,
) -> None:
    """Print validation results."""

    errors = validation[
        "absolute_error"
    ]

    mae = errors.mean()

    rmse = (
        (
            validation[
                "error_pct_points"
            ]
            ** 2
        ).mean()
        ** 0.5
    )

    max_error = errors.max()

    correlation = validation[
        [
            "reconstructed_weightage_pct",
            "official_weightage_pct",
        ]
    ].corr().iloc[0, 1]

    reconstructed_sum = (
        validation[
            "reconstructed_weightage_pct"
        ].sum()
    )

    official_sum = (
        validation[
            "official_weightage_pct"
        ].sum()
    )

    number_of_days = (
        reconstructed["date"]
        .nunique()
    )

    print()
    print("=" * 75)
    print("DAILY WEIGHT RECONSTRUCTION VALIDATION")
    print("=" * 75)

    print(
        f"Known anchor:       {END_ANCHOR.date()}"
    )

    print(
        f"Validation anchor:  {START_ANCHOR.date()}"
    )

    print(
        f"Trading days:       {number_of_days}"
    )

    print(
        f"Constituents:       {len(validation)}"
    )

    print()
    print(
        f"Official weight sum:      "
        f"{official_sum:.6f}%"
    )

    print(
        f"Reconstructed weight sum: "
        f"{reconstructed_sum:.6f}%"
    )

    print()
    print(
        f"MAE:                      "
        f"{mae:.8f} percentage points"
    )

    print(
        f"RMSE:                     "
        f"{rmse:.8f} percentage points"
    )

    print(
        f"Maximum absolute error:   "
        f"{max_error:.8f} percentage points"
    )

    print(
        f"Correlation:              "
        f"{correlation:.10f}"
    )

    print()
    print("-" * 75)
    print("CONSTITUENT-LEVEL VALIDATION")
    print("-" * 75)

    display_columns = [
        "symbol",
        "official_weightage_pct",
        "reconstructed_weightage_pct",
        "error_pct_points",
        "absolute_error",
    ]

    print(
        validation
        .sort_values(
            "absolute_error",
            ascending=False,
        )[display_columns]
        .to_string(
            index=False
        )
    )


# ============================================================
# SAVE OUTPUTS
# ============================================================

def save_outputs(
    reconstructed: pd.DataFrame,
    validation: pd.DataFrame,
) -> None:
    """Save reconstructed daily weights and endpoint validation."""

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    reconstructed = (
        reconstructed
        .sort_values(
            [
                "date",
                "symbol",
            ]
        )
        .reset_index(drop=True)
    )

    reconstructed.to_csv(
        DAILY_WEIGHTS_FILE,
        index=False,
    )

    validation.to_csv(
        VALIDATION_FILE,
        index=False,
    )

    print()
    print(
        f"Daily reconstructed weights saved to:"
    )

    print(
        DAILY_WEIGHTS_FILE
    )

    print()
    print(
        f"Endpoint validation saved to:"
    )

    print(
        VALIDATION_FILE
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print(
        "Loading raw datasets..."
    )

    weights, stocks = load_data()

    # --------------------------------------------------------
    # Official anchor weights
    # --------------------------------------------------------

    end_weights = get_official_weights(
        weights,
        END_ANCHOR,
    )

    start_weights = get_official_weights(
        weights,
        START_ANCHOR,
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # The raw stock dataset may contain historical banks
    # that are NOT current NIFTY Bank constituents.
    #
    # We use ONLY the constituents present at the
    # reconstruction anchor.
    # --------------------------------------------------------

    end_symbols = set(
        end_weights["symbol"]
    )

    start_symbols = set(
        start_weights["symbol"]
    )

    if end_symbols != start_symbols:

        added = sorted(
            end_symbols
            - start_symbols
        )

        removed = sorted(
            start_symbols
            - end_symbols
        )

        raise ValueError(
            "The NIFTY Bank constituent universe changed "
            "between the two anchors.\n"
            f"Added: {added}\n"
            f"Removed: {removed}\n\n"
            "This first reconstruction experiment assumes "
            "a constant constituent universe."
        )

    symbols = end_symbols

    print()
    print(
        f"Active NIFTY Bank constituents: "
        f"{len(symbols)}"
    )

    print(
        f"Historical stock universe: "
        f"{stocks['symbol'].nunique()}"
    )

    # --------------------------------------------------------
    # Prices
    # --------------------------------------------------------

    prices = get_prices(
        stocks,
        START_ANCHOR,
        END_ANCHOR,
        symbols,
    )

    validate_price_coverage(
        prices,
        symbols,
    )

    print(
        f"Trading dates available: "
        f"{prices['date'].nunique()}"
    )

    # --------------------------------------------------------
    # Reconstruct
    # --------------------------------------------------------

    reconstructed = reconstruct_backward(
        end_weights,
        prices,
    )

    # --------------------------------------------------------
    # Validate against official July weights
    # --------------------------------------------------------

    validation = validate_endpoint(
        reconstructed,
        start_weights,
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print_summary(
        validation,
        reconstructed,
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    save_outputs(
        reconstructed,
        validation,
    )


if __name__ == "__main__":
    main()