from __future__ import annotations

import io
import re
import time
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import fitz  # PyMuPDF
import pandas as pd
import requests


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

BASE_DIR = PROJECT_ROOT / "data" / "raw" / "index_weightage"

SOURCE_DIR = BASE_DIR / "source"
EXTRACTED_DIR = BASE_DIR / "extracted"

OUTPUT_FILE = BASE_DIR / "constituent_weights_raw.csv"

OFFICIAL_MONTHLY_REPORTS_URL = (
    "https://www.niftyindices.com/reports/monthly-reports"
)

ZIP_URL_TEMPLATE = (
    "https://www.niftyindices.com/"
    "Indices_-_Market_Capitalisation_and_Weightage/"
    "indices_data{month}{year}.zip"
)

# ============================================================
# PROJECT RANGE
# ============================================================

START_MONTH = "2023-01"
END_MONTH = "2026-08"

# ============================================================
# HTTP CONFIGURATION
# ============================================================

REQUEST_TIMEOUT = 60
MAX_RETRIES = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


# ============================================================
# DATA STRUCTURE
# ============================================================

@dataclass(frozen=True)
class MonthReport:
    year: int
    month: int

    @property
    def month_key(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    @property
    def month_abbr(self) -> str:
        return date(
            self.year,
            self.month,
            1,
        ).strftime("%b")

    @property
    def zip_filename(self) -> str:
        return f"indices_data{self.month_abbr}{self.year}.zip"

    @property
    def zip_url(self) -> str:
        return ZIP_URL_TEMPLATE.format(
            month=self.month_abbr,
            year=self.year,
        )

    @property
    def source_path(self) -> Path:
        return SOURCE_DIR / self.zip_filename

    @property
    def extracted_dir(self) -> Path:
        return EXTRACTED_DIR / self.month_key


# ============================================================
# MONTH GENERATION
# ============================================================

def generate_months(
    start_month: str,
    end_month: str,
) -> list[MonthReport]:
    """Generate an inclusive monthly range."""

    start = pd.Period(start_month, freq="M")
    end = pd.Period(end_month, freq="M")

    if start > end:
        raise ValueError(
            "START_MONTH must be less than or equal to END_MONTH."
        )

    return [
        MonthReport(
            year=period.year,
            month=period.month,
        )
        for period in pd.period_range(
            start,
            end,
            freq="M",
        )
    ]


# ============================================================
# DOWNLOAD
# ============================================================

def download_zip(report: MonthReport) -> Path:
    """
    Download one monthly ZIP.

    Existing valid ZIPs are reused.
    Downloads are written to a temporary file first.
    """

    SOURCE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = report.source_path

    # --------------------------------------------------------
    # Reuse existing valid source
    # --------------------------------------------------------

    if destination.exists():

        if zipfile.is_zipfile(destination):

            print(
                f"  ✓ Source already exists: "
                f"{destination.name}"
            )

            return destination

        print(
            "  ! Existing source file is invalid. "
            "Re-downloading."
        )

    temporary = destination.with_suffix(".tmp")

    # --------------------------------------------------------
    # Download with retry
    # --------------------------------------------------------

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        try:

            print(
                f"  Downloading: "
                f"{report.zip_url}"
            )

            response = requests.get(
                report.zip_url,
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
            )

            response.raise_for_status()

            content = response.content

            # Validate response before saving.
            if not zipfile.is_zipfile(
                io.BytesIO(content)
            ):
                raise RuntimeError(
                    "Downloaded response is not a valid ZIP."
                )

            temporary.write_bytes(content)

            # Validate saved file.
            if not zipfile.is_zipfile(
                temporary
            ):
                raise RuntimeError(
                    "Saved temporary ZIP failed validation."
                )

            # Atomic replacement.
            temporary.replace(destination)

            print(
                f"  ✓ Saved: {destination}"
            )

            return destination

        except Exception as exc:

            print(
                f"  ! Attempt "
                f"{attempt}/{MAX_RETRIES} failed: "
                f"{exc}"
            )

            if temporary.exists():
                temporary.unlink()

            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)

    raise RuntimeError(
        f"Could not download "
        f"{report.month_key}"
    )


# ============================================================
# PDF IDENTIFICATION
# ============================================================

def extract_pdf_text(
    pdf_bytes: bytes,
) -> str:
    """Extract text from a PDF in memory."""

    with fitz.open(
        stream=pdf_bytes,
        filetype="pdf",
    ) as document:

        return "\n".join(
            page.get_text()
            for page in document
        )


def is_nifty_bank_pdf(
    filename: str,
    pdf_bytes: bytes,
) -> bool:
    """
    Identify the NIFTY Bank PDF.

    Filename is only a first-level signal.
    PDF content is also inspected.
    """

    filename_signal = (
        "nifty_bank"
        in filename.lower()
    )

    try:

        text = extract_pdf_text(
            pdf_bytes
        )

    except Exception:

        return False

    normalized = re.sub(
        r"\s+",
        " ",
        text,
    ).lower()

    content_signal = (
        "constituents of nifty bank"
        in normalized
    )

    return (
        filename_signal
        and content_signal
    ) or content_signal


# ============================================================
# LOCATE NIFTY BANK PDF
# ============================================================

def get_nifty_bank_pdf(
    report: MonthReport,
    zip_path: Path,
) -> tuple[str, bytes]:
    """
    Locate the NIFTY Bank PDF inside the ZIP.

    Only the relevant PDF is returned.
    """

    with zipfile.ZipFile(
        zip_path,
        "r",
    ) as archive:

        pdf_members = [
            member
            for member in archive.infolist()
            if (
                not member.is_dir()
                and member.filename.lower().endswith(".pdf")
            )
        ]

        if not pdf_members:

            raise RuntimeError(
                f"No PDF files found in "
                f"{zip_path.name}"
            )

        candidates = []

        for member in pdf_members:

            pdf_bytes = archive.read(
                member
            )

            filename = Path(
                member.filename
            ).name

            if is_nifty_bank_pdf(
                filename,
                pdf_bytes,
            ):

                candidates.append(
                    (
                        filename,
                        pdf_bytes,
                    )
                )

        if not candidates:

            raise RuntimeError(
                f"NIFTY Bank PDF could not "
                f"be identified in "
                f"{zip_path.name}"
            )

        if len(candidates) > 1:

            raise RuntimeError(
                "Multiple NIFTY Bank PDF "
                f"candidates found: "
                f"{[x[0] for x in candidates]}"
            )

        return candidates[0]


# ============================================================
# SAVE EXTRACTED PDF
# ============================================================

def save_nifty_bank_pdf(
    report: MonthReport,
    pdf_name: str,
    pdf_bytes: bytes,
) -> Path:
    """
    Save only the relevant NIFTY Bank PDF.

    Existing extracted PDFs are reused.
    """

    report.extracted_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = (
        report.extracted_dir
        / Path(pdf_name).name
    )

    if destination.exists():

        print(
            f"  ✓ Extracted PDF already exists: "
            f"{destination.name}"
        )

        return destination

    destination.write_bytes(
        pdf_bytes
    )

    print(
        f"  ✓ Extracted: "
        f"{destination}"
    )

    return destination


# ============================================================
# REPORT DATE EXTRACTION
# ============================================================

MONTH_PATTERN = (
    r"(January|February|March|April|May|June|"
    r"July|August|September|October|November|December)"
)


def extract_report_date(
    pdf_path: Path,
) -> str:
    """
    Extract the actual report date from the PDF title.

    Example:

        July 31, 2026

    becomes:

        2026-07-31
    """

    text = extract_pdf_text(
        pdf_path.read_bytes()
    )

    pattern = (
        rf"{MONTH_PATTERN}"
        r"\s+"
        r"(\d{1,2})"
        r",\s+"
        r"(\d{4})"
    )

    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE,
    )

    if not match:

        raise RuntimeError(
            f"Could not determine report date "
            f"from {pdf_path.name}"
        )

    month_name = match.group(1)
    day = int(match.group(2))
    year = int(match.group(3))

    month_number = pd.to_datetime(
        month_name,
        format="%B",
    ).month

    report_date = date(
        year,
        month_number,
        day,
    )

    return report_date.isoformat()


# ============================================================
# TABLE DETECTION
# ============================================================

REQUIRED_HEADER_TERMS = {
    "symbol",
    "security name",
    "industry",
    "close price",
    "index mcap",
    "weightage",
}


def normalize_header(
    value: object,
) -> str:
    """Normalize table header text."""

    return re.sub(
        r"\s+",
        " ",
        str(value)
        .replace("\n", " ")
        .strip()
        .lower(),
    )


def find_constituent_table(
    page: fitz.Page,
) -> list[list[str]]:
    """
    Find the table containing the NIFTY Bank
    constituent data.
    """

    table_finder = page.find_tables()

    tables = table_finder.tables

    if not tables:

        return []

    for table in tables:

        extracted = table.extract()

        if not extracted:
            continue

        header = {
            normalize_header(cell)
            for cell in extracted[0]
            if cell is not None
        }

        # Header matching is intentionally based on
        # required semantic fields rather than a fixed
        # column position.
        if {
            "symbol",
            "security name",
            "industry",
            "close price",
            "weightage (%)",
        }.issubset(header) or {
            "symbol",
            "security name",
            "industry",
            "close price",
            "weightage (%)",
            "index mcap (rs. crores)",
        }.issubset(header):

            return extracted

    return []


# ============================================================
# TABLE NORMALIZATION
# ============================================================

def normalize_table(
    table: list[list[str]],
) -> pd.DataFrame:
    """
    Convert the detected PDF table into a normalized DataFrame.
    """

    if len(table) < 2:

        raise RuntimeError(
            "Detected table does not contain "
            "data rows."
        )

    raw_header = table[0]

    normalized_headers = [
        normalize_header(value)
        for value in raw_header
    ]

    column_mapping: dict[str, str] = {}

    for index, header in enumerate(
        normalized_headers
    ):

        if header == "symbol":

            column_mapping["symbol"] = raw_header[index]

        elif header == "security name":

            column_mapping[
                "security_name"
            ] = raw_header[index]

        elif header == "industry":

            column_mapping[
                "industry"
            ] = raw_header[index]

        elif header == "close price":

            column_mapping[
                "close_price"
            ] = raw_header[index]

        elif header.startswith(
            "index mcap"
        ):

            column_mapping[
                "index_mcap_rs_crores"
            ] = raw_header[index]

        elif header.startswith(
            "weightage"
        ):

            column_mapping[
                "weightage_pct"
            ] = raw_header[index]

    required = {
        "symbol",
        "security_name",
        "industry",
        "close_price",
        "index_mcap_rs_crores",
        "weightage_pct",
    }

    missing = (
        required
        - set(column_mapping)
    )

    if missing:

        raise RuntimeError(
            "Required table columns missing: "
            f"{sorted(missing)}"
        )

    # --------------------------------------------------------
    # Extract rows using column positions.
    # --------------------------------------------------------

    positions = {
        logical_name: normalized_headers.index(
            normalize_header(original_header)
        )
        for logical_name, original_header
        in column_mapping.items()
    }

    records = []

    for row in table[1:]:

        if not row:
            continue

        # Make sure the row has enough columns.
        if len(row) <= max(
            positions.values()
        ):
            continue

        symbol = str(
            row[positions["symbol"]]
        ).strip()

        if not symbol:
            continue

        # Skip accidental repeated headers.
        if (
            symbol.lower()
            == "symbol"
        ):
            continue

        record = {
            "symbol": symbol,
            "security_name": str(
                row[
                    positions["security_name"]
                ]
            ).strip(),
            "industry": str(
                row[
                    positions["industry"]
                ]
            ).strip(),
            "close_price": str(
                row[
                    positions["close_price"]
                ]
            ).strip(),
            "index_mcap_rs_crores": str(
                row[
                    positions[
                        "index_mcap_rs_crores"
                    ]
                ]
            ).strip(),
            "weightage_pct": str(
                row[
                    positions["weightage_pct"]
                ]
            ).strip(),
        }

        records.append(record)

    if not records:

        raise RuntimeError(
            "No constituent rows found "
            "inside detected table."
        )

    df = pd.DataFrame(
        records
    )

    # --------------------------------------------------------
    # Clean numeric fields.
    # --------------------------------------------------------

    numeric_columns = [
        "close_price",
        "index_mcap_rs_crores",
        "weightage_pct",
    ]

    for column in numeric_columns:

        df[column] = (
            df[column]
            .astype(str)
            .str.replace(
                ",",
                "",
                regex=False,
            )
            .str.replace(
                "%",
                "",
                regex=False,
            )
            .str.strip()
        )

        df[column] = pd.to_numeric(
            df[column],
            errors="raise",
        )

    return df


# ============================================================
# PDF → DATAFRAME
# ============================================================

def parse_nifty_bank_pdf(
    pdf_path: Path,
    report: MonthReport,
) -> pd.DataFrame:
    """
    Extract the NIFTY Bank constituent table
    using PDF table geometry.
    """

    report_date = extract_report_date(
        pdf_path
    )

    with fitz.open(
        pdf_path
    ) as document:

        all_tables = []

        for page_number, page in enumerate(
            document,
            start=1,
        ):

            table = find_constituent_table(
                page
            )

            if table:

                all_tables.append(
                    (
                        page_number,
                        table,
                    )
                )

    if not all_tables:

        raise RuntimeError(
            f"No NIFTY Bank constituent "
            f"table detected in "
            f"{pdf_path}"
        )

    # The monthly NIFTY Bank report is expected
    # to contain one constituent table.
    if len(all_tables) > 1:

        # Combine only if multiple pages are
        # actually part of the same report.
        combined_table = []

        first_header = all_tables[0][1][0]

        combined_table.append(
            first_header
        )

        for _, table in all_tables:

            for row in table[1:]:

                combined_table.append(
                    row
                )

        table = combined_table

    else:

        table = all_tables[0][1]

    df = normalize_table(
        table
    )

    # --------------------------------------------------------
    # Add provenance.
    # --------------------------------------------------------

    df.insert(
        0,
        "date",
        report_date,
    )

    df["source_month"] = (
        report.month_key
    )

    df["source_file"] = (
        pdf_path.name
    )

    # --------------------------------------------------------
    # Validation.
    # --------------------------------------------------------

    if df["symbol"].duplicated().any():

        duplicates = (
            df.loc[
                df["symbol"].duplicated(
                    keep=False
                ),
                "symbol",
            ]
            .unique()
            .tolist()
        )

        raise RuntimeError(
            "Duplicate constituent symbols "
            f"found: {duplicates}"
        )

    if not (
        df["weightage_pct"] > 0
    ).all():

        raise RuntimeError(
            "Non-positive weightage detected."
        )

    weight_sum = (
        df["weightage_pct"]
        .sum()
    )

    # PDF rounding means the displayed weights
    # may not sum to exactly 100.
    if abs(
        weight_sum - 100.0
    ) > 0.20:

        raise RuntimeError(
            f"Weightage total is "
            f"{weight_sum:.4f}%, "
            "outside the allowed tolerance."
        )

    # A NIFTY Bank report should contain
    # a plausible number of constituents.
    if not (
        5 <= len(df) <= 20
    ):

        raise RuntimeError(
            f"Unexpected constituent count: "
            f"{len(df)}"
        )

    # --------------------------------------------------------
    # Final column order.
    # --------------------------------------------------------

    df = df[
        [
            "date",
            "symbol",
            "security_name",
            "industry",
            "close_price",
            "index_mcap_rs_crores",
            "weightage_pct",
            "source_month",
            "source_file",
        ]
    ]

    return df


# ============================================================
# EXISTING DATA
# ============================================================

def load_existing_output() -> pd.DataFrame:
    """
    Load the existing consolidated dataset.

    If it does not exist, return an empty DataFrame.
    """

    if not OUTPUT_FILE.exists():

        return pd.DataFrame(
            columns=[
                "date",
                "symbol",
                "security_name",
                "industry",
                "close_price",
                "index_mcap_rs_crores",
                "weightage_pct",
                "source_month",
                "source_file",
            ]
        )

    df = pd.read_csv(
        OUTPUT_FILE
    )

    if df.empty:

        return pd.DataFrame(
            columns=df.columns
        )

    return df


# ============================================================
# MERGE
# ============================================================

def merge_into_output(
    new_df: pd.DataFrame,
) -> None:
    """
    Incrementally merge new data.

    Primary key:

        date + symbol

    Existing records are preserved.
    Duplicate records are not created.
    """

    existing_df = (
        load_existing_output()
    )

    combined = pd.concat(
        [
            existing_df,
            new_df,
        ],
        ignore_index=True,
    )

    combined["date"] = (
        pd.to_datetime(
            combined["date"],
            errors="raise",
        )
        .dt.strftime("%Y-%m-%d")
    )

    # --------------------------------------------------------
    # Idempotency
    # --------------------------------------------------------

    combined = (
        combined
        .drop_duplicates(
            subset=[
                "date",
                "symbol",
            ],
            keep="last",
        )
    )

    # --------------------------------------------------------
    # Stable ordering
    # --------------------------------------------------------

    combined = (
        combined
        .sort_values(
            [
                "date",
                "symbol",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # Atomic write
    # --------------------------------------------------------

    temporary = OUTPUT_FILE.with_suffix(
        ".tmp"
    )

    combined.to_csv(
        temporary,
        index=False,
    )

    temporary.replace(
        OUTPUT_FILE
    )

    print(
        f"  ✓ Consolidated dataset now contains "
        f"{len(combined):,} rows."
    )


# ============================================================
# PROCESS ONE MONTH
# ============================================================

def process_month(
    report: MonthReport,
) -> pd.DataFrame:
    """Run the complete ingestion process for one month."""

    print()
    print("=" * 70)
    print(
        f"PROCESSING {report.month_key}"
    )
    print("=" * 70)

    # --------------------------------------------------------
    # 1. Get ZIP
    # --------------------------------------------------------

    zip_path = download_zip(
        report
    )

    # --------------------------------------------------------
    # 2. Locate NIFTY Bank PDF
    # --------------------------------------------------------

    pdf_name, pdf_bytes = (
        get_nifty_bank_pdf(
            report,
            zip_path,
        )
    )

    print(
        f"  ✓ NIFTY Bank PDF: "
        f"{pdf_name}"
    )

    # --------------------------------------------------------
    # 3. Save relevant PDF
    # --------------------------------------------------------

    pdf_path = save_nifty_bank_pdf(
        report,
        pdf_name,
        pdf_bytes,
    )

    # --------------------------------------------------------
    # 4. Parse table
    # --------------------------------------------------------

    df = parse_nifty_bank_pdf(
        pdf_path,
        report,
    )

    print(
        f"  ✓ Report date: "
        f"{df['date'].iloc[0]}"
    )

    print(
        f"  ✓ Constituents: "
        f"{len(df)}"
    )

    print(
        f"  ✓ Weightage total: "
        f"{df['weightage_pct'].sum():.2f}%"
    )

    return df


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print("=" * 70)
    print(
        "NIFTY BANK HISTORICAL WEIGHTAGE INGESTION"
    )
    print("=" * 70)

    print(
        f"Source: "
        f"{OFFICIAL_MONTHLY_REPORTS_URL}"
    )

    print(
        f"Period: "
        f"{START_MONTH} → {END_MONTH}"
    )

    print(
        f"Output: "
        f"{OUTPUT_FILE}"
    )

    months = generate_months(
        START_MONTH,
        END_MONTH,
    )

    print(
        f"Months to process: "
        f"{len(months)}"
    )

    successful = 0
    failed = []

    # --------------------------------------------------------
    # Process month by month
    # --------------------------------------------------------

    for report in months:

        try:

            df = process_month(
                report
            )

            merge_into_output(
                df
            )

            successful += 1

        except Exception as exc:

            print()
            print(
                f"  ✗ FAILED "
                f"{report.month_key}: "
                f"{exc}"
            )

            failed.append(
                report.month_key
            )

            # Important:
            # continue processing other months.
            continue

        # Courtesy delay.
        time.sleep(0.5)

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "INGESTION COMPLETE"
    )
    print("=" * 70)

    print(
        f"Successful months: "
        f"{successful}/{len(months)}"
    )

    if failed:

        print()
        print(
            "Failed months:"
        )

        for month in failed:

            print(
                f"  - {month}"
            )

        print()
        print(
            "Successful data has been preserved. "
            "Rerun the pipeline after fixing "
            "the failed months."
        )

    if OUTPUT_FILE.exists():

        final_df = pd.read_csv(
            OUTPUT_FILE
        )

        print()
        print(
            f"Final rows: "
            f"{len(final_df):,}"
        )

        print(
            f"Unique report dates: "
            f"{final_df['date'].nunique():,}"
        )

        print(
            f"Unique constituents: "
            f"{final_df['symbol'].nunique():,}"
        )

        print()
        print(
            f"Output: "
            f"{OUTPUT_FILE}"
        )


if __name__ == "__main__":
    main()