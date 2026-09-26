from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


# ---------------------------------------------------------------------
# PROJECT CONFIGURATION
# ---------------------------------------------------------------------

START_DATE = pd.Timestamp("2023-01-01")
END_DATE = pd.Timestamp("2026-08-31")

OUTPUT_PATH = Path(
    "data/raw/earnings_raw.csv"
)

REQUEST_DELAY_SECONDS = 1.0
PAGE_LOAD_TIMEOUT = 60_000


# ---------------------------------------------------------------------
# NIFTY BANK HISTORICAL STOCK UNIVERSE
# ---------------------------------------------------------------------

INSTRUMENTS = {
    "AUBANK": {
        "name": "AU Small Finance Bank",
        "slug": "au-small-finance-bank-ltd",
    },
    "AXISBANK": {
        "name": "Axis Bank",
        "slug": "axis-bank",
    },
    "BANKBARODA": {
        "name": "Bank of Baroda",
        "slug": "bank-of-baroda",
    },
    "BANDHANBNK": {
        "name": "Bandhan Bank",
        "slug": "bandhan-bank-ltd",
    },
    "CANBK": {
        "name": "Canara Bank",
        "slug": "canara-bank",
    },
    "FEDERALBNK": {
        "name": "Federal Bank",
        "slug": "the-federal-bank",
    },
    "HDFCBANK": {
        "name": "HDFC Bank",
        "slug": "hdfc-bank-ltd",
    },
    "ICICIBANK": {
        "name": "ICICI Bank",
        "slug": "icici-bank-ltd",
    },
    "IDFCFIRSTB": {
        "name": "IDFC First Bank",
        "slug": "idfc-bank-ltd",
    },
    "INDUSINDBK": {
        "name": "IndusInd Bank",
        "slug": "indusind-bank",
    },
    "KOTAKBANK": {
        "name": "Kotak Mahindra Bank",
        "slug": "kotak-mahindra-bank",
    },
    "PNB": {
        "name": "Punjab National Bank",
        "slug": "punjab-national-bank",
    },
    "SBIN": {
        "name": "State Bank of India",
        "slug": "state-bank-of-india",
    },
    "UNIONBANK": {
        "name": "Union Bank of India",
        "slug": "union-bank-of-india",
    },
    "YESBANK": {
        "name": "Yes Bank",
        "slug": "yes-bank",
    },
}


# ---------------------------------------------------------------------
# PARSING HELPERS
# ---------------------------------------------------------------------

def parse_numeric(value: str | None) -> float | None:
    """
    Convert Investing.com numeric text to float.

    Handles:
    - commas
    - percentages
    - plus signs
    - B / M / K suffixes
    - missing values
    """

    if value is None:
        return None

    value = value.strip()

    if not value or value in {"--", "-", "N/A"}:
        return None

    value = (
        value
        .replace(",", "")
        .replace("%", "")
        .replace("+", "")
    )

    multiplier = 1.0

    if value.endswith("B"):
        multiplier = 1_000_000_000
        value = value[:-1]

    elif value.endswith("M"):
        multiplier = 1_000_000
        value = value[:-1]

    elif value.endswith("K"):
        multiplier = 1_000
        value = value[:-1]

    try:
        return float(value) * multiplier

    except ValueError:
        return None


def parse_date(value: str | None) -> pd.Timestamp | None:
    """Parse Investing.com date text."""

    if not value:
        return None

    parsed = pd.to_datetime(
        value,
        errors="coerce",
        dayfirst=False,
    )

    if pd.isna(parsed):
        parsed = pd.to_datetime(
            value,
            errors="coerce",
            dayfirst=True,
        )

    if pd.isna(parsed):
        return None

    return parsed


# ---------------------------------------------------------------------
# EARNINGS DATA EXTRACTION
# ---------------------------------------------------------------------

def extract_visible_earnings_rows(page) -> list[dict]:
    """
    Extract earnings rows from Investing.com's rendered page text.

    Uses pattern matching instead of relying on Investing.com's
    changing HTML/table structure.
    """

    import re

    text = page.locator("body").inner_text()

    start_marker = "Release Date"
    start = text.find(start_marker)

    if start == -1:
        raise RuntimeError(
            "Could not find 'Release Date' on the earnings page."
        )

    section = text[start:]

    # Stop before the unrelated content below the earnings table.
    for marker in (
        "All numbers in INR",
        "FAQ",
    ):
        position = section.find(marker)

        if position != -1:
            section = section[:position]

    # ---------------------------------------------------------------
    # Normalize whitespace.
    #
    # This is important because Playwright may return:
    #
    # 22.90
    # /22.99
    #
    # instead of:
    #
    # 22.90 / 22.99
    # ---------------------------------------------------------------

    section = re.sub(
        r"\s+",
        " ",
        section,
    ).strip()

    # Remove the table headers.
    header_pattern = re.compile(
        r"Release Date\s+"
        r"Period End\s+"
        r"EPS\s*/?\s*Forecast\s+"
        r"Revenue\s*/?\s*Forecast\s+"
        r"EPS Surprise %\s+"
        r"Revenue Surprise %\s+"
        r"Reaction",
        flags=re.IGNORECASE,
    )

    match = header_pattern.search(section)

    if not match:
        raise RuntimeError(
            "Could not identify the earnings table headers."
        )

    section = section[match.end():]

    # ---------------------------------------------------------------
    # Earnings-row pattern
    #
    # Example:
    #
    # Jul 18, 2026
    # 06/2026
    # 22.90 / 22.99
    # 213.82B / 216.43B
    # -0.39%
    # -1.21%
    # -5.46%
    #
    # Also handles "--" values.
    # ---------------------------------------------------------------

    date_pattern = (
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+\d{1,2},\s+\d{4}"
    )

    period_pattern = r"\d{2}/\d{4}"

    number_pattern = (
        r"(?:--|-?\d+(?:,\d{3})*(?:\.\d+)?[BMK]?)"
    )

    percentage_pattern = (
        r"(?:--|[+-]?\d+(?:\.\d+)?%)"
    )

    row_pattern = re.compile(
        rf"(?P<release_date>{date_pattern})\s+"
        rf"(?P<period_end>{period_pattern})\s+"
        rf"(?P<eps_actual>{number_pattern})\s*/\s*"
        rf"(?P<eps_forecast>{number_pattern})\s+"
        rf"(?P<revenue_actual>{number_pattern})\s*/\s*"
        rf"(?P<revenue_forecast>{number_pattern})\s+"
        rf"(?P<eps_surprise>{percentage_pattern})\s+"
        rf"(?P<revenue_surprise>{percentage_pattern})\s+"
        rf"(?P<reaction>{percentage_pattern}|Free Sign Up)",
        flags=re.IGNORECASE,
    )

    matches = list(
        row_pattern.finditer(section)
    )

    if not matches:
        raise RuntimeError(
            "Earnings section was found, but no earnings rows "
            "could be parsed."
        )

    rows = []

    for match in matches:

        rows.append(
            {
                "release_date": match.group(
                    "release_date"
                ),
                "period_end": match.group(
                    "period_end"
                ),
                "eps_actual": match.group(
                    "eps_actual"
                ),
                "eps_forecast": match.group(
                    "eps_forecast"
                ),
                "revenue_actual": match.group(
                    "revenue_actual"
                ),
                "revenue_forecast": match.group(
                    "revenue_forecast"
                ),
                "eps_surprise": match.group(
                    "eps_surprise"
                ),
                "revenue_surprise": match.group(
                    "revenue_surprise"
                ),
                "reaction": match.group(
                    "reaction"
                ),
            }
        )

    return rows


# ---------------------------------------------------------------------
# LOAD COMPLETE HISTORY
# ---------------------------------------------------------------------

def load_all_history(
    page,
    symbol: str,
) -> list[dict]:
    """
    Repeatedly click 'Load more' until the study-period boundary
    is reached.
    """

    last_row_count = 0
    stable_attempts = 0

    while True:

        rows = extract_visible_earnings_rows(
            page
        )

        print(
            f"    Loaded {len(rows)} earnings rows"
        )

        dates = [
            parse_date(
                row["release_date"]
            )
            for row in rows
        ]

        dates = [
            date
            for date in dates
            if date is not None
        ]

        if not dates:
            raise RuntimeError(
                f"{symbol}: no valid release dates found."
            )

        oldest_date = min(dates)

        print(
            f"    Oldest release: "
            f"{oldest_date.date()}"
        )

        # We have reached far enough back.
        if oldest_date <= START_DATE:
            return rows

        # -----------------------------------------------------------
        # Detect a Load More operation that isn't adding data.
        # -----------------------------------------------------------

        if len(rows) == last_row_count:
            stable_attempts += 1
        else:
            stable_attempts = 0

        last_row_count = len(rows)

        if stable_attempts >= 2:
            # The page may still be processing the previous request.
            # Give the table another chance before declaring failure.
            page.wait_for_timeout(5_000)

            refreshed_rows = extract_visible_earnings_rows(page)

            if len(refreshed_rows) > last_row_count:
                rows = refreshed_rows
                stable_attempts = 0
                last_row_count = len(rows)

                refreshed_dates = [
                    parse_date(row["release_date"])
                    for row in rows
                ]
                refreshed_dates = [
                    date for date in refreshed_dates if date is not None
                ]

                if refreshed_dates and min(refreshed_dates) <= START_DATE:
                    return rows
            else:
                raise RuntimeError(
                    f"{symbol}: 'Load more' did not increase the "
                    f"visible row count after repeated attempts."
                )

        # -----------------------------------------------------------
        # Find Load More button.
        # -----------------------------------------------------------

        buttons = page.get_by_text(
            "Load more",
            exact=True,
        )

        if buttons.count() == 0:
            raise RuntimeError(
                f"{symbol}: 'Load more' button not found "
                f"before reaching study-period start."
            )

        button = buttons.last

        try:

            button.scroll_into_view_if_needed()

            before_count = len(rows)

            try:
                button.click(
                    timeout=10_000,
                    force=True
                )

            except PlaywrightTimeoutError:
                # Fallback for Investing.com's dynamically layered UI.
                button.evaluate(
                    "(element) => element.click()"
                )

            # Wait for the actual table content to grow rather than
            # assuming a fixed 2-second rendering time.
            deadline = time.time() + 15

            while time.time() < deadline:
                page.wait_for_timeout(1_000)

                current_rows = extract_visible_earnings_rows(page)

                if len(current_rows) > before_count:
                    break

            else:
                # One final wait for a slower network response.
                page.wait_for_timeout(5_000)

            time.sleep(
                REQUEST_DELAY_SECONDS
            )

        except Exception as exc:

            raise RuntimeError(
                f"{symbol}: failed to click 'Load more'."
            ) from exc

        time.sleep(
            REQUEST_DELAY_SECONDS
        )


# ---------------------------------------------------------------------
# NORMALIZATION
# ---------------------------------------------------------------------

def normalize_rows(
    symbol: str,
    rows: list[dict],
) -> pd.DataFrame:
    """
    Convert scraped text into the raw earnings dataset schema.
    """

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    # ---------------------------------------------------------------
    # Release date
    # ---------------------------------------------------------------

    df["date"] = df["release_date"].apply(
        parse_date
    )

    # ---------------------------------------------------------------
    # Period end
    # ---------------------------------------------------------------

    df["period_end"] = (
        df["period_end"]
        .astype(str)
        .str.strip()
    )

    # ---------------------------------------------------------------
    # Numeric fields
    # ---------------------------------------------------------------

    df["eps_actual"] = (
        df["eps_actual"]
        .apply(parse_numeric)
    )

    df["eps_forecast"] = (
        df["eps_forecast"]
        .apply(parse_numeric)
    )

    df["revenue_actual"] = (
        df["revenue_actual"]
        .apply(parse_numeric)
    )

    df["revenue_forecast"] = (
        df["revenue_forecast"]
        .apply(parse_numeric)
    )

    df["eps_surprise"] = (
        df["eps_surprise"]
        .apply(parse_numeric)
    )

    df["revenue_surprise"] = (
        df["revenue_surprise"]
        .apply(parse_numeric)
    )

    df["symbol"] = symbol

    # ---------------------------------------------------------------
    # Keep raw source fields only.
    # ---------------------------------------------------------------

    df = df[
        [
            "symbol",
            "date",
            "period_end",
            "eps_actual",
            "eps_forecast",
            "revenue_actual",
            "revenue_forecast",
            "eps_surprise",
            "revenue_surprise",
            "reaction",
        ]
    ].copy()

    # ---------------------------------------------------------------
    # Study-period filter.
    # ---------------------------------------------------------------

    df = df[
        (df["date"] >= START_DATE)
        & (df["date"] <= END_DATE)
    ].copy()

    return df


# ---------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------

def validate_output(
    df: pd.DataFrame,
) -> None:
    """Validate the final raw earnings dataset."""

    required_columns = {
        "symbol",
        "date",
        "period_end",
        "eps_actual",
        "eps_forecast",
        "revenue_actual",
        "revenue_forecast",
        "eps_surprise",
        "revenue_surprise",
        "reaction",
    }

    missing_columns = (
        required_columns
        - set(df.columns)
    )

    if missing_columns:
        raise ValueError(
            "Missing required columns: "
            f"{sorted(missing_columns)}"
        )

    if df.empty:
        raise ValueError(
            "Final earnings dataset is empty."
        )

    # ---------------------------------------------------------------
    # Dates
    # ---------------------------------------------------------------

    if df["date"].isna().any():
        raise ValueError(
            "Earnings dataset contains invalid dates."
        )

    if (
        df["date"].min() < START_DATE
        or df["date"].max() > END_DATE
    ):
        raise ValueError(
            "Output contains dates outside study period."
        )

    # ---------------------------------------------------------------
    # Duplicate observations
    # ---------------------------------------------------------------

    duplicates = df.duplicated(
        subset=[
            "symbol",
            "date",
            "period_end",
        ]
    )

    if duplicates.any():

        duplicate_count = int(
            duplicates.sum()
        )

        raise ValueError(
            f"Found {duplicate_count} duplicate "
            "earnings observations."
        )

    # ---------------------------------------------------------------
    # All 15 historical banks must be represented.
    # ---------------------------------------------------------------

    expected_symbols = set(
        INSTRUMENTS.keys()
    )

    actual_symbols = set(
        df["symbol"].unique()
    )

    missing_symbols = (
        expected_symbols
        - actual_symbols
    )

    if missing_symbols:
        raise ValueError(
            "Missing banks from final dataset: "
            + ", ".join(
                sorted(missing_symbols)
            )
        )


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main() -> None:

    print("=" * 70)
    print(
        "NIFTY BANK CONSTITUENT EARNINGS ACQUISITION"
    )
    print("=" * 70)

    all_parts: list[pd.DataFrame] = []

    with sync_playwright() as playwright:

        browser = playwright.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/152.0.0.0 Safari/537.36"
            ),
        )

        page = context.new_page()

        page.set_default_timeout(
            PAGE_LOAD_TIMEOUT
        )

        # -----------------------------------------------------------
        # Process each bank.
        # -----------------------------------------------------------

        for symbol, config in INSTRUMENTS.items():

            url = (
                "https://www.investing.com/equities/"
                f"{config['slug']}-earnings"
            )

            print(
                f"\n{symbol} | {config['name']}"
            )

            print(
                f"  {url}"
            )

            try:

                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=PAGE_LOAD_TIMEOUT,
                )

                # Give the earnings component time to render.
                page.wait_for_timeout(
                    2_000
                )

                print("TITLE:", page.title())
                print("URL:", page.url)
                print("HAS RELEASE DATE:", "Release Date" in page.locator("body").inner_text())

                rows = load_all_history(
                    page=page,
                    symbol=symbol,
                )

                df = normalize_rows(
                    symbol=symbol,
                    rows=rows,
                )

                print(
                    f"    Study-period rows: "
                    f"{len(df)}"
                )

                if df.empty:
                    raise RuntimeError(
                        f"{symbol}: no records "
                        "in study period."
                    )

                all_parts.append(df)

            except Exception as exc:

                raise RuntimeError(
                    f"{symbol}: earnings acquisition failed."
                ) from exc

            time.sleep(
                REQUEST_DELAY_SECONDS
            )

        browser.close()

    # -----------------------------------------------------------------
    # COMBINE
    # -----------------------------------------------------------------

    if not all_parts:
        raise RuntimeError(
            "No earnings data was acquired."
        )

    final_df = pd.concat(
        all_parts,
        ignore_index=True,
    )

    # -----------------------------------------------------------------
    # SORT
    # -----------------------------------------------------------------

    final_df = (
        final_df
        .sort_values(
            [
                "date",
                "symbol",
            ]
        )
        .reset_index(drop=True)
    )

    # -----------------------------------------------------------------
    # FINAL VALIDATION
    # -----------------------------------------------------------------

    validate_output(
        final_df
    )

    # -----------------------------------------------------------------
    # WRITE RAW DATA
    # -----------------------------------------------------------------

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    final_df.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    # -----------------------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------------------

    print("\n" + "=" * 70)
    print(
        "EARNINGS ACQUISITION COMPLETE"
    )
    print("=" * 70)

    print(
        f"\nRows       : "
        f"{len(final_df):,}"
    )

    print(
        f"Symbols    : "
        f"{final_df['symbol'].nunique()}"
    )

    print(
        f"Date range : "
        f"{final_df['date'].min().date()} "
        f"→ "
        f"{final_df['date'].max().date()}"
    )

    print(
        "\nRows by bank:"
    )

    print(
        final_df["symbol"]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print(
        f"\nOutput:\n"
        f"{OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()