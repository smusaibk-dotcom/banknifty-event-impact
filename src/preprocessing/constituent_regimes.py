from __future__ import annotations

from pathlib import Path

import pandas as pd


# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

WEIGHT_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "index_weightage"
    / "constituent_weights_raw.csv"
)

EVENT_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "index_weightage"
    / "constituent_change_events.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "index_weightage"
)

REGIME_OUTPUT_FILE = OUTPUT_DIR / "constituent_regimes.csv"
REGIME_MEMBERS_OUTPUT_FILE = (
    OUTPUT_DIR / "constituent_regime_members.csv"
)


# ============================================================
# Load
# ============================================================

def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load official weight observations and known constituent events."""

    weights = pd.read_csv(WEIGHT_FILE)
    events = pd.read_csv(EVENT_FILE)

    weights["date"] = pd.to_datetime(weights["date"])
    events["effective_date"] = pd.to_datetime(
        events["effective_date"]
    )

    return weights, events


# ============================================================
# Validate
# ============================================================

def validate_inputs(
    weights: pd.DataFrame,
    events: pd.DataFrame,
) -> None:
    """Validate the minimum required input columns."""

    required_weight_columns = {
        "date",
        "symbol",
    }

    required_event_columns = {
        "effective_date",
        "event_type",
        "symbol",
    }

    missing_weights = (
        required_weight_columns - set(weights.columns)
    )

    missing_events = (
        required_event_columns - set(events.columns)
    )

    if missing_weights:
        raise ValueError(
            "Missing columns in weight file: "
            f"{sorted(missing_weights)}"
        )

    if missing_events:
        raise ValueError(
            "Missing columns in event file: "
            f"{sorted(missing_events)}"
        )


# ============================================================
# Build official constituent snapshots
# ============================================================

def build_official_snapshots(
    weights: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build the official constituent universe observed at each
    month-end weight snapshot.
    """

    snapshots = (
        weights[["date", "symbol"]]
        .drop_duplicates()
        .sort_values(["date", "symbol"])
        .reset_index(drop=True)
    )

    return snapshots


# ============================================================
# Detect constituent changes
# ============================================================

def detect_constituent_changes(
    snapshots: pd.DataFrame,
) -> pd.DataFrame:
    """
    Detect changes in constituent membership between consecutive
    official snapshots.
    """

    snapshot_dates = (
        snapshots["date"]
        .drop_duplicates()
        .sort_values()
        .tolist()
    )

    records: list[dict] = []

    previous_symbols: set[str] | None = None

    for date in snapshot_dates:
        current_symbols = set(
            snapshots.loc[
                snapshots["date"] == date,
                "symbol",
            ]
        )

        if previous_symbols is None:
            previous_symbols = current_symbols
            continue

        added = sorted(
            current_symbols - previous_symbols
        )

        removed = sorted(
            previous_symbols - current_symbols
        )

        if added or removed:
            records.append(
                {
                    "snapshot_date": date,
                    "added": ",".join(added),
                    "removed": ",".join(removed),
                    "previous_count": len(previous_symbols),
                    "current_count": len(current_symbols),
                }
            )

        previous_symbols = current_symbols

    return pd.DataFrame(records)


# ============================================================
# Verify supplied constituent events
# ============================================================

def verify_events_against_snapshots(
    events: pd.DataFrame,
    snapshots: pd.DataFrame,
) -> None:
    """
    Verify that manually supplied constituent events agree with
    the first official snapshot on or after the event date.
    """

    print("\nVerifying supplied constituent events...")

    for _, event in events.sort_values(
        "effective_date"
    ).iterrows():

        effective_date = event["effective_date"]
        symbol = event["symbol"]
        event_type = event["event_type"]

        future_dates = (
            snapshots.loc[
                snapshots["date"] >= effective_date,
                "date",
            ]
            .drop_duplicates()
            .sort_values()
        )

        if future_dates.empty:
            raise ValueError(
                f"No official snapshot found on/after "
                f"{effective_date.date()} for {symbol}."
            )

        verification_date = future_dates.iloc[0]

        symbols = set(
            snapshots.loc[
                snapshots["date"] == verification_date,
                "symbol",
            ]
        )

        if event_type == "INCLUSION":
            if symbol not in symbols:
                raise ValueError(
                    f"Expected {symbol} to be present on "
                    f"{verification_date.date()}, but it is absent."
                )

        elif event_type == "EXCLUSION":
            if symbol in symbols:
                raise ValueError(
                    f"Expected {symbol} to be absent on "
                    f"{verification_date.date()}, but it is present."
                )

        else:
            raise ValueError(
                f"Unknown event type: {event_type}"
            )

        print(
            f"  VERIFIED: {effective_date.date()} | "
            f"{event_type:9s} | {symbol}"
        )


# ============================================================
# Build stable constituent regimes
# ============================================================

def build_regimes(
    snapshots: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build one regime whenever the constituent universe changes.

    A regime represents one stable constituent universe.
    """

    snapshot_dates = (
        snapshots["date"]
        .drop_duplicates()
        .sort_values()
        .tolist()
    )

    regimes: list[dict] = []
    members: list[dict] = []

    previous_symbols: set[str] | None = None
    regime_number = 0

    for snapshot_date in snapshot_dates:

        current_symbols = set(
            snapshots.loc[
                snapshots["date"] == snapshot_date,
                "symbol",
            ]
        )

        universe_changed = (
            previous_symbols is None
            or current_symbols != previous_symbols
        )

        if universe_changed:
            regime_number += 1
            regime_id = f"R{regime_number}"

            symbols = sorted(current_symbols)

            regimes.append(
                {
                    "regime_id": regime_id,
                    "start_snapshot_date": snapshot_date,
                    "constituent_count": len(symbols),
                }
            )

            for symbol in symbols:
                members.append(
                    {
                        "regime_id": regime_id,
                        "start_snapshot_date": snapshot_date,
                        "symbol": symbol,
                    }
                )

        previous_symbols = current_symbols

    regimes_df = pd.DataFrame(regimes)
    members_df = pd.DataFrame(members)

    # --------------------------------------------------------
    # Determine the final official snapshot belonging to each
    # regime.
    # --------------------------------------------------------

    regime_start_dates = (
        regimes_df["start_snapshot_date"]
        .tolist()
    )

    regime_end_dates: list[pd.Timestamp] = []

    for i, start_date in enumerate(regime_start_dates):

        if i < len(regime_start_dates) - 1:
            next_start_date = regime_start_dates[i + 1]

            previous_snapshot_dates = [
                date
                for date in snapshot_dates
                if date < next_start_date
            ]

            regime_end_dates.append(
                previous_snapshot_dates[-1]
            )

        else:
            regime_end_dates.append(
                snapshot_dates[-1]
            )

    regimes_df["end_snapshot_date"] = regime_end_dates

    # Keep a clean, predictable column order.
    regimes_df = regimes_df[
        [
            "regime_id",
            "start_snapshot_date",
            "end_snapshot_date",
            "constituent_count",
        ]
    ]

    members_df = members_df[
        [
            "regime_id",
            "start_snapshot_date",
            "symbol",
        ]
    ]

    return regimes_df, members_df


# ============================================================
# Validate regime output
# ============================================================

def validate_regimes(
    regimes: pd.DataFrame,
    members: pd.DataFrame,
) -> None:
    """Validate the structural regime output."""

    if regimes.empty:
        raise ValueError("No constituent regimes were created.")

    if regimes["regime_id"].duplicated().any():
        raise ValueError(
            "Duplicate regime IDs detected."
        )

    if (
        regimes["start_snapshot_date"]
        > regimes["end_snapshot_date"]
    ).any():
        raise ValueError(
            "A regime has a start date after its end date."
        )

    member_counts = (
        members.groupby("regime_id")["symbol"]
        .nunique()
    )

    expected_counts = (
        regimes.set_index("regime_id")["constituent_count"]
    )

    if not member_counts.equals(expected_counts):
        raise ValueError(
            "Regime constituent counts do not match "
            "the regime member table."
        )


# ============================================================
# Main
# ============================================================

def main() -> None:

    print("=" * 70)
    print("NIFTY BANK CONSTITUENT REGIME BUILDER")
    print("=" * 70)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # 1. Load
    # --------------------------------------------------------

    print("\n[1/5] Loading inputs...")

    weights, events = load_inputs()

    validate_inputs(
        weights,
        events,
    )

    # --------------------------------------------------------
    # 2. Build official snapshots
    # --------------------------------------------------------

    print(
        "\n[2/5] Building official constituent snapshots..."
    )

    snapshots = build_official_snapshots(weights)

    print(
        f"Official snapshots: "
        f"{snapshots['date'].nunique()}"
    )

    # --------------------------------------------------------
    # 3. Detect constituent changes
    # --------------------------------------------------------

    print(
        "\n[3/5] Detecting constituent changes..."
    )

    detected_changes = detect_constituent_changes(
        snapshots
    )

    if detected_changes.empty:
        print("No constituent changes detected.")
    else:
        print("\nDetected changes:")
        print(
            detected_changes.to_string(
                index=False
            )
        )

    # --------------------------------------------------------
    # 4. Verify supplied events
    # --------------------------------------------------------

    print(
        "\n[4/5] Verifying supplied events..."
    )

    verify_events_against_snapshots(
        events,
        snapshots,
    )

    # --------------------------------------------------------
    # 5. Build regimes
    # --------------------------------------------------------

    print(
        "\n[5/5] Building constituent regimes..."
    )

    regimes, members = build_regimes(
        snapshots
    )

    validate_regimes(
        regimes,
        members,
    )

    regimes.to_csv(
        REGIME_OUTPUT_FILE,
        index=False,
    )

    members.to_csv(
        REGIME_MEMBERS_OUTPUT_FILE,
        index=False,
    )

    # --------------------------------------------------------
    # Report
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("REGIME BUILD COMPLETE")
    print("=" * 70)

    print("\nRegimes:")
    print(
        regimes.to_string(
            index=False
        )
    )

    print("\nRegime members:")
    print(
        members.to_string(
            index=False
        )
    )

    print("\nSaved:")
    print(REGIME_OUTPUT_FILE)
    print(REGIME_MEMBERS_OUTPUT_FILE)


if __name__ == "__main__":
    main()