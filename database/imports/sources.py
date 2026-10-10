"""Downloads from OpenStreetMap (Overpass API) and Open Charge Map, with a local cache.

Every response is saved under data/raw/ (git-ignored). Re-running an import reads the
cached file instead of downloading again, which is polite to these free services and
makes imports repeatable. Pass refresh=True (or --refresh on the scripts) to re-download.
"""

import json
import os
import time

import requests

from database.common import RAW_DIR

USER_AGENT = "ChargeSpot/0.1 (college final-year project; station data import)"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OCM_URL = "https://api.openchargemap.io/v3/poi"


def _cached(cache_name: str, refresh: bool, download) -> dict | list:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{cache_name}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    data = download()
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def _get_with_retries(method: str, url: str, attempts: int = 4, **kwargs) -> requests.Response:
    """Free APIs rate-limit; wait and retry on 429/5xx instead of failing straight away."""
    for attempt in range(1, attempts + 1):
        response = requests.request(method, url, headers={"User-Agent": USER_AGENT}, timeout=180, **kwargs)
        if response.status_code == 200:
            return response
        if response.status_code in (429, 502, 503, 504) and attempt < attempts:
            wait = 15 * attempt
            print(f"  {url} answered {response.status_code}; retrying in {wait}s ...")
            time.sleep(wait)
            continue
        response.raise_for_status()
    raise RuntimeError("unreachable")


def overpass(query: str, cache_name: str, refresh: bool = False) -> dict:
    return _cached(cache_name, refresh, lambda: _get_with_retries("POST", OVERPASS_URL, data={"data": query}).json())


def open_charge_map(params: dict, cache_name: str, refresh: bool = False) -> list:
    key = os.getenv("OCM_API_KEY", "").strip()
    if not key:
        raise SystemExit("OCM_API_KEY is not set in backend/.env.")

    def download():
        full = {"output": "json", "compact": "false", "verbose": "false", "maxresults": 5000, **params, "key": key}
        return _get_with_retries("GET", OCM_URL, params=full).json()

    return _cached(cache_name, refresh, download)
