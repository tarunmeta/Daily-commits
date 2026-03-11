"""
update_learning_log.py

Automatically tracks what the intelligence engine fetched today
and maintains a running log of repos explored, topics seen, etc.
This makes commits genuinely meaningful — you can look back and see
what you learned each day.
"""

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

DATA_DIR = "data"
LOG_PATH = os.path.join(DATA_DIR, "learning_log.md")
GITHUB_DATA = os.path.join(DATA_DIR, "github_trending.json")
HN_DATA = os.path.join(DATA_DIR, "hacker_news.json")
CRYPTO_DATA = os.path.join(DATA_DIR, "crypto.json")


def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def get_today_ist():
    now = datetime.now(tz=ZoneInfo("Asia/Kolkata"))
    return now.strftime("%Y-%m-%d"), now.strftime("%H:%M")


def build_todays_entry(today: str, time_str: str) -> str:
    github = load_json(GITHUB_DATA) or []
    hn = load_json(HN_DATA) or []
    crypto = load_json(CRYPTO_DATA) or {}

    lines = [f"\n## 📅 {today} (last updated: {time_str} IST)\n"]

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
    today, time_str = get_today_ist()

    # Read existing log
    existing = ""
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            existing = f.read()

    todays_section_header = f"## 📅 {today}"

    new_entry = build_todays_entry(today, time_str)

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
            before = "\n".join(lines[:start_idx])
            after = "\n".join(lines[end_idx:])
            updated = before + new_entry + "\n" + after
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
        f.write(updated)

    print(f"Learning log updated for {today}.")


if __name__ == "__main__":
    update_log()