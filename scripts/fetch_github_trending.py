import hashlib
import json
import os
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

DATA_DIR = "data"
OUTPUT_PATH = os.path.join(DATA_DIR, "github_trending.json")
SOURCE_URL = "https://github.com/trending"
REQUEST_TIMEOUT = 15
IST = ZoneInfo("Asia/Kolkata")


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_previous(payload):
    if isinstance(payload, dict) and isinstance(payload.get("repos"), list):
        return payload.get("repos", []), payload.get("meta", {}) or {}
    if isinstance(payload, list):
        return payload, {}
    return [], {}


def hash_payload(data):
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_space(value):
    return " ".join(str(value).split()).strip()


def parse_trending_repos(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    repos = []

    for article in soup.select("article.Box-row"):
        repo_name_tag = article.select_one("h2 a")
        if not repo_name_tag:
            continue

        repo_name = normalize_space(repo_name_tag.get_text()).replace(" / ", "/").replace(" ", "")
        description_tag = article.select_one("p.col-9")
        language_tag = article.select_one('[itemprop="programmingLanguage"]')
        stars_today_tag = article.select_one("span.d-inline-block.float-sm-right")

        repos.append(
            {
                "name": repo_name,
                "description": normalize_space(description_tag.get_text()) if description_tag else "No description",
                "language": normalize_space(language_tag.get_text()) if language_tag else "Unknown",
                "stars_today": normalize_space(stars_today_tag.get_text()) if stars_today_tag else "0 stars today",
            }
        )

    return repos


def build_snapshot(repos, previous_repos, previous_meta):
    now_utc = datetime.now(UTC)
    now_ist = now_utc.astimezone(IST)

    content_hash = hash_payload(repos)
    previous_hash = previous_meta.get("content_hash") or (hash_payload(previous_repos) if previous_repos else "")

    previous_names = {repo.get("name", "") for repo in previous_repos}
    current_names = {repo.get("name", "") for repo in repos}
    previous_top = previous_repos[0].get("name") if previous_repos else None
    current_top = repos[0].get("name") if repos else None

    return {
        "meta": {
            "schema_version": 2,
            "source_url": SOURCE_URL,
            "fetched_at_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "fetched_at_ist": now_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
            "item_count": len(repos),
            "content_hash": content_hash,
            "previous_hash": previous_hash,
            "new_repos_vs_previous": len(current_names - previous_names),
            "top_repo_changed": previous_top != current_top if previous_top and current_top else bool(current_top),
        },
        "repos": repos,
    }


def fetch_trending_repos():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
        )
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    previous_payload = load_json(OUTPUT_PATH)
    previous_repos, previous_meta = extract_previous(previous_payload)

    try:
        response = requests.get(SOURCE_URL, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        repos = parse_trending_repos(response.text)
        if not repos:
            raise RuntimeError("Parsed zero repositories from GitHub trending page.")
    except Exception as exc:
        print(f"Error fetching GitHub trending repos: {exc}")
        return False

    new_hash = hash_payload(repos)
    old_hash = previous_meta.get("content_hash") or (hash_payload(previous_repos) if previous_repos else "")
    if old_hash and new_hash == old_hash:
        print("GitHub trending unchanged; snapshot not rewritten.")
        return False

    payload = build_snapshot(repos, previous_repos, previous_meta)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(
        "Updated GitHub trending snapshot: "
        f"{len(repos)} repos, hash {payload['meta']['content_hash'][:12]}."
    )
    return True


if __name__ == "__main__":
    fetch_trending_repos()
