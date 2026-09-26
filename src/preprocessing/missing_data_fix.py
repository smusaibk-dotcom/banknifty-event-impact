import yfinance as yf
import pandas as pd


def fetch_missing_data(ticker, missing_dates):

    if not missing_dates:
        return pd.DataFrame()


    missing_dates = pd.to_datetime(missing_dates)

    fetched_data = []


    for date in missing_dates:

        start_date = date
        end_date = date + pd.Timedelta(days=1)

        data = yf.download(
            ticker,
            start=start_date,
            end=end_date,
            auto_adjust=False,
            progress=False
        )


        if not data.empty:

            data = data.reset_index()

            data = data[
                data["Date"] == date
            ]

            fetched_data.append(data)


    if fetched_data:
        return pd.concat(
            fetched_data,
            ignore_index=True
        )


    return pd.DataFrame()