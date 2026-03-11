"""
update_learning_log.py

Automatically tracks what the intelligence engine fetched today
and maintains a running log of repos explored, topics seen, etc.
This makes commits genuinely meaningful — you can look back and see
what you learned each day.
"""

import json
import os
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

DATA_DIR = "data"
LOG_PATH = os.path.join(DATA_DIR, "learning_log.md")
GITHUB_DATA = os.path.join(DATA_DIR, "github_trending.json")
HN_DATA = os.path.join(DATA_DIR, "hacker_news.json")
CRYPTO_DATA = os.path.join(DATA_DIR, "crypto.json")
IST = ZoneInfo("Asia/Kolkata")


def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def get_today_ist():
    now = datetime.now(tz=IST)
    return now.strftime("%Y-%m-%d"), now.strftime("%H:%M")


def parse_payload(payload, kind):
    if kind == "github":
        if isinstance(payload, dict) and isinstance(payload.get("repos"), list):
            return payload.get("repos", []), payload.get("meta", {}) or {}
        if isinstance(payload, list):
            return payload, {}
        return [], {}

    if kind == "hn":
        if isinstance(payload, dict) and isinstance(payload.get("stories"), list):
            return payload.get("stories", []), payload.get("meta", {}) or {}
        if isinstance(payload, list):
            return payload, {}
        return [], {}

    if kind == "crypto":
        if isinstance(payload, dict) and isinstance(payload.get("assets"), dict):
            return payload.get("assets", {}), payload.get("meta", {}) or {}
        if isinstance(payload, dict):
            return payload, {}
        return {}, {}

    return [], {}


def parse_utc_label(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=UTC)
    except ValueError:
        return None


def resolve_entry_time_ist(*metas):
    timestamps = []
    for meta in metas:
        parsed = parse_utc_label(meta.get("fetched_at_utc", "") if isinstance(meta, dict) else "")
        if parsed:
            timestamps.append(parsed.astimezone(IST))
    if timestamps:
        latest = max(timestamps)
        return latest.strftime("%H:%M")
    return datetime.now(tz=IST).strftime("%H:%M")


def short_hash(meta):
    if not isinstance(meta, dict):
        return "n/a"
    content_hash = str(meta.get("content_hash", "") or "")
    return content_hash[:12] if content_hash else "n/a"


def source_item_count(content):
    if isinstance(content, list):
        return len(content)
    if isinstance(content, dict):
        return len(content)
    return 0


def source_change_summary(kind, meta):
    if not isinstance(meta, dict):
        return "legacy payload"

    if kind == "github":
        new_count = int(meta.get("new_repos_vs_previous", 0) or 0)
        top_changed = bool(meta.get("top_repo_changed", False))
        return f"+{new_count} new repos, top changed: {'yes' if top_changed else 'no'}"

    if kind == "hn":
        new_count = int(meta.get("new_story_ids_vs_previous", 0) or 0)
        top_changed = bool(meta.get("top_story_changed", False))
        return f"+{new_count} new stories, top changed: {'yes' if top_changed else 'no'}"

    moved = int(meta.get("assets_changed_vs_previous", 0) or 0)
    mover = str(meta.get("largest_move_asset", "") or "n/a")
    return f"{moved} assets moved, biggest mover: {mover}"


def build_todays_entry(today: str) -> str:
    github_payload = load_json(GITHUB_DATA) or []
    hn_payload = load_json(HN_DATA) or []
    crypto_payload = load_json(CRYPTO_DATA) or {}

    github, github_meta = parse_payload(github_payload, "github")
    hn, hn_meta = parse_payload(hn_payload, "hn")
    crypto, crypto_meta = parse_payload(crypto_payload, "crypto")
    time_str = resolve_entry_time_ist(github_meta, hn_meta, crypto_meta)

    lines = [f"\n## 📅 {today} (last updated: {time_str} IST)\n"]

    lines.append("### 🧪 Source Integrity Snapshot")
    lines.append("| Source | Items | Last Fetch (IST) | Hash | Change Signal |")
    lines.append("| :--- | ---: | :--- | :--- | :--- |")
    lines.append(
        f"| GitHub Trending | {source_item_count(github)} | "
        f"{github_meta.get('fetched_at_ist', 'Unknown')} | {short_hash(github_meta)} | "
        f"{source_change_summary('github', github_meta)} |"
    )
    lines.append(
        f"| Hacker News | {source_item_count(hn)} | "
        f"{hn_meta.get('fetched_at_ist', 'Unknown')} | {short_hash(hn_meta)} | "
        f"{source_change_summary('hn', hn_meta)} |"
    )
    lines.append(
        f"| Crypto | {source_item_count(crypto)} | "
        f"{crypto_meta.get('fetched_at_ist', 'Unknown')} | {short_hash(crypto_meta)} | "
        f"{source_change_summary('crypto', crypto_meta)} |"
    )
    lines.append("")

    lines.append("### 🔎 What Changed Since Previous Snapshot")
    lines.append(f"- GitHub: {source_change_summary('github', github_meta)}")
    lines.append(f"- Hacker News: {source_change_summary('hn', hn_meta)}")
    lines.append(f"- Crypto: {source_change_summary('crypto', crypto_meta)}")
    lines.append("")

    # Top repos
    if github:
        lines.append("### 🚀 Trending Repos Tracked Today")
        for repo in github[:5]:
            name = repo.get("name", "")
            desc = repo.get("description", "")[:80]
            lang = repo.get("language", "")
            stars = repo.get("stars_today", "")
            lines.append(f"- **[{name}](https://github.com/{name})** ({lang}) — {desc}  ")
            lines.append(f"  ⭐ {stars}")
        lines.append("")

    # HN stories
    if hn:
        lines.append("### 📰 Hacker News Stories")
        for story in hn[:5]:
            title = story.get("title", "")
            url = story.get("url", "#")
            score = story.get("score", 0)
            lines.append(f"- [{title}]({url}) — Score: {score}")
        lines.append("")

    # Crypto snapshot
    if crypto:
        lines.append("### 💰 Crypto at Time of Update")
        for coin, data in crypto.items():
            price = data.get("price_usd", 0)
            change = data.get("change_24h", 0)
            arrow = "🟢" if change >= 0 else "🔴"
            lines.append(f"- {coin.capitalize()}: ${price:,} {arrow} {change:+.2f}%")
        lines.append("")

    lines.append("---")
    return "\n".join(lines)


def update_log():
    today, _ = get_today_ist()

    # Read existing log
    existing = ""
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            existing = f.read()

    todays_section_header = f"## 📅 {today}"

    new_entry = build_todays_entry(today)

    if todays_section_header in existing:
        # Replace today's existing entry with updated one
        lines = existing.split("\n")
        # Find where today's section starts
        start_idx = None
        end_idx = len(lines)
        for i, line in enumerate(lines):
            if line.startswith(todays_section_header):
                start_idx = i
            elif start_idx is not None and line.startswith("## 📅") and i != start_idx:
                end_idx = i
                break

        if start_idx is not None:
            new_lines = lines[:start_idx] + new_entry.split("\n") + lines[end_idx:]
            updated = "\n".join(new_lines)
        else:
            updated = existing + new_entry
    else:
        # Prepend today's entry after the header
        header_end = existing.find("\n---\n")
        if header_end != -1:
            updated = existing[:header_end + 5] + new_entry + existing[header_end + 5:]
        else:
            # First time — create full file
            header = "# 📚 Daily Learning Log\n\nThis log tracks what I explored each day through the intelligence engine.\n\n---"
            updated = header + new_entry + existing

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write(updated.rstrip() + "\n")

    print(f"Learning log updated for {today}.")


if __name__ == "__main__":
    update_log()
