import hashlib
import json
import os
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import requests

DATA_DIR = "data"
OUTPUT_PATH = os.path.join(DATA_DIR, "hacker_news.json")
TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
REQUEST_TIMEOUT = 12
IST = ZoneInfo("Asia/Kolkata")


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_previous(payload):
    if isinstance(payload, dict) and isinstance(payload.get("stories"), list):
        return payload.get("stories", []), payload.get("meta", {}) or {}
    if isinstance(payload, list):
        return payload, {}
    return [], {}


def hash_payload(data):
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fetch_story_payloads():
    response = requests.get(TOP_STORIES_URL, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    top_ids = response.json()[:15]

    stories = []
    for story_id in top_ids:
        item_response = requests.get(ITEM_URL.format(item_id=story_id), timeout=REQUEST_TIMEOUT)
        item_response.raise_for_status()
        story = item_response.json() or {}
        if story.get("type") != "story":
            continue

        stories.append(
            {
                "id": story_id,
                "title": story.get("title", "Untitled"),
                "url": story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                "score": int(story.get("score", 0) or 0),
                "comments": int(story.get("descendants", 0) or 0),
            }
        )
        if len(stories) >= 5:
            break

    if not stories:
        raise RuntimeError("No HN stories parsed.")
    return stories


def build_snapshot(stories, previous_stories, previous_meta):
    now_utc = datetime.now(UTC)
    now_ist = now_utc.astimezone(IST)

    content_hash = hash_payload(stories)
    previous_hash = previous_meta.get("content_hash") or (hash_payload(previous_stories) if previous_stories else "")

    current_ids = {story.get("id") for story in stories}
    previous_ids = {story.get("id") for story in previous_stories}
    previous_top = previous_stories[0].get("id") if previous_stories else None
    current_top = stories[0].get("id") if stories else None

    return {
        "meta": {
            "schema_version": 2,
            "source_url": TOP_STORIES_URL,
            "fetched_at_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "fetched_at_ist": now_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
            "item_count": len(stories),
            "content_hash": content_hash,
            "previous_hash": previous_hash,
            "new_story_ids_vs_previous": len(current_ids - previous_ids),
            "top_story_changed": previous_top != current_top if previous_top and current_top else bool(current_top),
        },
        "stories": stories,
    }


def fetch_hacker_news_top():
    os.makedirs(DATA_DIR, exist_ok=True)
    previous_payload = load_json(OUTPUT_PATH)
    previous_stories, previous_meta = extract_previous(previous_payload)

    try:
        stories = fetch_story_payloads()
    except Exception as exc:
        print(f"Error fetching Hacker News data: {exc}")
        return False

    new_hash = hash_payload(stories)
    old_hash = previous_meta.get("content_hash") or (hash_payload(previous_stories) if previous_stories else "")
    if old_hash and new_hash == old_hash:
        print("Hacker News unchanged; snapshot not rewritten.")
        return False

    payload = build_snapshot(stories, previous_stories, previous_meta)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(
        "Updated Hacker News snapshot: "
        f"{len(stories)} stories, hash {payload['meta']['content_hash'][:12]}."
    )
    return True


if __name__ == "__main__":
    fetch_hacker_news_top()
