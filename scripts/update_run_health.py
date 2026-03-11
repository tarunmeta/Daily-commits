"""
update_run_health.py

Builds run_health.json from real repository state:
- git history for commit counts/streak
- source metadata from data snapshots
"""

import argparse
import json
import os
import subprocess
from collections import defaultdict
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

DATA_DIR = "data"
LOG_PATH = os.path.join(DATA_DIR, "auto-commits.log")
OUTPUT_PATH = os.path.join(DATA_DIR, "run_health.json")
TARGET_PER_DAY = 100
IST = ZoneInfo("Asia/Kolkata")


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_utc_label(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=UTC)
    except ValueError:
        return None


def parse_commit_iso(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def git_output(args):
    cmd = ["git", *args]
    output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
    return output.strip()


def ist_day_bounds_utc(day_ist):
    start_ist = datetime.combine(day_ist, time.min, tzinfo=IST)
    end_ist = start_ist + timedelta(days=1)
    return start_ist.astimezone(UTC), end_ist.astimezone(UTC)


def count_today_commits_git(today_ist):
    start_utc, end_utc = ist_day_bounds_utc(today_ist)
    output = git_output(
        [
            "log",
            "--no-merges",
            "--since",
            start_utc.isoformat(),
            "--before",
            end_utc.isoformat(),
            "--pretty=%H",
        ]
    )
    return len([line for line in output.splitlines() if line.strip()])


def commit_dates_ist_from_git(limit=1000):
    output = git_output(["log", "--no-merges", "--pretty=%cI", "-n", str(limit)])
    dates = set()
    for line in output.splitlines():
        parsed = parse_commit_iso(line.strip())
        if parsed is not None:
            dates.add(parsed.astimezone(IST).date())
    return dates


def count_streak_from_git(today_ist):
    dates = commit_dates_ist_from_git()
    streak = 0
    cursor = today_ist
    while cursor in dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def last_commit_times_from_git():
    output = git_output(["log", "-1", "--no-merges", "--pretty=%cI"])
    if not output:
        return None, None
    parsed = parse_commit_iso(output)
    if parsed is None:
        return None, None
    utc_text = parsed.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    ist_text = parsed.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    return utc_text, ist_text


def count_today_commits_log(today_ist):
    if not os.path.exists(LOG_PATH):
        return 0
    today_text = today_ist.strftime("%Y-%m-%d")
    count = 0
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith(f"{today_text} |"):
                count += 1
    return count


def count_streak_log(today_ist):
    if not os.path.exists(LOG_PATH):
        return 0
    counts = defaultdict(int)
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(" | ")
            if not parts:
                continue
            counts[parts[0]] += 1

    streak = 0
    cursor = today_ist
    while cursor.isoformat() in counts:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def extract_source_details(payload, source_type):
    if source_type == "github":
        if isinstance(payload, dict) and isinstance(payload.get("repos"), list):
            return payload.get("repos", []), payload.get("meta", {}) or {}
        if isinstance(payload, list):
            return payload, {}
        return [], {}

    if source_type == "hn":
        if isinstance(payload, dict) and isinstance(payload.get("stories"), list):
            return payload.get("stories", []), payload.get("meta", {}) or {}
        if isinstance(payload, list):
            return payload, {}
        return [], {}

    if source_type == "crypto":
        if isinstance(payload, dict) and isinstance(payload.get("assets"), dict):
            return payload.get("assets", {}), payload.get("meta", {}) or {}
        if isinstance(payload, dict):
            return payload, {}
        return {}, {}

    return [], {}


def source_summary(label, filename, source_type):
    path = os.path.join(DATA_DIR, filename)
    payload = load_json(path)
    content, meta = extract_source_details(payload, source_type)

    if isinstance(content, list):
        count = len(content)
    elif isinstance(content, dict):
        count = len(content)
    else:
        count = 0

    content_hash = meta.get("content_hash", "")
    hash_short = content_hash[:12] if content_hash else ""

    if source_type == "github":
        change_summary = f"+{meta.get('new_repos_vs_previous', 0)} new repos"
        change_flag = bool(meta.get("new_repos_vs_previous", 0) or meta.get("top_repo_changed", False))
    elif source_type == "hn":
        change_summary = f"+{meta.get('new_story_ids_vs_previous', 0)} new stories"
        change_flag = bool(meta.get("new_story_ids_vs_previous", 0) or meta.get("top_story_changed", False))
    else:
        change_summary = f"{meta.get('assets_changed_vs_previous', 0)} assets moved"
        change_flag = bool(meta.get("assets_changed_vs_previous", 0))

    return {
        "label": label,
        "item_count": int(meta.get("item_count", meta.get("asset_count", count)) or count),
        "last_fetch_utc": meta.get("fetched_at_utc", ""),
        "last_fetch_ist": meta.get("fetched_at_ist", ""),
        "content_hash": content_hash,
        "content_hash_short": hash_short,
        "change_flag": change_flag,
        "change_summary": change_summary,
    }


def latest_data_timestamp(sources):
    timestamps = []
    for details in sources.values():
        parsed = parse_utc_label(details.get("last_fetch_utc", ""))
        if parsed:
            timestamps.append(parsed)
    if not timestamps:
        return "", ""
    latest = max(timestamps)
    return latest.strftime("%Y-%m-%d %H:%M:%S UTC"), latest.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S IST")


def update_run_health(pending_commit=0):
    today_ist = datetime.now(tz=IST).date()

    commit_source = "git-history"
    try:
        commits_today = count_today_commits_git(today_ist)
        streak = count_streak_from_git(today_ist)
        last_commit_utc, last_commit_ist = last_commit_times_from_git()
    except Exception:
        commit_source = "auto-commits-log"
        commits_today = count_today_commits_log(today_ist)
        streak = count_streak_log(today_ist)
        last_commit_utc, last_commit_ist = "", ""

    pending_commit = max(int(pending_commit), 0)
    commits_today += pending_commit

    if commits_today >= TARGET_PER_DAY:
        status = "target-reached"
    elif commits_today == 0:
        status = "idle"
    else:
        status = "on-track"

    sources = {
        "github": source_summary("GitHub Trending", "github_trending.json", "github"),
        "hacker_news": source_summary("Hacker News", "hacker_news.json", "hn"),
        "crypto": source_summary("Crypto", "crypto.json", "crypto"),
    }
    last_data_update_utc, last_data_update_ist = latest_data_timestamp(sources)

    payload = {
        "schema_version": 2,
        "date_ist": today_ist.isoformat(),
        "target_commits_per_day": TARGET_PER_DAY,
        "commits_today": commits_today,
        "remaining_today": max(TARGET_PER_DAY - commits_today, 0),
        "status": status,
        "streak_days": streak,
        "commit_count_source": commit_source,
        "pending_commit_included": pending_commit,
        "last_commit_utc": last_commit_utc,
        "last_commit_ist": last_commit_ist,
        "last_data_update_utc": last_data_update_utc,
        "last_data_update_ist": last_data_update_ist,
        "sources": sources,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(
        "Run health updated. "
        f"Commits today: {commits_today}, streak: {streak}, source: {commit_source}."
    )


def main():
    parser = argparse.ArgumentParser(description="Update run health metrics.")
    parser.add_argument(
        "--pending-commit",
        type=int,
        default=0,
        help="Include N pending commit(s) in today's count before writing health.",
    )
    args = parser.parse_args()
    update_run_health(pending_commit=args.pending_commit)


if __name__ == "__main__":
    main()
