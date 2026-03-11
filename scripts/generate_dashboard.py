"""
generate_dashboard.py

Generates the main README.md dashboard.
Each run produces slightly different content based on live data,
making every commit genuinely different.
"""

import json
import os
from datetime import datetime, UTC
from collections import defaultdict


DATA_DIR = "data"


def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def load_run_health():
    return load_json(os.path.join(DATA_DIR, "run_health.json")) or {}


def load_commit_stats():
    """Parse auto-commits.log and return per-day counts for last 7 days."""
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

    # Return last 7 days sorted
    sorted_days = sorted(counts.items())[-7:]
    return dict(sorted_days)


def make_mini_bar(count, target=100):
    """Make a simple ASCII progress bar."""
    filled = int((count / target) * 20)
    bar = "█" * filled + "░" * (20 - filled)
    pct = int((count / target) * 100)
    return f"`{bar}` {pct}%"


def generate_dashboard():
    github_repos = load_json(os.path.join(DATA_DIR, "github_trending.json")) or []
    crypto_data = load_json(os.path.join(DATA_DIR, "crypto.json")) or {}
    hacker_news = load_json(os.path.join(DATA_DIR, "hacker_news.json")) or []
    run_health = load_run_health()
    commit_stats = load_commit_stats()

    now_utc = datetime.now(UTC)
    now_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

    content = []

    # ── Header ──────────────────────────────────────────────
    content.append("# 🧠 Daily Intelligence Engine\n")
    content.append("> Auto-updated dashboard tracking tech trends, crypto markets, and dev news.\n")
    content.append(f"**Last Updated:** `{now_str}`\n")

    # ── Quick summary line ───────────────────────────────────
    summary_parts = []
    if github_repos:
        summary_parts.append(f"🔥 Top repo: **{github_repos[0]['name']}**")
    if crypto_data.get("bitcoin"):
        btc = crypto_data["bitcoin"]
        arrow = "↑" if btc.get("change_24h", 0) >= 0 else "↓"
        summary_parts.append(f"₿ BTC: **${btc['price_usd']:,}** {arrow}")
    if hacker_news:
        summary_parts.append(f"📰 HN Top: **{hacker_news[0]['title'][:50]}...**")

    if summary_parts:
        content.append("## 📌 Today at a Glance\n")
        for part in summary_parts:
            content.append(f"- {part}")
        content.append("")

    # ── Run Health ───────────────────────────────────────────
    content.append("## 🩺 Engine Health\n")
    if run_health:
        commits_today = run_health.get("commits_today", 0)
        target = run_health.get("target_commits_per_day", 100)
        status = run_health.get("status", "unknown")
        status_emoji = "✅" if status == "target-reached" else "🔄"

        content.append(f"| Metric | Value |")
        content.append(f"| :--- | :--- |")
        content.append(f"| Last Run (IST) | `{run_health.get('last_run_ist', 'N/A')}` |")
        content.append(f"| Commits Today | {commits_today} / {target} |")
        content.append(f"| Progress | {make_mini_bar(commits_today, target)} |")
        content.append(f"| Status | {status_emoji} {status} |")
        content.append("")
    else:
        content.append("_Health data unavailable._\n")

    # ── 7-Day Activity ───────────────────────────────────────
    if commit_stats:
        content.append("## 📆 Last 7 Days Activity\n")
        content.append("| Date | Commits | Progress |")
        content.append("| :--- | :--- | :--- |")
        for date, count in sorted(commit_stats.items()):
            bar = make_mini_bar(count)
            content.append(f"| {date} | {count} | {bar} |")
        content.append("")

    # ── Crypto ───────────────────────────────────────────────
    content.append("## 💰 Crypto Snapshot\n")
    if crypto_data:
        content.append("| Asset | Price (USD) | 24h Change | Trend |")
        content.append("| :--- | ---: | ---: | :---: |")
        for asset, stats in crypto_data.items():
            price = stats.get("price_usd", 0)
            change = stats.get("change_24h", 0)
            trend = "🟢" if change >= 0 else "🔴"
            change_str = f"{change:+.2f}%"
            content.append(f"| {asset.capitalize()} | ${price:,} | {change_str} | {trend} |")
        content.append("")
    else:
        content.append("_Crypto data unavailable._\n")

    # ── GitHub Trending ──────────────────────────────────────
    content.append("## 🚀 Top Trending Repositories\n")
    if github_repos:
        content.append("| Repository | Language | ⭐ Today | About |")
        content.append("| :--- | :--- | ---: | :--- |")
        for repo in github_repos[:8]:
            name = repo["name"]
            url = f"https://github.com/{name}"
            desc = repo.get("description", "")
            short_desc = desc[:80] + "…" if len(desc) > 80 else desc
            lang = repo.get("language", "—")
            stars = repo.get("stars_today", "—")
            content.append(f"| [{name}]({url}) | {lang} | {stars} | {short_desc} |")
        content.append("")
    else:
        content.append("_GitHub trending data unavailable._\n")

    # ── Hacker News ──────────────────────────────────────────
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
        content.append("_Hacker News data unavailable._\n")

    # ── Footer ───────────────────────────────────────────────
    content.append("---")
    content.append("> 🤖 This dashboard is auto-generated. Data refreshes 4× daily (00/06/12/18 UTC). Crypto & news update hourly.")
    content.append("> 📚 See [learning_log.md](data/learning_log.md) for daily notes on repos explored.")

    # Write README
    readme_path = "README.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("\n".join(content) + "\n")

    print("README.md dashboard generated successfully.")


if __name__ == "__main__":
    generate_dashboard()