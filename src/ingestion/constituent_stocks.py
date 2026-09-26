from __future__ import annotations

import io
import time
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests


# ---------------------------------------------------------------------
# PROJECT PATHS
# ---------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_FILE = RAW_DIR / "constituent_stocks_raw.csv"

RAW_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------
# STUDY PERIOD
# ---------------------------------------------------------------------

START_DATE = date(2023, 1, 1)
END_DATE = date(2026, 8, 31)


# ---------------------------------------------------------------------
# HISTORICAL NIFTY BANK STOCK UNIVERSE
#
# We intentionally use the SUPerset of all relevant constituents during
# the study period. Historical membership will be handled separately.
# ---------------------------------------------------------------------

SYMBOLS = {
    "AUBANK",
    "AXISBANK",
    "BANKBARODA",
    "BANDHANBNK",
    "CANBK",
    "FEDERALBNK",
    "HDFCBANK",
    "ICICIBANK",
    "IDFCFIRSTB",
    "INDUSINDBK",
    "KOTAKBANK",
    "PNB",
    "SBIN",
    "UNIONBANK",
    "YESBANK",
}


# ---------------------------------------------------------------------
# NSE SOURCE TRANSITION
#
# Legacy Bhavcopy:
#   before 08-Jul-2024
#
# UDiFF Common Bhavcopy:
#   from 08-Jul-2024 onward
# ---------------------------------------------------------------------

NSE_UDIFF_CUTOFF = date(2024, 7, 8)


# Legacy source
LEGACY_URL = (
    "https://archives.nseindia.com/"
    "content/historical/EQUITIES/"
    "{year}/{month}/"
    "cm{day}{month}{year}bhav.csv.zip"
)

# Current UDiFF source
UDIFF_URL = (
    "https://nsearchives.nseindia.com/"
    "content/cm/"
    "BhavCopy_NSE_CM_0_0_0_{yyyymmdd}_F_0000.csv.zip"
)


# ---------------------------------------------------------------------
# HTTP CONFIGURATION
# ---------------------------------------------------------------------

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0 Safari/537.36"
)

REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
CHECKPOINT_EVERY = 25


# ---------------------------------------------------------------------
# HTTP SESSION
# ---------------------------------------------------------------------

def create_session() -> requests.Session:
    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
    )

    return session


# ---------------------------------------------------------------------
# DATE HELPERS
# ---------------------------------------------------------------------

def daterange(start: date, end: date):
    current = start

    while current <= end:
        yield current
        current += timedelta(days=1)


# ---------------------------------------------------------------------
# URL BUILDERS
# ---------------------------------------------------------------------

def build_legacy_url(day: date) -> str:
    month = day.strftime("%b").upper()

    return LEGACY_URL.format(
        year=day.year,
        month=month,
        day=f"{day.day:02d}",
    )


def build_udiff_url(day: date) -> str:
    return UDIFF_URL.format(
        yyyymmdd=day.strftime("%Y%m%d")
    )


# ---------------------------------------------------------------------
# DOWNLOAD
# ---------------------------------------------------------------------

def download_file(
    session: requests.Session,
    url: str,
) -> bytes | None:

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            response = session.get(
                url,
                timeout=REQUEST_TIMEOUT,
            )

            # NSE uses 404 for dates without a report
            # (weekends/holidays).
            if response.status_code == 404:
                return None

            response.raise_for_status()

            return response.content

        except requests.RequestException as exc:

            if attempt == MAX_RETRIES:
                print(
                    f"  ERROR: failed after {MAX_RETRIES} attempts: "
                    f"{url}"
                )
                print(f"  {exc}")
                return None

            wait_seconds = 2 ** (attempt - 1)

            print(
                f"  Retry {attempt}/{MAX_RETRIES} "
                f"after error: {exc}"
            )

            time.sleep(wait_seconds)

    return None


# ---------------------------------------------------------------------
# LEGACY BHAVCOPY PARSER
# ---------------------------------------------------------------------

def parse_legacy_bhavcopy(
    content: bytes,
    trading_date: date,
) -> pd.DataFrame:

    with zipfile.ZipFile(io.BytesIO(content)) as archive:

        csv_files = [
            name
            for name in archive.namelist()
            if name.lower().endswith(".csv")
        ]

        if not csv_files:
            raise ValueError(
                "No CSV file found inside legacy Bhavcopy ZIP."
            )

        with archive.open(csv_files[0]) as file:
            df = pd.read_csv(file)

    # Legacy NSE column names.
    required_columns = {
        "SYMBOL",
        "SERIES",
        "OPEN",
        "HIGH",
        "LOW",
        "CLOSE",
        "TOTTRDQTY",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            f"Legacy Bhavcopy missing columns: {missing}"
        )

    df = df[
        (df["SERIES"] == "EQ")
        & (df["SYMBOL"].isin(SYMBOLS))
    ].copy()

    if df.empty:
        return pd.DataFrame()

    df["date"] = pd.to_datetime(trading_date)

    df = df.rename(
        columns={
            "SYMBOL": "symbol",
            "OPEN": "open",
            "HIGH": "high",
            "LOW": "low",
            "CLOSE": "close",
            "TOTTRDQTY": "volume",
        }
    )

    return df[
        [
            "date",
            "symbol",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    ]


# ---------------------------------------------------------------------
# UDIFF BHAVCOPY PARSER
# ---------------------------------------------------------------------

def parse_udiff_bhavcopy(
    content: bytes,
) -> pd.DataFrame:

    with zipfile.ZipFile(io.BytesIO(content)) as archive:

        csv_files = [
            name
            for name in archive.namelist()
            if name.lower().endswith(".csv")
        ]

        if not csv_files:
            raise ValueError(
                "No CSV file found inside UDiFF Bhavcopy ZIP."
            )

        with archive.open(csv_files[0]) as file:
            df = pd.read_csv(file)

    required_columns = {
        "TradDt",
        "TckrSymb",
        "SctySrs",
        "OpnPric",
        "HghPric",
        "LwPric",
        "ClsPric",
        "TtlTradgVol",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            f"UDiFF Bhavcopy missing columns: {missing}"
        )

    df = df[
        (df["SctySrs"] == "EQ")
        & (df["TckrSymb"].isin(SYMBOLS))
    ].copy()

    if df.empty:
        return pd.DataFrame()

    df["date"] = pd.to_datetime(df["TradDt"])

    df = df.rename(
        columns={
            "TckrSymb": "symbol",
            "OpnPric": "open",
            "HghPric": "high",
            "LwPric": "low",
            "ClsPric": "close",
            "TtlTradgVol": "volume",
        }
    )

    return df[
        [
            "date",
            "symbol",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    ]


# ---------------------------------------------------------------------
# FETCH ONE DATE
# ---------------------------------------------------------------------

def fetch_date(
    session: requests.Session,
    trading_date: date,
) -> pd.DataFrame:

    if trading_date < NSE_UDIFF_CUTOFF:
        url = build_legacy_url(trading_date)

        content = download_file(
            session,
            url,
        )

        if content is None:
            return pd.DataFrame()

        return parse_legacy_bhavcopy(
            content,
            trading_date,
        )

    url = build_udiff_url(trading_date)

    content = download_file(
        session,
        url,
    )

    if content is None:
        return pd.DataFrame()

    return parse_udiff_bhavcopy(content)


# ---------------------------------------------------------------------
# LOAD EXISTING DATA
# ---------------------------------------------------------------------

def load_existing_data() -> pd.DataFrame:

    if not OUTPUT_FILE.exists():
        return pd.DataFrame(
            columns=[
                "date",
                "symbol",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        )

    df = pd.read_csv(
        OUTPUT_FILE,
        parse_dates=["date"],
    )

    return df


# ---------------------------------------------------------------------
# SAVE CHECKPOINT
# ---------------------------------------------------------------------

def save_data(df: pd.DataFrame) -> None:

    df = (
        df.drop_duplicates(
            subset=["date", "symbol"],
            keep="last",
        )
        .sort_values(
            ["date", "symbol"]
        )
        .reset_index(drop=True)
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False,
    )


# ---------------------------------------------------------------------
# MAIN INGESTION
# ---------------------------------------------------------------------

def main() -> None:

    print("=" * 70)
    print("NIFTY BANK CONSTITUENT STOCK DATA INGESTION")
    print("=" * 70)

    print(f"Study period : {START_DATE} → {END_DATE}")
    print(f"Stock universe: {len(SYMBOLS)} symbols")
    print(f"Output       : {OUTPUT_FILE}")
    print()

    existing = load_existing_data()

    if not existing.empty:

        existing_dates = set(
            existing["date"].dt.date
        )

        print(
            f"Existing rows : {len(existing):,}"
        )

        print(
            f"Existing dates: {len(existing_dates):,}"
        )

    else:

        existing_dates = set()

        print("No existing dataset found.")

    # -------------------------------------------------------------
    # IMPORTANT:
    #
    # We fetch by DATE, not by STOCK.
    #
    # Each NSE Bhavcopy contains the entire market.
    # Therefore one request gives us all 15 target stocks.
    # -------------------------------------------------------------

    target_dates = [
        d
        for d in daterange(
            START_DATE,
            END_DATE,
        )
        if d not in existing_dates
    ]

    print(
        f"Dates requiring acquisition: "
        f"{len(target_dates):,}"
    )

    if not target_dates:

        print("\nNothing to acquire.")
        print("Dataset is already up to date.")
        return

    session = create_session()

    new_frames: list[pd.DataFrame] = []

    successful_dates = 0
    empty_dates = 0

    for i, trading_date in enumerate(
        target_dates,
        start=1,
    ):

        print(
            f"[{i}/{len(target_dates)}] "
            f"{trading_date}"
        )

        try:

            day_data = fetch_date(
                session,
                trading_date,
            )

            if day_data.empty:

                empty_dates += 1

                print(
                    "  No relevant market data "
                    "(weekend/holiday/non-trading day)."
                )

                continue

            new_frames.append(day_data)

            successful_dates += 1

            print(
                f"  Retrieved "
                f"{len(day_data)} constituent rows."
            )

        except Exception as exc:

            print(
                f"  ERROR processing "
                f"{trading_date}: {exc}"
            )

        # ---------------------------------------------------------
        # Checkpoint
        # ---------------------------------------------------------

        if (
            successful_dates > 0
            and successful_dates % CHECKPOINT_EVERY == 0
        ):

            if new_frames:

                new_data = pd.concat(
                    new_frames,
                    ignore_index=True,
                )

                combined = pd.concat(
                    [
                        existing,
                        new_data,
                    ],
                    ignore_index=True,
                )

                save_data(combined)

                existing = combined

                new_frames = []

                print(
                    "  ✓ Checkpoint saved."
                )

        # Small delay to avoid hammering NSE.
        time.sleep(0.15)

    # -------------------------------------------------------------
    # FINAL SAVE
    # -------------------------------------------------------------

    if new_frames:

        new_data = pd.concat(
            new_frames,
            ignore_index=True,
        )

        existing = pd.concat(
            [
                existing,
                new_data,
            ],
            ignore_index=True,
        )

    save_data(existing)

    # -------------------------------------------------------------
    # INGESTION SUMMARY
    # -------------------------------------------------------------

    final = pd.read_csv(
        OUTPUT_FILE,
        parse_dates=["date"],
    )

    print()
    print("=" * 70)
    print("INGESTION COMPLETE")
    print("=" * 70)

    print(
        f"Final rows       : {len(final):,}"
    )

    print(
        f"Unique dates     : "
        f"{final['date'].nunique():,}"
    )

    print(
        f"Unique securities: "
        f"{final['symbol'].nunique():,}"
    )

    print(
        f"Date range       : "
        f"{final['date'].min().date()} "
        f"→ "
        f"{final['date'].max().date()}"
    )

    print(
        f"Successful files : {successful_dates:,}"
    )

    print(
        f"Empty/non-trading: {empty_dates:,}"
    )

    print(
        f"Output           : {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()