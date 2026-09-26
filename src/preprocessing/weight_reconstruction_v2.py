from pathlib import Path

import pandas as pd


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

STOCK_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "constituent_stocks_data(2).csv"
)

REGIME_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "constituent_regimes(3).csv"
)

REGIME_MEMBERS_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "constituent_regime_members(1).csv"
)

OFFICIAL_WEIGHT_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "index_weightage"
    / "constituent_weights_raw.csv"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "daily_weight_reconstruction.csv"
)


# ============================================================
# CONFIGURATION
# ============================================================

START_DATE = pd.Timestamp("2023-01-02")
END_DATE = pd.Timestamp("2026-08-31")


# ============================================================
# LOAD DATA
# ============================================================

def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:

    stocks = pd.read_csv(STOCK_FILE)
    regimes = pd.read_csv(REGIME_FILE)
    members = pd.read_csv(REGIME_MEMBERS_FILE)
    official = pd.read_csv(OFFICIAL_WEIGHT_FILE)

    stocks["date"] = pd.to_datetime(stocks["date"])
    regimes["regime_start"] = pd.to_datetime(regimes["regime_start"])
    regimes["regime_end"] = pd.to_datetime(regimes["regime_end"])
    members["start_snapshot_date"] = pd.to_datetime(
        members["start_snapshot_date"]
    )
    members["end_snapshot_date"] = pd.to_datetime(
        members["end_snapshot_date"]
    )
    official["date"] = pd.to_datetime(official["date"])

    stocks["symbol"] = stocks["symbol"].astype(str).str.strip()
    regimes["regime_id"] = regimes["regime_id"].astype(str).str.strip()
    members["symbol"] = members["symbol"].astype(str).str.strip()
    official["symbol"] = official["symbol"].astype(str).str.strip()

    return stocks, regimes, members, official


# ============================================================
# VALIDATE INPUTS
# ============================================================

def validate_inputs(
    stocks: pd.DataFrame,
    regimes: pd.DataFrame,
    members: pd.DataFrame,
    official: pd.DataFrame,
) -> None:

    required_stock_columns = {
        "date",
        "symbol",
        "close",
    }

    required_regime_columns = {
        "regime_id",
        "regime_start",
        "regime_end",
    }

    required_member_columns = {
        "regime_id",
        "symbol",
        "start_snapshot_date",
        "end_snapshot_date",
    }

    required_weight_columns = {
        "date",
        "symbol",
        "weightage_pct",
    }

    missing = required_stock_columns - set(stocks.columns)
    if missing:
        raise ValueError(f"Missing stock columns: {sorted(missing)}")

    missing = required_regime_columns - set(regimes.columns)
    if missing:
        raise ValueError(f"Missing regime columns: {sorted(missing)}")

    missing = required_member_columns - set(members.columns)
    if missing:
        raise ValueError(f"Missing member columns: {sorted(missing)}")

    missing = required_weight_columns - set(official.columns)
    if missing:
        raise ValueError(f"Missing official-weight columns: {sorted(missing)}")

    if stocks["date"].min() > START_DATE:
        raise ValueError("Stock data does not cover the required start date.")

    if stocks["date"].max() < END_DATE:
        raise ValueError("Stock data does not cover the required end date.")

    if stocks.duplicated(["date", "symbol"]).any():
        raise ValueError("Duplicate date + symbol rows found in stock data.")

    if official.duplicated(["date", "symbol"]).any():
        raise ValueError(
            "Duplicate date + symbol rows found in official weights."
        )

    if members.duplicated(["regime_id", "symbol"]).any():
        raise ValueError(
            "Duplicate regime_id + symbol rows found in regime membership."
        )


# ============================================================
# PRICE MATRIX
# ============================================================

def prepare_prices(
    stocks: pd.DataFrame,
    symbols: list[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:

    data = stocks[
        stocks["symbol"].isin(symbols)
        & stocks["date"].between(start_date, end_date)
    ].copy()

    prices = data.pivot(
        index="date",
        columns="symbol",
        values="close",
    )

    prices = prices.sort_index()

    missing_symbols = sorted(set(symbols) - set(prices.columns))

    if missing_symbols:
        raise ValueError(
            f"Missing stock-price symbols: {missing_symbols}"
        )

    prices = prices[symbols]

    if prices.isna().any().any():
        missing = prices.isna().sum()
        missing = missing[missing > 0]

        raise ValueError(
            f"Missing closing prices found:\n{missing}"
        )

    return prices


# ============================================================
# BACKWARD RECONSTRUCTION
# ============================================================

def reconstruct_from_anchor(
    prices: pd.DataFrame,
    anchor_weights: pd.Series,
    anchor_date: pd.Timestamp,
    start_date: pd.Timestamp,
) -> pd.DataFrame:

    dates = prices.loc[
        start_date:anchor_date
    ].index.sort_values()

    if anchor_date not in dates:
        raise ValueError(
            f"Anchor date {anchor_date.date()} missing from price data."
        )

    current_weights = anchor_weights.copy()

    results = []

    # Official anchor
    results.append(
        pd.DataFrame(
            {
                "date": anchor_date,
                "symbol": current_weights.index,
                "weight": current_weights.values,
                "weight_source": "OFFICIAL",
            }
        )
    )

    # Work backwards from the official anchor
    for i in range(len(dates) - 1, 0, -1):

        current_date = dates[i]
        previous_date = dates[i - 1]

        current_prices = prices.loc[current_date]
        previous_prices = prices.loc[previous_date]

        price_ratio = current_prices / previous_prices

        previous_unnormalized = current_weights / price_ratio

        previous_weights = (
            previous_unnormalized
            / previous_unnormalized.sum()
            * 100
        )

        results.append(
            pd.DataFrame(
                {
                    "date": previous_date,
                    "symbol": previous_weights.index,
                    "weight": previous_weights.values,
                    "weight_source": "RECONSTRUCTED",
                }
            )
        )

        current_weights = previous_weights

    result = pd.concat(
        results,
        ignore_index=True,
    )

    return result


# ============================================================
# OFFICIAL WEIGHT LOOKUP
# ============================================================

def get_official_weights(
    official: pd.DataFrame,
    anchor_date: pd.Timestamp,
    symbols: list[str],
) -> pd.Series:

    data = official[
        (official["date"] == anchor_date)
        & official["symbol"].isin(symbols)
    ].copy()

    if data.empty:
        raise ValueError(
            f"No official weights found for {anchor_date.date()}."
        )

    if set(data["symbol"]) != set(symbols):
        missing = sorted(set(symbols) - set(data["symbol"]))
        extra = sorted(set(data["symbol"]) - set(symbols))

        raise ValueError(
            f"Official universe mismatch on {anchor_date.date()}. "
            f"Missing={missing}, Extra={extra}"
        )

    weights = data.set_index("symbol")["weightage_pct"]

    return weights[symbols]


# ============================================================
# REGIME RECONSTRUCTION
# ============================================================

def reconstruct_regime(
    regime_id: str,
    regime_start: pd.Timestamp,
    regime_end: pd.Timestamp,
    members: pd.DataFrame,
    stocks: pd.DataFrame,
    official: pd.DataFrame,
) -> list[pd.DataFrame]:

    regime_symbols = (
        members.loc[
            members["regime_id"] == regime_id,
            "symbol",
        ]
        .drop_duplicates()
        .tolist()
    )

    if not regime_symbols:
        raise ValueError(
            f"No members found for regime {regime_id}."
        )

    regime_official = official[
        (official["date"] >= regime_start)
        & (official["date"] <= regime_end)
        & official["symbol"].isin(regime_symbols)
    ].copy()

    anchor_dates = sorted(
        regime_official["date"].unique()
    )

    if not anchor_dates:
        raise ValueError(
            f"No official weight anchors found for {regime_id}."
        )

    outputs = []

    # --------------------------------------------------------
    # Stable intervals between official anchors
    # --------------------------------------------------------

    for i in range(1, len(anchor_dates)):

        previous_anchor = pd.Timestamp(anchor_dates[i - 1])
        current_anchor = pd.Timestamp(anchor_dates[i])

        prices = prepare_prices(
            stocks=stocks,
            symbols=regime_symbols,
            start_date=previous_anchor,
            end_date=current_anchor,
        )

        anchor_weights = get_official_weights(
            official=official,
            anchor_date=current_anchor,
            symbols=regime_symbols,
        )

        reconstructed = reconstruct_from_anchor(
            prices=prices,
            anchor_weights=anchor_weights,
            anchor_date=current_anchor,
            start_date=previous_anchor,
        )

        # Previous anchor will be supplied by the previous interval.
        reconstructed = reconstructed[
            reconstructed["date"] != previous_anchor
        ]

        outputs.append(reconstructed)

    # --------------------------------------------------------
    # Initial partial period
    #
    # Example:
    # 02-Jan-2023 → 31-Jan-2023
    # --------------------------------------------------------

    first_anchor = pd.Timestamp(anchor_dates[0])

    if regime_start < first_anchor:

        prices = prepare_prices(
            stocks=stocks,
            symbols=regime_symbols,
            start_date=regime_start,
            end_date=first_anchor,
        )

        anchor_weights = get_official_weights(
            official=official,
            anchor_date=first_anchor,
            symbols=regime_symbols,
        )

        reconstructed = reconstruct_from_anchor(
            prices=prices,
            anchor_weights=anchor_weights,
            anchor_date=first_anchor,
            start_date=regime_start,
        )

        reconstructed = reconstructed[
            reconstructed["date"] < first_anchor
        ]

        outputs.append(reconstructed)

    return outputs


# ============================================================
# BOUNDARY PERIODS
# ============================================================

def reconstruct_boundary_period(
    start_date: str,
    anchor_date: str,
    regime_id: str,
    members: pd.DataFrame,
    stocks: pd.DataFrame,
    official: pd.DataFrame,
) -> pd.DataFrame:

    start_date = pd.Timestamp(start_date)
    anchor_date = pd.Timestamp(anchor_date)

    symbols = (
        members.loc[
            members["regime_id"] == regime_id,
            "symbol",
        ]
        .drop_duplicates()
        .tolist()
    )

    prices = prepare_prices(
        stocks=stocks,
        symbols=symbols,
        start_date=start_date,
        end_date=anchor_date,
    )

    anchor_weights = get_official_weights(
        official=official,
        anchor_date=anchor_date,
        symbols=symbols,
    )

    result = reconstruct_from_anchor(
        prices=prices,
        anchor_weights=anchor_weights,
        anchor_date=anchor_date,
        start_date=start_date,
    )

    return result


# ============================================================
# FINAL VALIDATION
# ============================================================

def validate_output(
    result: pd.DataFrame,
    official: pd.DataFrame,
) -> None:

    if result.duplicated(["date", "symbol"]).any():
        raise ValueError(
            "Duplicate date + symbol rows in final reconstruction."
        )

    daily_sums = (
        result.groupby("date")["weight"]
        .sum()
    )

    if not (daily_sums.round(8) == 100).all():
        bad_dates = daily_sums[
            daily_sums.round(8) != 100
        ]

        raise ValueError(
            f"Weight totals are not 100% on:\n{bad_dates}"
        )

    # Check every official observation is preserved exactly.
    official_subset = official[
        official["date"].between(
            START_DATE,
            END_DATE,
        )
    ][
        ["date", "symbol", "weightage_pct"]
    ].copy()

    reconstructed_subset = result[
        result["weight_source"] == "OFFICIAL"
    ][
        ["date", "symbol", "weight"]
    ].copy()

    merged = official_subset.merge(
        reconstructed_subset,
        on=["date", "symbol"],
        how="left",
    )

    if merged["weight"].isna().any():
        raise ValueError(
            "Some official weight observations are missing "
            "from the reconstructed dataset."
        )

    if not (
        (merged["weight"] - merged["weightage_pct"])
        .abs()
        .lt(1e-10)
        .all()
    ):
        raise ValueError(
            "Official weights were altered."
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    stocks, regimes, members, official = load_data()

    validate_inputs(
        stocks=stocks,
        regimes=regimes,
        members=members,
        official=official,
    )

    all_results = []

    # --------------------------------------------------------
    # 1. Normal regime reconstruction
    # --------------------------------------------------------

    for _, regime in regimes.sort_values(
        "regime_start"
    ).iterrows():

        results = reconstruct_regime(
            regime_id=regime["regime_id"],
            regime_start=regime["regime_start"],
            regime_end=regime["regime_end"],
            members=members,
            stocks=stocks,
            official=official,
        )

        all_results.extend(results)

    # --------------------------------------------------------
    # 2. Transition / boundary periods
    # --------------------------------------------------------

    # January 2023
    all_results.append(
        reconstruct_boundary_period(
            start_date="2023-01-02",
            anchor_date="2023-01-31",
            regime_id="R1",
            members=members,
            stocks=stocks,
            official=official,
        )
    )

    # September 2024
    # R1 constituents are used before the R2 effective date.
    all_results.append(
        reconstruct_boundary_period(
            start_date="2024-09-02",
            anchor_date="2024-09-30",
            regime_id="R1",
            members=members,
            stocks=stocks,
            official=official,
        )
    )

    # December 2025
    # R2 constituents are used before the R3 effective date.
    all_results.append(
        reconstruct_boundary_period(
            start_date="2025-12-01",
            anchor_date="2025-12-31",
            regime_id="R2",
            members=members,
            stocks=stocks,
            official=official,
        )
    )

    # --------------------------------------------------------
    # 3. Combine
    # --------------------------------------------------------

    result = pd.concat(
        all_results,
        ignore_index=True,
    )

    result["date"] = pd.to_datetime(result["date"])

    result = result[
        result["date"].between(
            START_DATE,
            END_DATE,
        )
    ].copy()

    # Official observations always take precedence.
    result["source_priority"] = (
        result["weight_source"] == "OFFICIAL"
    ).astype(int)

    result = (
        result
        .sort_values(
            [
                "date",
                "symbol",
                "source_priority",
            ],
            ascending=[True, True, False],
        )
        .drop_duplicates(
            ["date", "symbol"],
            keep="first",
        )
        .drop(columns="source_priority")
        .sort_values(
            ["date", "symbol"]
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # 4. Final validation
    # --------------------------------------------------------

    validate_output(
        result=result,
        official=official,
    )

    # --------------------------------------------------------
    # 5. Save
    # --------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        OUTPUT_FILE,
        index=False,
        date_format="%Y-%m-%d",
    )

    print("Weight reconstruction complete.")
    print(f"Rows: {len(result):,}")
    print(
        f"Date range: "
        f"{result['date'].min().date()} → "
        f"{result['date'].max().date()}"
    )
    print(
        f"Symbols: "
        f"{result['symbol'].nunique()}"
    )
    print(
        f"Saved to: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()