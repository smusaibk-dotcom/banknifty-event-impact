import pandas as pd


def remove_dates(
    df,
    dates,
    date_column
):
    """
    Remove specified dates from dataframe.

    Parameters:
    df: pandas DataFrame
    dates: list of dates to remove
    date_column: name of date column

    Returns:
    cleaned dataframe
    """

    df = df.copy()

    df[date_column] = pd.to_datetime(
        df[date_column]
    )

    dates = pd.to_datetime(dates)

    df = df[
        ~df[date_column].isin(dates)
    ]

    return df