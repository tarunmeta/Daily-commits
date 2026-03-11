"""
generate_dashboard.py

Generates the main README.md dashboard.
The output is content-driven: README only changes when underlying signals change.
"""

import json
import os
import subprocess
from collections import defaultdict
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo


DATA_DIR = "data"
README_PATH = "README.md"
IST = ZoneInfo("Asia/Kolkata")


def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def load_run_health():
    return load_json(os.path.join(DATA_DIR, "run_health.json")) or {}


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


def short_hash(meta):
    content_hash = str(meta.get("content_hash", "") or "")
    return content_hash[:12] if content_hash else "n/a"


def source_count(content):
    if isinstance(content, list):
        return len(content)
    if isinstance(content, dict):
        return len(content)
    return 0


def source_change_text(kind, meta):
    if kind == "github":
        new_count = int(meta.get("new_repos_vs_previous", 0) or 0)
        top_changed = "yes" if meta.get("top_repo_changed", False) else "no"
        return f"+{new_count} new repos, top changed: {top_changed}"

    if kind == "hn":
        new_count = int(meta.get("new_story_ids_vs_previous", 0) or 0)
        top_changed = "yes" if meta.get("top_story_changed", False) else "no"
        return f"+{new_count} new stories, top changed: {top_changed}"

    moved = int(meta.get("assets_changed_vs_previous", 0) or 0)
    mover = str(meta.get("largest_move_asset", "") or "n/a")
    return f"{moved} assets moved, biggest mover: {mover}"


def git_output(args):
    output = subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL, text=True)
    return output.strip()


def count_commits_for_day_git(day_ist):
    start_ist = datetime.combine(day_ist, time.min, tzinfo=IST)
    end_ist = start_ist + timedelta(days=1)
    output = git_output(
        [
            "log",
            "--no-merges",
            "--since",
            start_ist.astimezone(UTC).isoformat(),
            "--before",
            end_ist.astimezone(UTC).isoformat(),
            "--pretty=%H",
        ]
    )
    return len([line for line in output.splitlines() if line.strip()])


def load_commit_stats_from_git(days=7):
    today_ist = datetime.now(tz=IST).date()
    stats = {}
    for offset in range(days - 1, -1, -1):
        day = today_ist - timedelta(days=offset)
        stats[day.isoformat()] = count_commits_for_day_git(day)
    return stats


def load_commit_stats_from_log(days=7):
    """Fallback parser for auto-commits.log."""
    log_path = os.path.join(DATA_DIR, "auto-commits.log")
    if not os.path.exists(log_path):
        return {}

    counts = defaultdict(int)
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(" | ")
            if len(parts) >= 2:
                date = parts[0]
                counts[date] += 1

    sorted_days = sorted(counts.items())[-days:]
    return dict(sorted_days)


def load_commit_stats(days=7):
    try:
        return load_commit_stats_from_git(days=days)
    except Exception:
        return load_commit_stats_from_log(days=days)


def make_mini_bar(count, target=100):
    """Make a simple ASCII progress bar."""
    target = max(int(target or 0), 1)
    ratio = min(max(count / target, 0), 1)
    filled = int(ratio * 20)
    bar = "█" * filled + "░" * (20 - filled)
    pct = int(ratio * 100)
    return f"`{bar}` {pct}%"


def generate_dashboard():
    github_payload = load_json(os.path.join(DATA_DIR, "github_trending.json")) or []
    crypto_payload = load_json(os.path.join(DATA_DIR, "crypto.json")) or {}
    hacker_news_payload = load_json(os.path.join(DATA_DIR, "hacker_news.json")) or []

    github_repos, github_meta = parse_payload(github_payload, "github")
    crypto_data, crypto_meta = parse_payload(crypto_payload, "crypto")
    hacker_news, hn_meta = parse_payload(hacker_news_payload, "hn")

    run_health = load_run_health()
    commit_stats = load_commit_stats()
    target = int(run_health.get("target_commits_per_day", 100) or 100)
    health_sources = run_health.get("sources", {}) if isinstance(run_health.get("sources"), dict) else {}
    pending_commit = int(run_health.get("pending_commit_included", 0) or 0)
    if pending_commit > 0:
        today_key = datetime.now(tz=IST).date().isoformat()
        if today_key in commit_stats:
            commit_stats[today_key] = int(commit_stats[today_key] or 0) + pending_commit

    last_updated = run_health.get("last_data_update_utc", "") or github_meta.get("fetched_at_utc", "")
    if not last_updated:
        candidates = [
            parse_utc_label(github_meta.get("fetched_at_utc", "")),
            parse_utc_label(hn_meta.get("fetched_at_utc", "")),
            parse_utc_label(crypto_meta.get("fetched_at_utc", "")),
        ]
        valid = [c for c in candidates if c]
        if valid:
            last_updated = max(valid).strftime("%Y-%m-%d %H:%M:%S UTC")
        else:
            last_updated = "Unavailable"

    content = []

    content.append("# ⚙️ Daily Automation Intelligence Engine\n")
    content.append("> Evidence-first dashboard powered by GitHub Trending, Hacker News, and CoinGecko snapshots.\n")
    content.append(f"**Last Meaningful Data Update (UTC):** `{last_updated}`")
    content.append(f"**Commit Policy:** `Commit only when tracked content changes`")
    content.append("")

    # Today at a glance
    summary_parts = []
    if github_repos:
        summary_parts.append(f"Top GitHub repo: **{github_repos[0].get('name', 'n/a')}**")
    if crypto_data.get("bitcoin"):
        btc = crypto_data["bitcoin"]
        change = float(btc.get("change_24h", 0) or 0)
        arrow = "↑" if change >= 0 else "↓"
        summary_parts.append(f"BTC: **${btc.get('price_usd', 0):,}** {arrow} ({change:+.2f}%)")
    if hacker_news:
        summary_parts.append(f"HN top story: **{hacker_news[0].get('title', 'n/a')}**")

    if summary_parts:
        content.append("## 📌 Today at a Glance\n")
        for part in summary_parts:
            content.append(f"- {part}")
        content.append("")

    # Data freshness/integrity
    content.append("## 🔐 Data Freshness and Integrity\n")
    content.append("| Source | Items | Last Fetch (UTC) | Hash | Change Summary |")
    content.append("| :--- | ---: | :--- | :--- | :--- |")

    gh_change = source_change_text("github", github_meta)
    hn_change = source_change_text("hn", hn_meta)
    cr_change = source_change_text("crypto", crypto_meta)

    content.append(
        f"| GitHub Trending | {source_count(github_repos)} | "
        f"{github_meta.get('fetched_at_utc', health_sources.get('github', {}).get('last_fetch_utc', 'Unknown'))} | "
        f"`{short_hash(github_meta)}` | {gh_change} |"
    )
    content.append(
        f"| Hacker News | {source_count(hacker_news)} | "
        f"{hn_meta.get('fetched_at_utc', health_sources.get('hacker_news', {}).get('last_fetch_utc', 'Unknown'))} | "
        f"`{short_hash(hn_meta)}` | {hn_change} |"
    )
    content.append(
        f"| Crypto | {source_count(crypto_data)} | "
        f"{crypto_meta.get('fetched_at_utc', health_sources.get('crypto', {}).get('last_fetch_utc', 'Unknown'))} | "
        f"`{short_hash(crypto_meta)}` | {cr_change} |"
    )
    content.append("")

    content.append("## 🧭 Change Summary\n")
    content.append(f"- GitHub: {gh_change}")
    content.append(f"- Hacker News: {hn_change}")
    content.append(f"- Crypto: {cr_change}")
    content.append("")

    # Run Health
    content.append("## 🩺 Engine Health\n")
    if run_health:
        commits_today = run_health.get("commits_today", 0)
        status = run_health.get("status", "unknown")
        streak = run_health.get("streak_days", 0)
        last_commit_ist = run_health.get("last_commit_ist", "N/A")
        count_source = run_health.get("commit_count_source", "unknown")
        status_icon = "✅" if status == "target-reached" else "🔄"

        content.append("| Metric | Value |")
        content.append("| :--- | :--- |")
        content.append(f"| Date (IST) | `{run_health.get('date_ist', 'N/A')}` |")
        content.append(f"| Commits Today | `{commits_today}` / `{target}` |")
        content.append(f"| Remaining Today | `{run_health.get('remaining_today', 'N/A')}` |")
        content.append(f"| Progress | {make_mini_bar(int(commits_today or 0), target)} |")
        content.append(f"| Streak | `{streak}` day(s) |")
        content.append(f"| Last Commit (IST) | `{last_commit_ist}` |")
        content.append(f"| Count Source | `{count_source}` |")
        content.append(f"| Status | {status_icon} `{status}` |")
        content.append("")
    else:
        content.append("_Health data unavailable._")
        content.append("")

    # 7-day activity
    if commit_stats:
        content.append("## 📆 Last 7 Days Activity\n")
        content.append("| Date | Commits | Progress |")
        content.append("| :--- | :--- | :--- |")
        for date, count in sorted(commit_stats.items()):
            bar = make_mini_bar(int(count or 0), target)
            content.append(f"| {date} | {count} | {bar} |")
        content.append("")

    # Crypto
    content.append("## 💰 Crypto Snapshot\n")
    if crypto_data:
        content.append("| Asset | Price (USD) | 24h Change | Trend |")
        content.append("| :--- | ---: | ---: | :---: |")
        for asset, stats in crypto_data.items():
            price = float(stats.get("price_usd", 0) or 0)
            change = float(stats.get("change_24h", 0) or 0)
            trend = "🟢" if change >= 0 else "🔴"
            change_str = f"{change:+.2f}%"
            content.append(f"| {asset.capitalize()} | ${price:,} | {change_str} | {trend} |")
        content.append("")
    else:
        content.append("_Crypto data unavailable._")
        content.append("")

    # GitHub Trending
    content.append("## 🚀 Top Trending Repositories\n")
    if github_repos:
        content.append("| Repository | Language | ⭐ Today | About |")
        content.append("| :--- | :--- | ---: | :--- |")
        for repo in github_repos[:8]:
            name = repo.get("name", "unknown/unknown")
            url = f"https://github.com/{name}"
            desc = str(repo.get("description", "") or "")
            short_desc = desc[:80] + "…" if len(desc) > 80 else desc
            lang = repo.get("language", "—")
            stars = repo.get("stars_today", "—")
            content.append(f"| [{name}]({url}) | {lang} | {stars} | {short_desc} |")
        content.append("")
    else:
        content.append("_GitHub trending data unavailable._")
        content.append("")

    # Hacker News
    content.append("## 📰 Top Hacker News Stories\n")
    if hacker_news:
        content.append("| Story | Score | 💬 |")
        content.append("| :--- | ---: | ---: |")
        for story in hacker_news[:5]:
            title = story.get("title", "Untitled")
            url = story.get("url", "#")
            score = story.get("score", 0)
            comments = story.get("comments", 0)
            content.append(f"| [{title}]({url}) | {score} | {comments} |")
        content.append("")
    else:
        content.append("_Hacker News data unavailable._")
        content.append("")

    # Footer
    content.append("---")
    content.append("> This README is generated by automation scripts in `scripts/`.")
    content.append("> See [data/learning_log.md](data/learning_log.md) for day-wise learning notes.")

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(content) + "\n")

    print("README.md dashboard generated successfully.")


if __name__ == "__main__":
    generate_dashboard()
