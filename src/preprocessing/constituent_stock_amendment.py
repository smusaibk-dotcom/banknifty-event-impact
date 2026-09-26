import yfinance as yf
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 1. Define your parameters
# Add standard tickers. For international markets, add extensions (e.g., "RELIANCE.NS" for India)
STOCK_TICKERS = ["HDFCBANK.NS", 'KOTAKBANK.NS','SBIN.NS','AUBANK.NS','AXISBANK.NS','CANBK.NS','ICICIBANK.NS','IDFCFIRSTB.NS','INDUSINDBK.NS','PNB.NS','UNIONBANK.NS','YESBANK.NS','BANDHANBNK.NS','BANKBARODA.NS','FEDERALBNK.NS'] 
START_DATE = "2023-01-01"
END_DATE = "2026-09-01"

OUTPUT_FILE= (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "constituent_stocks_data.csv"
)

def extract_stock_data(tickers, start, end, output_path):
    print(f" Initializing extraction for: {', '.join(tickers)}...")
    
    # Download data from the API
    raw_data = yf.download(tickers, start=start, end=end, group_by='ticker')
    
    all_stocks_df = []
    
    # Restructure multi-index tables to a clean row-by-row structure
    for ticker in tickers:
        if ticker in raw_data.columns.levels[0]:
            ticker_df = raw_data[ticker].copy()

            if ticker_df.empty:
                print(f"NO DATA FOUND !! for {ticker}")
                continue
            ticker_df['Ticker'] = ticker
            ticker_df = ticker_df.reset_index()
            # Retain only the necessary columns requested
            ticker_df = ticker_df[['Date', 'Ticker', 'Open', 'High', 'Low', 'Close', 'Volume']]
            all_stocks_df.append(ticker_df)
            
    if all_stocks_df:
        # Merge all data into one master sheet
        final_df = pd.concat(all_stocks_df, ignore_index=True)
        
        # Save to CSV
        final_df.to_csv(output_path, index=False)
        print(f" Extraction successful! Saved data file to: '{output_path}'")
    else:
        print(" No data could be retrieved for the specified tickers.")

# Execute automation
extract_stock_data(STOCK_TICKERS, START_DATE, END_DATE, OUTPUT_FILE)
