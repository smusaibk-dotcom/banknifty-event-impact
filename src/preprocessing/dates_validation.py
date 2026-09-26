import pandas as pd


def get_missing_dates(
        reference_df,
        target_df,
        reference_date_col,
        target_date_col
):

    reference_dates = set(
        pd.to_datetime(reference_df[reference_date_col])
    )

    target_dates = set(
        pd.to_datetime(target_df[target_date_col])
    )


    missing_dates = reference_dates - target_dates

    return sorted(list(missing_dates))