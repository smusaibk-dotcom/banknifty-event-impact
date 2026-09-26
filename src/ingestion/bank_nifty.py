from __future__ import annotations

import time
import tomllib
from datetime import date, timedelta
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ============================================================
# PROJECT CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_PATH = PROJECT_ROOT / "configs" / "settings.toml"

with CONFIG_PATH.open("rb") as file:
    CONFIG = tomllib.load(file)


START_DATE = date.fromisoformat(
    CONFIG["ingestion_scope"]["start_date"]
)

END_DATE = date.fromisoformat(
    CONFIG["ingestion_scope"]["end_date"]
)

RAW_DATA_DIR = (
    PROJECT_ROOT
    / CONFIG["storage"]["raw_data_dir"]
)

OUTPUT_PATH = (
    RAW_DATA_DIR
    / "bank_nifty_daily_raw.csv"
)


# ============================================================
# SOURCE CONFIGURATION
# ============================================================

NSE_ARCHIVE_URL = (
    "https://archives.nseindia.com/"
    "content/indices/ind_close_all_{date}.csv"
)

TARGET_INDEX = CONFIG["metadata"]["index_name"]


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


# ============================================================
# EXPECTED OUTPUT SCHEMA
# ============================================================

OUTPUT_COLUMNS = [
    "date",
    "open",
    "high",
    "low",
    "close",
]


# ============================================================
# HTTP SESSION
# ============================================================

def create_session() -> requests.Session:
    """
    Create a requests session with retry handling.
    """

    session = requests.Session()

    session.headers.update(HEADERS)

    retry_strategy = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )

    adapter = HTTPAdapter(
        max_retries=retry_strategy
    )

    session.mount(
        "https://",
        adapter,
    )

    session.mount(
        "http://",
        adapter,
    )

    return session


# ============================================================
# FETCH ONE DAILY NSE ARCHIVE
# ============================================================

def fetch_daily_archive(
    session: requests.Session,
    trading_date: date,
) -> pd.DataFrame | None:
    """
    Download NSE's daily index archive for one calendar date.

    Returns:
        DataFrame if an archive exists.
        None if NSE has no file for that date.
    """

    date_string = trading_date.strftime(
        "%d%m%Y"
    )

    url = NSE_ARCHIVE_URL.format(
        date=date_string
    )

    response = session.get(
        url,
        timeout=30,
    )

    # Weekends and exchange holidays generally
    # have no daily archive.
    if response.status_code == 404:
        return None

    response.raise_for_status()

    if not response.content:
        raise RuntimeError(
            f"Empty NSE response for {trading_date}."
        )

    return pd.read_csv(
        StringIO(response.text)
    )


# ============================================================
# EXTRACT NIFTY BANK
# ============================================================

def extract_bank_nifty(
    daily_data: pd.DataFrame,
) -> pd.DataFrame:
    """
    Extract only Nifty Bank OHLC data from
    NSE's daily all-index dataset.

    This performs source-schema handling only.
    No analytical cleaning is performed here.
    """

    # Normalize source column labels so that
    # minor formatting differences do not break ingestion.
    daily_data.columns = (
        daily_data.columns
        .astype(str)
        .str.replace(
            "\ufeff",
            "",
            regex=False,
        )
        .str.strip()
    )

    required_columns = {
        "Index Name",
        "Index Date",
        "Open Index Value",
        "High Index Value",
        "Low Index Value",
        "Closing Index Value",
    }

    missing_columns = (
        required_columns
        - set(daily_data.columns)
    )

    if missing_columns:
        raise RuntimeError(
            "Expected NSE columns are missing: "
            f"{sorted(missing_columns)}\n"
            f"Received columns: "
            f"{daily_data.columns.tolist()}"
        )

    bank_nifty = daily_data.loc[
        daily_data["Index Name"]
        .astype(str)
        .str.strip()
        .eq(TARGET_INDEX)
    ].copy()

    if bank_nifty.empty:
        return pd.DataFrame(
            columns=OUTPUT_COLUMNS
        )

    bank_nifty = bank_nifty[
        [
            "Index Date",
            "Open Index Value",
            "High Index Value",
            "Low Index Value",
            "Closing Index Value",
        ]
    ]

    bank_nifty = bank_nifty.rename(
        columns={
            "Index Date": "date",
            "Open Index Value": "open",
            "High Index Value": "high",
            "Low Index Value": "low",
            "Closing Index Value": "close",
        }
    )

    return bank_nifty


# ============================================================
# LOAD EXISTING ACQUIRED DATA
# ============================================================

def load_existing_data() -> pd.DataFrame:
    """
    Load previously acquired data.

    If the raw file does not exist, return an empty
    DataFrame with the expected schema.
    """

    if not OUTPUT_PATH.exists():
        return pd.DataFrame(
            columns=OUTPUT_COLUMNS
        )

    existing_data = pd.read_csv(
        OUTPUT_PATH,
        parse_dates=["date"],
    )

    missing_columns = (
        set(OUTPUT_COLUMNS)
        - set(existing_data.columns)
    )

    if missing_columns:
        raise RuntimeError(
            "Existing Bank Nifty file is missing "
            f"columns: {sorted(missing_columns)}"
        )

    return existing_data[OUTPUT_COLUMNS]


# ============================================================
# DETERMINE MISSING DATES
# ============================================================

def get_missing_dates(
    existing_data: pd.DataFrame,
) -> list[date]:
    """
    Determine which calendar dates within the configured
    range have not yet been acquired.

    Existing dates are never downloaded again.
    """

    if existing_data.empty:
        existing_dates: set[date] = set()
    else:
        existing_dates = set(
            existing_data["date"]
            .dt.date
        )

    all_dates = pd.date_range(
        start=START_DATE,
        end=END_DATE,
        freq="D",
    )

    missing_dates = [
        current_date.date()
        for current_date in all_dates
        if current_date.date()
        not in existing_dates
    ]

    return missing_dates


# ============================================================
# SAVE DATA
# ============================================================

def save_data(
    data: pd.DataFrame,
) -> None:
    """
    Save the current acquired dataset.

    Data is deduplicated by date and sorted chronologically
    before being written.
    """

    RAW_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    data = (
        data[OUTPUT_COLUMNS]
        .drop_duplicates(
            subset=["date"],
            keep="last",
        )
        .sort_values("date")
        .reset_index(drop=True)
    )

    data.to_csv(
        OUTPUT_PATH,
        index=False,
    )


# ============================================================
# ACQUISITION PIPELINE
# ============================================================

def acquire_bank_nifty() -> pd.DataFrame:
    """
    Incrementally acquire Bank Nifty data.

    Existing data is preserved.
    Only missing dates are requested.
    Successful new records are checkpointed periodically.
    """

    existing_data = load_existing_data()

    missing_dates = get_missing_dates(
        existing_data
    )

    print(
        f"Existing records : "
        f"{len(existing_data):,}"
    )

    print(
        f"Dates to acquire : "
        f"{len(missing_dates):,}"
    )

    # --------------------------------------------------------
    # Nothing new to acquire
    # --------------------------------------------------------

    if not missing_dates:

        print(
            "Nothing new to acquire."
        )

        return existing_data

    # --------------------------------------------------------
    # Start session
    # --------------------------------------------------------

    session = create_session()

    combined_data = existing_data.copy()

    successful_records = 0
    failed_dates: list[date] = []

    # --------------------------------------------------------
    # Acquire missing dates
    # --------------------------------------------------------

    for index, current_date in enumerate(
        missing_dates,
        start=1,
    ):

        print(
            f"[{index}/{len(missing_dates)}] "
            f"Fetching {current_date}"
        )

        try:

            daily_data = fetch_daily_archive(
                session=session,
                trading_date=current_date,
            )

            # No archive for this date.
            if daily_data is None:
                continue

            bank_nifty = extract_bank_nifty(
                daily_data
            )

            if bank_nifty.empty:
                continue

            # Add newly acquired records.
            combined_data = pd.concat(
                [
                    combined_data,
                    bank_nifty,
                ],
                ignore_index=True,
            )

            successful_records += len(
                bank_nifty
            )

            # ------------------------------------------------
            # Checkpoint every 25 successful records.
            # ------------------------------------------------

            if successful_records % 25 == 0:

                save_data(
                    combined_data
                )

                print(
                    f"  Checkpoint saved "
                    f"({successful_records} "
                    f"new records)"
                )

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
        ) as exc:

            print(
                f"  FAILED: {current_date} "
                f"→ {exc}"
            )

            failed_dates.append(
                current_date
            )

        # Small delay to avoid hammering NSE.
        time.sleep(0.2)

    # --------------------------------------------------------
    # Final save
    # --------------------------------------------------------

    save_data(
        combined_data
    )

    # --------------------------------------------------------
    # Acquisition summary
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("ACQUISITION SUMMARY")
    print("=" * 60)

    print(
        f"Existing records      : "
        f"{len(existing_data):,}"
    )

    print(
        f"New records acquired  : "
        f"{successful_records:,}"
    )

    print(
        f"Final records         : "
        f"{len(combined_data.drop_duplicates('date')):,}"
    )

    print(
        f"Failed dates          : "
        f"{len(failed_dates):,}"
    )

    print(
        f"Output                : "
        f"{OUTPUT_PATH}"
    )

    if failed_dates:

        print()
        print(
            "Failed dates:"
        )

        for failed_date in failed_dates:
            print(
                f"  {failed_date}"
            )

    return combined_data


# ============================================================
# ENTRY POINT
# ============================================================

def main() -> None:

    print("=" * 60)
    print("BANK NIFTY DATA ACQUISITION")
    print("=" * 60)
    print(
        f"Index      : {TARGET_INDEX}"
    )
    print(
        f"Start date : {START_DATE}"
    )

    print(
        f"End date   : {END_DATE}"
    )
    print(
        "Mode       : Incremental"
    )
    print()

    acquire_bank_nifty()


if __name__ == "__main__":
    main()