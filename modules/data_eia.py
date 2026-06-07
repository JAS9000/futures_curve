# data_eia.py
# Fetches the weekly U.S. crude oil inventory series from the EIA Open Data
# API. Only used for research question 2.
# Get a free API key from https://www.eia.gov/opendata/register.php


import os
import time

import pandas as pd
import requests

import config


# Build the path where the cached data file lives
def cache_path():
    return os.path.join(config.CACHE_DIR, "eia_inventory.parquet")


# Decide whether the cached file is recent enough to use
def cache_fresh(path):
    if not os.path.exists(path):
        return False
    # File age in hours
    age_seconds = time.time() - os.path.getmtime(path)
    age_hours = age_seconds / 3600
    return age_hours < config.CACHE_MAX_AGE_HOURS


# Build the EIA inventory endpoint URL
def inventory_url():
    return f"{config.EIA_API_BASE}/{config.INVENTORY_ROUTE}/data/"


# Pull the inventory series from EIA. Returns a pandas Series or None
# if anything went wrong (no key, no internet, rate limited, etc.).
def fetch_inventory(api_key):
    # If no key was given, just return None - the app handles that
    if not api_key or api_key.strip() in ("", "paste_your_key_here"):
        return None

    # If the cached file is recent enough, use that. The read is wrapped in a
    # try/except so a damaged cache file can never crash the app: if reading
    # fails we simply fall through and fetch the data again from the EIA.
    path = cache_path()
    if cache_fresh(path):
        try:
            return pd.read_parquet(path)["value"]
        except Exception:
            pass

    # EIA returns max 5000 rows per request, so we have to page through
    all_rows = []
    offset = 0
    batch_size = 5000

    while True:
        params = {
            "api_key": api_key,
            "frequency": "weekly",
            "data[0]": "value",
            "facets[series][]": config.INVENTORY_SERIES,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "offset": offset,
            "length": batch_size,
        }
        try:
            response = requests.get(inventory_url(), params=params, timeout=30)
        except requests.RequestException:
            return None
        if response.status_code != 200:
            return None

        # The JSON payload puts the rows under response.data
        batch = response.json().get("response", {}).get("data", [])
        if not batch:
            break
        all_rows.extend(batch)
        # If we got less than a full batch, we've reached the end
        if len(batch) < batch_size:
            break
        offset += batch_size

    if not all_rows:
        return None

    # Turn the list of dicts into a clean pandas Series
    df = pd.DataFrame(all_rows)
    df["period"] = pd.to_datetime(df["period"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"]).sort_values("period")
    series = df.set_index("period")["value"].rename("value")

    # Save to disk so we don't have to refetch within CACHE_MAX_AGE_HOURS
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    series.to_frame().to_parquet(path)
    return series


# Quick connection test that returns (ok, message).
# Called once at startup so the sidebar can show the status.
def test_connection(api_key):
    if not api_key or api_key.strip() in ("", "paste_your_key_here"):
        return False, "No EIA key configured. Question 2 will be skipped."
    try:
        # Just ask for 1 row to see if the key works
        params = {
            "api_key": api_key,
            "frequency": "weekly",
            "data[0]": "value",
            "facets[series][]": config.INVENTORY_SERIES,
            "length": 1,
        }
        response = requests.get(inventory_url(), params=params, timeout=15)
    except requests.RequestException:
        return False, "Could not reach EIA."

    if response.status_code in (401, 403):
        return False, "EIA key rejected. Re-copy your key from the email."
    if response.status_code == 429:
        return False, "EIA rate limited. Try again in a few minutes."
    if response.status_code != 200:
        return False, f"EIA returned an error (HTTP {response.status_code})."

    data = response.json().get("response", {}).get("data", [])
    if not data:
        return False, "EIA reachable but returned no data."

    return True, "EIA key valid. Live inventory data in use."
