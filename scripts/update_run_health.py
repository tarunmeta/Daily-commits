"""
update_run_health.py

Counts today's commits from auto-commits.log and writes run_health.json.
"""

import json
import os
from datetime import datetime, UTC
from zoneinfo import ZoneInfo

DATA_DIR = "data"
LOG_PATH = os.path.join(DATA_DIR, "auto-commits.log")
OUTPUT_PATH = os.path.join(DATA_DIR, "run_health.json")
TARGET_PER_DAY = 100


def count_today_commits(today_ist: str) -> int:
    if not os.path.exists(LOG_PATH):
        return 0
    count = 0
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith(f"{today_ist} |"):
                count += 1
    return count


def count_streak() -> int:
    """Count consecutive days with at least 1 commit."""
    if not os.path.exists(LOG_PATH):
        return 0

    from collections import defaultdict
    from datetime import date, timedelta

    counts = defaultdict(int)
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(" | ")
            if len(parts) >= 1:
                counts[parts[0]] += 1

    today = datetime.now(tz=ZoneInfo("Asia/Kolkata")).date()
    streak = 0
    check = today
    while str(check) in counts:
        streak += 1
        check -= timedelta(days=1)
    return streak


def update_run_health() -> None:
    now_utc = datetime.now(UTC)
    now_ist = now_utc.astimezone(ZoneInfo("Asia/Kolkata"))
    today_ist = now_ist.strftime("%Y-%m-%d")

    commits_today = count_today_commits(today_ist)
    streak = count_streak()

    payload = {
        "last_run_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "last_run_ist": now_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        "date_ist": today_ist,
        "target_commits_per_day": TARGET_PER_DAY,
        "commits_today": commits_today,
        "remaining_today": max(TARGET_PER_DAY - commits_today, 0),
        "status": "target-reached" if commits_today >= TARGET_PER_DAY else "on-track",
        "streak_days": streak,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)

    print(f"Run health updated. Commits today: {commits_today}, Streak: {streak} days.")


if __name__ == "__main__":
    update_run_health()