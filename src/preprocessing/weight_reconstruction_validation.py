from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OFFICIAL_WEIGHTS_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "constituent_weights_raw.csv"
)

RECONSTRUCTED_WEIGHTS_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "daily_weight_reconstruction_new.csv"
)

REGIMES_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "constituent_regimes.csv"
)

REGIME_MEMBERS_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "constituent_regime_members.csv"
)

CONSTITUENT_OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "weight_reconstruction_validation_constituent.csv"
)

MONTHLY_OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "weight_reconstruction_validation_monthly.csv"
)


# ============================================================
# LOAD DATA
# ============================================================

def load_data():

    official = pd.read_csv(
        OFFICIAL_WEIGHTS_PATH
    )

    reconstructed = pd.read_csv(
        RECONSTRUCTED_WEIGHTS_PATH
    )

    regimes = pd.read_csv(
        REGIMES_PATH
    )

    regime_members = pd.read_csv(
        REGIME_MEMBERS_PATH
    )

    print("Loaded inputs")
    print(f"Official weights:      {len(official):,} rows")
    print(f"Reconstructed weights: {len(reconstructed):,} rows")
    print(f"Regimes:               {len(regimes):,}")
    print(f"Regime members:        {len(regime_members):,}")

    return (
        official,
        reconstructed,
        regimes,
        regime_members,
    )


# ============================================================
# NORMAL MONTH
# ============================================================

def validate_normal_month(
    month_end,
    previous_official_date,
    official,
    reconstructed,
):
    """
    Normal month:

        Current month official anchor
                    ↓
        backward reconstruction
                    ↓
        first reconstructed trading day
                    ↓
        compare against previous
        month's official snapshot
    """

    reconstructed_month = reconstructed[
        (
            reconstructed["date"] > previous_official_date
        )
        & (
            reconstructed["date"] < month_end
        )
        & (
            reconstructed["weight_source"]
            == "RECONSTRUCTED"
        )
    ]

    if reconstructed_month.empty:
        return []

    validation_date = (
        reconstructed_month["date"]
        .sort_values()
        .iloc[0]
    )

    reconstructed_weights = reconstructed[
        reconstructed["date"] == validation_date
    ][
        ["symbol", "weight"]
    ].copy()

    official_weights = official[
        official["date"] == previous_official_date
    ][
        ["symbol", "weightage_pct"]
    ].copy()

    comparison = official_weights.merge(
        reconstructed_weights,
        on="symbol",
        how="inner",
        validate="one_to_one",
    )

    comparison = comparison.rename(
        columns={
            "weightage_pct": "official_weight",
            "weight": "reconstructed_weight",
        }
    )

    comparison["deviation"] = (
        comparison["reconstructed_weight"]
        - comparison["official_weight"]
    )

    comparison["absolute_deviation"] = (
        comparison["deviation"].abs()
    )

    comparison["percentage_deviation"] = np.where(
        comparison["official_weight"] != 0,
        (
            comparison["deviation"]
            / comparison["official_weight"]
        )
        * 100,
        np.nan,
    )

    comparison["squared_error"] = (
        comparison["deviation"] ** 2
    )

    comparison["validation_type"] = "NORMAL"
    comparison["month_end"] = month_end
    comparison["reconstructed_date"] = validation_date
    comparison["official_comparison_date"] = (
        previous_official_date
    )

    return comparison[
        [
            "validation_type",
            "month_end",
            "reconstructed_date",
            "official_comparison_date",
            "symbol",
            "reconstructed_weight",
            "official_weight",
            "deviation",
            "absolute_deviation",
            "percentage_deviation",
            "squared_error",
        ]
    ].to_dict("records")


# ============================================================
# TRANSITION MONTH
# ============================================================

def validate_transition_month(
    transition_date,
    previous_official_date,
    current_regime_id,
    next_regime_id,
    official,
    reconstructed,
    regime_members,
):
    """
    Transition month:

        Previous regime official anchor
                    ↓
        forward reconstruction
                    ↓
        last reconstructed trading day
                    ↓
        compare against next regime
        official snapshot

    If new constituents enter the next regime:

        Their reconstructed weight is treated as zero.

        Their official weight is redistributed equally
        across the common constituents for comparison.
    """

    transition_reconstructed = reconstructed[
        (
            reconstructed["date"] > previous_official_date
        )
        & (
            reconstructed["date"] < transition_date
        )
        & (
            reconstructed["weight_source"]
            == "RECONSTRUCTED"
        )
    ]

    if transition_reconstructed.empty:
        return []

    validation_date = (
        transition_reconstructed["date"]
        .sort_values()
        .iloc[-1]
    )

    reconstructed_weights = reconstructed[
        reconstructed["date"] == validation_date
    ][
        ["symbol", "weight"]
    ].copy()

    current_members = set(
        regime_members[
            regime_members["regime_id"]
            == current_regime_id
        ]["symbol"]
    )

    next_members = set(
        regime_members[
            regime_members["regime_id"]
            == next_regime_id
        ]["symbol"]
    )

    new_constituents = (
        next_members - current_members
    )

    common_constituents = (
        current_members & next_members
    )

    official_weights = official[
        official["date"] == transition_date
    ][
        ["symbol", "weightage_pct"]
    ].copy()

    # --------------------------------------------------------
    # No constituent-universe change
    # --------------------------------------------------------

    if not new_constituents:

        comparison = official_weights.merge(
            reconstructed_weights,
            on="symbol",
            how="inner",
            validate="one_to_one",
        )

        comparison = comparison.rename(
            columns={
                "weightage_pct": "official_weight",
                "weight": "reconstructed_weight",
            }
        )

    # --------------------------------------------------------
    # New constituents entered
    # --------------------------------------------------------

    else:

        new_constituent_weight = official_weights[
            official_weights["symbol"].isin(
                new_constituents
            )
        ]["weightage_pct"].sum()

        redistribution = (
            new_constituent_weight
            / len(common_constituents)
        )

        official_common = official_weights[
            official_weights["symbol"].isin(
                common_constituents
            )
        ].copy()

        reconstructed_common = reconstructed_weights[
            reconstructed_weights["symbol"].isin(
                common_constituents
            )
        ].copy()

        comparison = official_common.merge(
            reconstructed_common,
            on="symbol",
            how="inner",
            validate="one_to_one",
        )

        comparison = comparison.rename(
            columns={
                "weightage_pct": "official_weight",
                "weight": "reconstructed_weight",
            }
        )

        comparison["official_weight"] = (
            comparison["official_weight"]
            - redistribution
        )

    # --------------------------------------------------------
    # Constituent-level deviation
    # --------------------------------------------------------

    comparison["deviation"] = (
        comparison["reconstructed_weight"]
        - comparison["official_weight"]
    )

    comparison["absolute_deviation"] = (
        comparison["deviation"].abs()
    )

    comparison["percentage_deviation"] = np.where(
        comparison["official_weight"] != 0,
        (
            comparison["deviation"]
            / comparison["official_weight"]
        )
        * 100,
        np.nan,
    )

    comparison["squared_error"] = (
        comparison["deviation"] ** 2
    )

    comparison["validation_type"] = "TRANSITION"
    comparison["month_end"] = transition_date
    comparison["reconstructed_date"] = validation_date
    comparison["official_comparison_date"] = (
        transition_date
    )

    return comparison[
        [
            "validation_type",
            "month_end",
            "reconstructed_date",
            "official_comparison_date",
            "symbol",
            "reconstructed_weight",
            "official_weight",
            "deviation",
            "absolute_deviation",
            "percentage_deviation",
            "squared_error",
        ]
    ].to_dict("records")


# ============================================================
# MONTHLY SUMMARY
# ============================================================

def create_monthly_summary(
    constituent_results,
):

    df = constituent_results.copy()

    summary_rows = []

    group_columns = [
        "validation_type",
        "month_end",
        "reconstructed_date",
        "official_comparison_date",
    ]

    for keys, group in df.groupby(
        group_columns,
        sort=True,
    ):

        deviations = group["deviation"]

        mse = (
            deviations ** 2
        ).mean()

        correlation = (
            group["reconstructed_weight"]
            .corr(group["official_weight"])
        )

        summary_rows.append(
            {
                "validation_type": keys[0],
                "month_end": keys[1],
                "reconstructed_date": keys[2],
                "official_comparison_date": keys[3],
                "mae": group[
                    "absolute_deviation"
                ].mean(),
                "mse": mse,
                "rmse": np.sqrt(mse),
                "max_absolute_error": group[
                    "absolute_deviation"
                ].max(),
                "mean_error": deviations.mean(),
                "correlation": correlation,
                "constituent_count": len(group),
            }
        )

    return pd.DataFrame(summary_rows)


# ============================================================
# MAIN
# ============================================================

def main():

    (
        official,
        reconstructed,
        regimes,
        regime_members,
    ) = load_data()

    official_dates = sorted(
        official["date"].unique()
    )

    transition_dates = set(
        regimes["start_snapshot_date"]
    )

    all_results = []

    # ========================================================
    # MONTHLY VALIDATION
    # ========================================================

    for i, month_end in enumerate(
        official_dates
    ):

        if i == 0:
            continue

        previous_official_date = (
            official_dates[i - 1]
        )

        # ----------------------------------------------------
        # TRANSITION MONTH
        # ----------------------------------------------------

        if month_end in transition_dates:

            next_regime_row = regimes[
                regimes["start_snapshot_date"]
                == month_end
            ]

            previous_regime_rows = regimes[
                regimes["start_snapshot_date"]
                < month_end
            ]

            if (
                next_regime_row.empty
                or previous_regime_rows.empty
            ):
                raise ValueError(
                    f"Could not identify regimes for "
                    f"transition date {month_end}."
                )

            next_regime_id = (
                next_regime_row.iloc[0]["regime_id"]
            )

            current_regime_id = (
                previous_regime_rows
                .sort_values(
                    "start_snapshot_date"
                )
                .iloc[-1]["regime_id"]
            )

            results = validate_transition_month(
                transition_date=month_end,
                previous_official_date=
                    previous_official_date,
                current_regime_id=
                    current_regime_id,
                next_regime_id=
                    next_regime_id,
                official=official,
                reconstructed=reconstructed,
                regime_members=regime_members,
            )

        # ----------------------------------------------------
        # NORMAL MONTH
        # ----------------------------------------------------

        else:

            results = validate_normal_month(
                month_end=month_end,
                previous_official_date=
                    previous_official_date,
                official=official,
                reconstructed=reconstructed,
            )

        all_results.extend(results)

    # ========================================================
    # CONSTITUENT-LEVEL DATASET
    # ========================================================

    constituent_results = pd.DataFrame(
        all_results
    )

    if constituent_results.empty:
        raise ValueError(
            "No constituent-level validation results "
            "were generated."
        )

    constituent_results = constituent_results.sort_values(
        [
            "month_end",
            "symbol",
        ]
    ).reset_index(drop=True)

    # ========================================================
    # MONTHLY SUMMARY
    # ========================================================

    monthly_summary = create_monthly_summary(
        constituent_results
    )

    # ========================================================
    # SAVE CONSTITUENT-LEVEL RESULTS
    # ========================================================

    constituent_results.to_csv(
        CONSTITUENT_OUTPUT_PATH,
        index=False,
    )

    # ========================================================
    # SAVE MONTHLY SUMMARY
    # ========================================================

    monthly_summary.to_csv(
        MONTHLY_OUTPUT_PATH,
        index=False,
    )

    # ========================================================
    # OUTPUT
    # ========================================================

    print("\n" + "=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)

    print(
        f"Validation months       : "
        f"{len(monthly_summary):,}"
    )

    print(
        f"Constituent-level rows  : "
        f"{len(constituent_results):,}"
    )

    print(
        f"Normal months           : "
        f"{(
            monthly_summary['validation_type']
            == 'NORMAL'
        ).sum():,}"
    )

    print(
        f"Transition months       : "
        f"{(
            monthly_summary['validation_type']
            == 'TRANSITION'
        ).sum():,}"
    )

    print("\nMonthly summary:")
    print(
        monthly_summary.to_string(
            index=False
        )
    )

    print("\nConstituent-level validation saved to:")
    print(CONSTITUENT_OUTPUT_PATH)

    print("\nMonthly summary saved to:")
    print(MONTHLY_OUTPUT_PATH)


if __name__ == "__main__":
    main()