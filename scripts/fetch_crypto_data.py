import hashlib
import json
import os
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import requests

DATA_DIR = "data"
OUTPUT_PATH = os.path.join(DATA_DIR, "crypto.json")
SOURCE_URL = "https://api.coingecko.com/api/v3/simple/price"
REQUEST_TIMEOUT = 15
IST = ZoneInfo("Asia/Kolkata")
COINS = {
    "bitcoin": "bitcoin",
    "ethereum": "ethereum",
    "solana": "solana",
    "bnb": "binancecoin",
}


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_previous(payload):
    if isinstance(payload, dict) and isinstance(payload.get("assets"), dict):
        return payload.get("assets", {}), payload.get("meta", {}) or {}
    if isinstance(payload, dict):
        # Legacy format was already the asset dictionary.
        return payload, {}
    return {}, {}


def hash_payload(data):
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fetch_assets():
    params = {
        "ids": ",".join(COINS.values()),
        "vs_currencies": "usd",
        "include_24hr_change": "true",
    }
    response = requests.get(SOURCE_URL, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    data = response.json()

    snapshot = {}
    for alias, gecko_id in COINS.items():
        coin = data.get(gecko_id, {})
        if "usd" not in coin:
            raise RuntimeError(f"Missing USD price for {gecko_id}")
        snapshot[alias] = {
            "price_usd": float(coin["usd"]),
            "change_24h": float(coin.get("usd_24h_change") or 0.0),
        }
    return snapshot


def changed_assets_count(current_assets, previous_assets):
    changed = 0
    for name, stats in current_assets.items():
        prev = previous_assets.get(name, {})
        prev_price = float(prev.get("price_usd", 0.0) or 0.0)
        prev_change = float(prev.get("change_24h", 0.0) or 0.0)
        if round(stats["price_usd"], 6) != round(prev_price, 6) or round(stats["change_24h"], 6) != round(prev_change, 6):
            changed += 1
    return changed


def build_snapshot(assets, previous_assets, previous_meta):
    now_utc = datetime.now(UTC)
    now_ist = now_utc.astimezone(IST)

    content_hash = hash_payload(assets)
    previous_hash = previous_meta.get("content_hash") or (hash_payload(previous_assets) if previous_assets else "")

    largest_move_asset = max(assets.items(), key=lambda x: abs(x[1].get("change_24h", 0.0)))[0] if assets else ""
    largest_move_24h = assets.get(largest_move_asset, {}).get("change_24h", 0.0) if largest_move_asset else 0.0

    return {
        "meta": {
            "schema_version": 2,
            "source_url": SOURCE_URL,
            "fetched_at_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "fetched_at_ist": now_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
            "asset_count": len(assets),
            "content_hash": content_hash,
            "previous_hash": previous_hash,
            "assets_changed_vs_previous": changed_assets_count(assets, previous_assets),
            "largest_move_asset": largest_move_asset,
            "largest_move_24h": round(float(largest_move_24h), 4),
        },
        "assets": assets,
    }


def fetch_crypto_prices():
    os.makedirs(DATA_DIR, exist_ok=True)
    previous_payload = load_json(OUTPUT_PATH)
    previous_assets, previous_meta = extract_previous(previous_payload)

    try:
        assets = fetch_assets()
    except Exception as exc:
        print(f"Error fetching crypto data: {exc}")
        return False

    new_hash = hash_payload(assets)
    old_hash = previous_meta.get("content_hash") or (hash_payload(previous_assets) if previous_assets else "")
    if old_hash and new_hash == old_hash:
        print("Crypto prices unchanged; snapshot not rewritten.")
        return False

    payload = build_snapshot(assets, previous_assets, previous_meta)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(
        "Updated crypto snapshot: "
        f"{len(assets)} assets, hash {payload['meta']['content_hash'][:12]}."
    )
    return True


if __name__ == "__main__":
    fetch_crypto_prices()
