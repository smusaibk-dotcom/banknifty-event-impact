from __future__ import annotations

import json
import os

import requests


INSTRUMENT_ID = 18017

URL = (
    f"https://endpoints.investing.com/"
    f"earnings/v1/instruments/{INSTRUMENT_ID}/earnings"
)

CURSOR = (
    "eyJMaW1pdCI6MTAsIlByZXZSZXFZZWFyIjoyMDIxLCJQcmV2UmVxTW9uIjoxMn0"
)


def main() -> None:

    print("=" * 70)
    print("INVESTING.COM EARNINGS ENDPOINT TEST")
    print("=" * 70)

    token = os.getenv("INVESTING_BEARER_TOKEN")

    if not token:
        raise RuntimeError(
            "INVESTING_BEARER_TOKEN environment variable is not set."
        )

    headers = {
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Authorization": f"Bearer {token}",
        "Origin": "https://www.investing.com",
        "Referer": "https://www.investing.com/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/152.0.0.0 Safari/537.36"
        ),
    }

    params = {
        "limit": 10,

    }

    print(f"\nURL:\n{URL}")
    print(f"\nParameters:\n{params}")

    response = requests.get(
        URL,
        params=params,
        headers=headers,
        timeout=30,
    )

    print(f"\nHTTP status  : {response.status_code}")
    print(f"Response size: {len(response.content):,} bytes")

    print("\nResponse headers:")
    print(
        json.dumps(
            dict(response.headers),
            indent=2,
        )
    )

    response.raise_for_status()

    data = response.json()

    print("\nTop-level type:")
    print(type(data).__name__)

    if isinstance(data, dict):
        print("\nTop-level keys:")
        print(list(data.keys()))

    print("\nJSON response:")
    print(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()