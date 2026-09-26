from pathlib import Path

import pandas as pd


def standardize_dataset(
    input_file: str | Path,
    output_file: str | Path,
    column_renames: dict[str, str] | None = None,
    date_columns: list[str] | None = None,
) -> pd.DataFrame:
    """
    Generic dataset standardization utility.

    Operations:
    - Standardize column names to lowercase.
    - Strip whitespace from column names.
    - Rename columns using an optional mapping.
    - Convert specified date columns to pandas datetime.
    - Save dates as YYYY-MM-DD when writing CSV.
    - Preserve all other columns and values.
    """

    input_file = Path(input_file)
    output_file = Path(output_file)

    # ---------------------------------------------------------
    # 1. Load
    # ---------------------------------------------------------

    df = pd.read_csv(input_file)

    # ---------------------------------------------------------
    # 2. Standardize column names
    # ---------------------------------------------------------

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
    )

    # ---------------------------------------------------------
    # 3. Standardize rename mapping
    # ---------------------------------------------------------

    if column_renames:
        column_renames = {
            old.strip().lower(): new.strip().lower()
            for old, new in column_renames.items()
        }

        df = df.rename(columns=column_renames)

    # ---------------------------------------------------------
    # 4. Convert date columns
    # ---------------------------------------------------------

    if date_columns:
        for column in date_columns:

            column = column.strip().lower()

            if column not in df.columns:
                raise ValueError(
                    f"Date column '{column}' not found. "
                    f"Available columns: {list(df.columns)}"
                )

            df[column] = pd.to_datetime(
                df[column],
                dayfirst=True
            )

    # ---------------------------------------------------------
    # 5. Save
    # ---------------------------------------------------------

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        output_file,
        index=False,
        date_format="%Y-%m-%d",
    )

    return df
