from __future__ import annotations

import os
import requests


URL = "https://api.twelvedata.com/earnings"


def main() -> None:
    api_key = os.getenv("TWELVE_DATA_API_KEY")

    if not api_key:
        raise RuntimeError(
            "TWELVE_DATA_API_KEY is not set."
        )

    response = requests.get(
        URL,
        params={
            "symbol": "AXISBANK:NSE",
            "apikey": api_key,
        },
        timeout=30,
    )

    print("HTTP status:", response.status_code)

    data = response.json()

    if data.get("status") == "error":
        print("\nAPI ERROR:")
        print(data)
        return

    earnings = data.get("earnings", [])

    print("\nRecords:", len(earnings))

    for row in earnings:
        print(row)


if __name__ == "__main__":
    main()