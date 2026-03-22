"""
Revenue Tracking Dashboard

Tracks monetization metrics across platforms:
- Post counts and frequency analysis
- Content type performance (threads vs singles, batch vs individual)
- Engagement pattern detection (best days, times, cadence)
- Affiliate marketing tracking
- Cross-platform activity overview
"""

import os
import json
from datetime import datetime, timedelta
from typing import List, Optional
from collections import Counter

from config import ROOT_DIR, get_verbose
from cache import get_accounts, get_products, get_twitter_cache_path, get_youtube_cache_path, get_afm_cache_path
from status import info, success, warning


def _revenue_path() -> str:
    return os.path.join(ROOT_DIR, ".mp", "revenue.json")


def _load_revenue() -> dict:
    path = _revenue_path()
    if not os.path.exists(path):
        return {
            "affiliate_clicks": [],
            "affiliate_sales": [],
            "milestones": [],
        }
    with open(path, "r") as f:
        return json.load(f)


def _save_revenue(data: dict) -> None:
    with open(_revenue_path(), "w") as f:
        json.dump(data, f, indent=2)


# --- Affiliate Tracking ---

def log_affiliate_click(product_id: str, source: str = "twitter") -> None:
    """Log an affiliate link click."""
    data = _load_revenue()
    data["affiliate_clicks"].append({
        "product_id": product_id,
        "source": source,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    _save_revenue(data)


def log_affiliate_sale(product_id: str, amount: float, source: str = "twitter") -> None:
    """Log an affiliate sale/conversion."""
    data = _load_revenue()
    data["affiliate_sales"].append({
        "product_id": product_id,
        "amount": amount,
        "source": source,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    _save_revenue(data)


def log_milestone(description: str) -> None:
    """Log a notable milestone (e.g. first 100 posts, first sale)."""
    data = _load_revenue()
    data["milestones"].append({
        "description": description,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    _save_revenue(data)


# --- Analytics Functions ---

def _parse_twitter_date(date_str: str) -> Optional[datetime]:
    """Parse Twitter post date format: MM/DD/YYYY, HH:MM:SS"""
    try:
        return datetime.strptime(date_str, "%m/%d/%Y, %H:%M:%S")
    except (ValueError, TypeError):
        return None


def _parse_youtube_date(date_str: str) -> Optional[datetime]:
    """Parse YouTube video date format: YYYY-MM-DD HH:MM:SS"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def get_twitter_stats(account_id: Optional[str] = None) -> dict:
    """
    Get Twitter posting statistics.

    Returns dict with:
        total_posts, single_posts, threads, total_tweets_in_threads,
        posts_per_day, best_day, best_hour, days_active, avg_per_day,
        recent_posts (last 5), streak info
    """
    path = get_twitter_cache_path()
    if not os.path.exists(path):
        return {"total_posts": 0}

    with open(path, "r") as f:
        data = json.load(f)

    all_posts = []
    for account in data.get("accounts", []):
        if account_id and account["id"] != account_id:
            continue
        all_posts.extend(account.get("posts", []))

    if not all_posts:
        return {"total_posts": 0}

    threads = [p for p in all_posts if p.get("type") == "thread"]
    singles = len(all_posts) - len(threads)
    total_tweets_in_threads = sum(p.get("tweet_count", 1) for p in threads)

    # Parse dates for time analysis
    dates = []
    hours = []
    for p in all_posts:
        dt = _parse_twitter_date(p.get("date", ""))
        if dt:
            dates.append(dt.strftime("%Y-%m-%d"))
            hours.append(dt.hour)

    day_counts = Counter(dates)
    hour_counts = Counter(hours)

    best_day = day_counts.most_common(1)[0] if day_counts else (None, 0)
    best_hour = hour_counts.most_common(1)[0] if hour_counts else (None, 0)

    days_active = len(day_counts)
    avg_per_day = len(all_posts) / max(days_active, 1)

    # Streak calculation
    streak = _calculate_streak(sorted(set(dates)))

    # Recent posts
    recent = all_posts[-5:] if len(all_posts) >= 5 else all_posts

    return {
        "total_posts": len(all_posts),
        "single_posts": singles,
        "threads": len(threads),
        "total_tweets_in_threads": total_tweets_in_threads,
        "days_active": days_active,
        "avg_per_day": round(avg_per_day, 1),
        "best_day": {"date": best_day[0], "count": best_day[1]},
        "best_hour": {"hour": best_hour[0], "count": best_hour[1]},
        "streak": streak,
        "recent_posts": recent,
    }


def get_youtube_stats(account_id: Optional[str] = None) -> dict:
    """
    Get YouTube upload statistics.

    Returns dict with:
        total_videos, videos_per_day, best_day, days_active, avg_per_day,
        recent_videos (last 5), streak info
    """
    path = get_youtube_cache_path()
    if not os.path.exists(path):
        return {"total_videos": 0}

    with open(path, "r") as f:
        data = json.load(f)

    all_videos = []
    for account in data.get("accounts", []):
        if account_id and account["id"] != account_id:
            continue
        all_videos.extend(account.get("videos", []))

    if not all_videos:
        return {"total_videos": 0}

    dates = []
    for v in all_videos:
        dt = _parse_youtube_date(v.get("date", ""))
        if dt:
            dates.append(dt.strftime("%Y-%m-%d"))

    day_counts = Counter(dates)
    best_day = day_counts.most_common(1)[0] if day_counts else (None, 0)
    days_active = len(day_counts)
    avg_per_day = len(all_videos) / max(days_active, 1)

    streak = _calculate_streak(sorted(set(dates)))
    recent = all_videos[-5:] if len(all_videos) >= 5 else all_videos

    return {
        "total_videos": len(all_videos),
        "days_active": days_active,
        "avg_per_day": round(avg_per_day, 1),
        "best_day": {"date": best_day[0], "count": best_day[1]},
        "streak": streak,
        "recent_videos": recent,
    }


def get_affiliate_stats() -> dict:
    """Get affiliate marketing statistics."""
    data = _load_revenue()
    clicks = data.get("affiliate_clicks", [])
    sales = data.get("affiliate_sales", [])
    products = get_products()

    total_revenue = sum(s.get("amount", 0) for s in sales)

    # Clicks by source
    click_sources = Counter(c.get("source", "unknown") for c in clicks)
    sale_sources = Counter(s.get("source", "unknown") for s in sales)

    # Clicks per product
    clicks_per_product = Counter(c.get("product_id", "unknown") for c in clicks)

    return {
        "total_products": len(products),
        "total_clicks": len(clicks),
        "total_sales": len(sales),
        "total_revenue": round(total_revenue, 2),
        "clicks_by_source": dict(click_sources),
        "sales_by_source": dict(sale_sources),
        "clicks_per_product": dict(clicks_per_product),
        "conversion_rate": round(len(sales) / max(len(clicks), 1) * 100, 1),
    }


def _calculate_streak(sorted_dates: List[str]) -> dict:
    """Calculate current and longest posting streaks from sorted date strings."""
    if not sorted_dates:
        return {"current": 0, "longest": 0}

    today = datetime.now().strftime("%Y-%m-%d")
    current_streak = 0
    longest_streak = 0
    streak = 1

    for i in range(len(sorted_dates) - 1):
        d1 = datetime.strptime(sorted_dates[i], "%Y-%m-%d")
        d2 = datetime.strptime(sorted_dates[i + 1], "%Y-%m-%d")
        if (d2 - d1).days == 1:
            streak += 1
        else:
            longest_streak = max(longest_streak, streak)
            streak = 1

    longest_streak = max(longest_streak, streak)

    # Current streak (counting backwards from today)
    current_streak = 0
    check_date = datetime.now().date()
    date_set = set(sorted_dates)
    while check_date.strftime("%Y-%m-%d") in date_set:
        current_streak += 1
        check_date -= timedelta(days=1)

    return {"current": current_streak, "longest": longest_streak}


def get_queue_stats() -> dict:
    """Get content queue statistics."""
    queue_path = os.path.join(ROOT_DIR, ".mp", "content_queue.json")
    if not os.path.exists(queue_path):
        return {"twitter_queued": 0, "youtube_queued": 0}

    with open(queue_path, "r") as f:
        queue = json.load(f)

    tw_items = queue.get("twitter", [])
    yt_items = queue.get("youtube", [])

    return {
        "twitter_queued": len([i for i in tw_items if i["status"] == "queued"]),
        "twitter_posted": len([i for i in tw_items if i["status"] == "posted"]),
        "twitter_failed": len([i for i in tw_items if i["status"] == "failed"]),
        "youtube_queued": len([i for i in yt_items if i["status"] == "queued"]),
        "youtube_posted": len([i for i in yt_items if i["status"] == "posted"]),
        "youtube_failed": len([i for i in yt_items if i["status"] == "failed"]),
    }


def print_revenue_dashboard() -> None:
    """Print a comprehensive revenue and activity dashboard."""
    from termcolor import colored

    print()
    print(colored("=" * 60, "yellow"))
    print(colored("       MONETIZATION DASHBOARD", "yellow", attrs=["bold"]))
    print(colored("=" * 60, "yellow"))

    # Twitter Stats
    tw = get_twitter_stats()
    print(colored("\n  TWITTER / X", "blue", attrs=["bold"]))
    print(colored("  " + "-" * 40, "blue"))
    if tw["total_posts"] > 0:
        print(colored(f"  Total posts:        {tw['total_posts']}", "cyan"))
        print(colored(f"  Single tweets:      {tw['single_posts']}", "cyan"))
        print(colored(f"  Threads:            {tw['threads']}", "cyan"))
        if tw["threads"] > 0:
            print(colored(f"  Tweets in threads:  {tw['total_tweets_in_threads']}", "cyan"))
        print(colored(f"  Days active:        {tw['days_active']}", "cyan"))
        print(colored(f"  Avg posts/day:      {tw['avg_per_day']}", "cyan"))
        if tw["best_day"]["date"]:
            print(colored(f"  Best day:           {tw['best_day']['date']} ({tw['best_day']['count']} posts)", "green"))
        if tw["best_hour"]["hour"] is not None:
            print(colored(f"  Best hour:          {tw['best_hour']['hour']}:00 ({tw['best_hour']['count']} posts)", "green"))
        streak = tw.get("streak", {})
        if streak.get("current", 0) > 0:
            print(colored(f"  Current streak:     {streak['current']} days", "green"))
        if streak.get("longest", 0) > 0:
            print(colored(f"  Longest streak:     {streak['longest']} days", "green"))
    else:
        print(colored("  No posts yet.", "white"))

    # YouTube Stats
    yt = get_youtube_stats()
    print(colored("\n  YOUTUBE SHORTS", "red", attrs=["bold"]))
    print(colored("  " + "-" * 40, "red"))
    if yt["total_videos"] > 0:
        print(colored(f"  Total videos:       {yt['total_videos']}", "cyan"))
        print(colored(f"  Days active:        {yt['days_active']}", "cyan"))
        print(colored(f"  Avg videos/day:     {yt['avg_per_day']}", "cyan"))
        if yt["best_day"]["date"]:
            print(colored(f"  Best day:           {yt['best_day']['date']} ({yt['best_day']['count']} videos)", "green"))
        streak = yt.get("streak", {})
        if streak.get("current", 0) > 0:
            print(colored(f"  Current streak:     {streak['current']} days", "green"))
        if streak.get("longest", 0) > 0:
            print(colored(f"  Longest streak:     {streak['longest']} days", "green"))
    else:
        print(colored("  No videos yet.", "white"))

    # Affiliate Stats
    afm = get_affiliate_stats()
    print(colored("\n  AFFILIATE MARKETING", "magenta", attrs=["bold"]))
    print(colored("  " + "-" * 40, "magenta"))
    if afm["total_products"] > 0 or afm["total_clicks"] > 0:
        print(colored(f"  Products tracked:   {afm['total_products']}", "cyan"))
        print(colored(f"  Total clicks:       {afm['total_clicks']}", "cyan"))
        print(colored(f"  Total sales:        {afm['total_sales']}", "cyan"))
        print(colored(f"  Total revenue:      ${afm['total_revenue']:.2f}", "green"))
        print(colored(f"  Conversion rate:    {afm['conversion_rate']}%", "cyan"))
        if afm["clicks_by_source"]:
            print(colored(f"  Clicks by source:", "cyan"))
            for source, count in afm["clicks_by_source"].items():
                print(colored(f"    {source}: {count}", "white"))
    else:
        print(colored("  No affiliate data yet.", "white"))

    # Queue Stats
    qs = get_queue_stats()
    print(colored("\n  CONTENT QUEUE", "white", attrs=["bold"]))
    print(colored("  " + "-" * 40, "white"))
    print(colored(f"  Twitter queued:     {qs.get('twitter_queued', 0)}", "cyan"))
    print(colored(f"  Twitter posted:     {qs.get('twitter_posted', 0)}", "cyan"))
    print(colored(f"  YouTube queued:     {qs.get('youtube_queued', 0)}", "cyan"))
    print(colored(f"  YouTube posted:     {qs.get('youtube_posted', 0)}", "cyan"))

    # Milestones
    data = _load_revenue()
    milestones = data.get("milestones", [])
    if milestones:
        print(colored("\n  MILESTONES", "yellow", attrs=["bold"]))
        print(colored("  " + "-" * 40, "yellow"))
        for m in milestones[-5:]:
            print(colored(f"  {m['timestamp']}: {m['description']}", "yellow"))

    # Overall Summary
    total_content = tw.get("total_posts", 0) + yt.get("total_videos", 0)
    print(colored("\n  " + "=" * 40, "yellow"))
    print(colored(f"  TOTAL CONTENT PIECES: {total_content}", "yellow", attrs=["bold"]))
    if afm["total_revenue"] > 0:
        print(colored(f"  TOTAL REVENUE:        ${afm['total_revenue']:.2f}", "green", attrs=["bold"]))
    print(colored("  " + "=" * 40, "yellow"))
    print()
