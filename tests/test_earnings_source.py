from __future__ import annotations

import io

import pandas as pd
import requests


URL = "https://www.investing.com/equities/axis-bank-earnings"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def main() -> None:
    print("=" * 70)
    print("INVESTING.COM EARNINGS SOURCE TEST")
    print("=" * 70)

    response = requests.get(
        URL,
        headers=HEADERS,
        timeout=30,
    )

    print(f"\nHTTP status : {response.status_code}")
    print(f"Response size: {len(response.text):,} characters")

    response.raise_for_status()

    tables = pd.read_html(
        io.StringIO(response.text)
    )

    print(f"\nHTML tables found: {len(tables)}")

    for i, table in enumerate(tables):

        print("\n" + "-" * 70)
        print(f"TABLE {i}")
        print("-" * 70)

        print("Columns:")
        print(list(table.columns))

        print("\nShape:")
        print(table.shape)

        print("\nFirst 5 rows:")
        print(table.head().to_string(index=False))


if __name__ == "__main__":
    main()