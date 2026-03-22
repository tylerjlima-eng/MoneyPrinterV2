"""
Content Scheduler & Queue System

Pre-generates content (tweets, threads, video scripts) and queues them for
posting at optimal times throughout the day. Supports both Twitter and YouTube.
"""

import os
import json
import time
import subprocess
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from config import ROOT_DIR, get_verbose
from cache import get_accounts
from status import info, success, warning, error


def _queue_path() -> str:
    return os.path.join(ROOT_DIR, ".mp", "content_queue.json")


def _load_queue() -> dict:
    path = _queue_path()
    if not os.path.exists(path):
        return {"twitter": [], "youtube": []}
    with open(path, "r") as f:
        return json.load(f)


def _save_queue(queue: dict) -> None:
    with open(_queue_path(), "w") as f:
        json.dump(queue, f, indent=2)


def queue_twitter_content(account_id: str, content: str, content_type: str = "single",
                          scheduled_time: Optional[str] = None, tweets: Optional[List[str]] = None) -> dict:
    """Queue a tweet or thread for later posting."""
    queue = _load_queue()
    item = {
        "id": str(uuid4()),
        "account_id": account_id,
        "content": content,
        "content_type": content_type,  # "single" or "thread"
        "status": "queued",  # queued, posted, failed
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scheduled_time": scheduled_time,
        "posted_at": None,
    }
    if content_type == "thread" and tweets:
        item["tweets"] = tweets
    queue["twitter"].append(item)
    _save_queue(queue)
    return item


def queue_youtube_content(account_id: str, topic: str, script: str,
                          metadata: Optional[dict] = None,
                          scheduled_time: Optional[str] = None) -> dict:
    """Queue a YouTube Short concept for later generation and upload."""
    queue = _load_queue()
    item = {
        "id": str(uuid4()),
        "account_id": account_id,
        "topic": topic,
        "script": script,
        "metadata": metadata or {},
        "status": "queued",  # queued, generating, generated, uploading, posted, failed
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scheduled_time": scheduled_time,
        "posted_at": None,
        "video_path": None,
    }
    queue["youtube"].append(item)
    _save_queue(queue)
    return item


def get_queued_items(platform: str, status: Optional[str] = None) -> List[dict]:
    """Get all queued items for a platform, optionally filtered by status."""
    queue = _load_queue()
    items = queue.get(platform, [])
    if status:
        items = [i for i in items if i["status"] == status]
    return items


def update_queue_item(platform: str, item_id: str, updates: dict) -> None:
    """Update a queued item's fields."""
    queue = _load_queue()
    for item in queue.get(platform, []):
        if item["id"] == item_id:
            item.update(updates)
            break
    _save_queue(queue)


def remove_queue_item(platform: str, item_id: str) -> None:
    """Remove an item from the queue."""
    queue = _load_queue()
    queue[platform] = [i for i in queue.get(platform, []) if i["id"] != item_id]
    _save_queue(queue)


def clear_queue(platform: str, status: Optional[str] = None) -> int:
    """Clear queue items. If status is given, only clear items with that status."""
    queue = _load_queue()
    before = len(queue.get(platform, []))
    if status:
        queue[platform] = [i for i in queue.get(platform, []) if i["status"] != status]
    else:
        queue[platform] = []
    _save_queue(queue)
    return before - len(queue[platform])


def get_optimal_post_times(platform: str, count: int = 3) -> List[str]:
    """
    Returns optimal posting times based on platform best practices.
    Times are returned as HH:MM strings for today/tomorrow.
    """
    if platform == "twitter":
        # Twitter optimal times: morning, lunch, evening
        base_times = ["08:00", "12:30", "17:00", "19:30", "21:00"]
    else:
        # YouTube optimal times: afternoon and evening
        base_times = ["11:00", "14:00", "17:00", "19:00", "20:00"]

    now = datetime.now()
    result = []
    for t in base_times:
        hour, minute = map(int, t.split(":"))
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if scheduled <= now:
            scheduled += timedelta(days=1)
        result.append(scheduled.strftime("%Y-%m-%d %H:%M:%S"))
        if len(result) >= count:
            break

    return result


def pre_generate_twitter_content(account_id: str, topic: str, count: int = 5,
                                 include_threads: bool = True) -> List[dict]:
    """
    Pre-generates a batch of tweets and optionally threads, queuing them
    for later posting at optimal times.

    Returns the list of queued items.
    """
    from llm_provider import generate_text
    import re

    optimal_times = get_optimal_post_times("twitter", count)
    queued = []

    for i in range(count):
        scheduled = optimal_times[i] if i < len(optimal_times) else None

        # Every 3rd item is a thread if threads are enabled
        if include_threads and i > 0 and i % 3 == 0:
            completion = generate_text(
                f"Generate a Twitter thread about: {topic}. "
                "The thread should have exactly 4 tweets. "
                "Each tweet must be under 260 characters. "
                "The first tweet should hook the reader. "
                "Return ONLY a JSON array of strings."
            )
            completion = completion.replace("```json", "").replace("```", "").strip()
            try:
                tweets = json.loads(completion)
                if isinstance(tweets, list):
                    tweets = [re.sub(r"\*", "", t).replace('"', "")[:260] for t in tweets]
                    content = " | ".join(tweets)
                    item = queue_twitter_content(account_id, content, "thread",
                                                scheduled, tweets)
                    queued.append(item)
                    if get_verbose():
                        info(f"Queued thread ({len(tweets)} tweets) for {scheduled or 'manual posting'}")
                    continue
            except (json.JSONDecodeError, TypeError):
                pass

        # Single tweet
        completion = generate_text(
            f"Generate a Twitter post about: {topic}. "
            "The Limit is 2 sentences. Choose a specific sub-topic."
        )
        completion = re.sub(r"\*", "", completion).replace('"', "")
        if len(completion) > 260:
            parts = completion[:257].rsplit(" ", 1)
            completion = (parts[0] if len(parts) > 1 else completion[:257]) + "..."

        item = queue_twitter_content(account_id, completion, "single", scheduled)
        queued.append(item)
        if get_verbose():
            info(f"Queued tweet for {scheduled or 'manual posting'}")

    success(f"Pre-generated {len(queued)} items for Twitter queue.")
    return queued


def pre_generate_youtube_content(account_id: str, niche: str, language: str,
                                 count: int = 3) -> List[dict]:
    """
    Pre-generates video topics, scripts, and metadata for YouTube Shorts,
    queuing them for later generation and upload.
    """
    from llm_provider import generate_text
    from config import get_script_sentence_length
    import re

    optimal_times = get_optimal_post_times("youtube", count)
    queued = []

    for i in range(count):
        scheduled = optimal_times[i] if i < len(optimal_times) else None

        # Generate topic
        topic = generate_text(
            f"Generate a specific video idea about: {niche}. "
            "Make it exactly one sentence. Only return the topic."
        )

        # Generate script
        sentence_length = get_script_sentence_length()
        script = generate_text(
            f"Generate a script for a video in {sentence_length} sentences about: {topic}. "
            f"Write in {language}. Get straight to the point. "
            "No markdown, no formatting, no title. Only return the script."
        )
        script = re.sub(r"\*", "", script)

        # Generate metadata
        title = generate_text(
            f"Generate a YouTube Video Title for: {topic}. "
            "Include hashtags. Under 100 characters. Only return the title."
        )
        if len(title) > 100:
            title = title[:97] + "..."

        description = generate_text(
            f"Generate a YouTube Video Description for this script: {script}. "
            "Only return the description."
        )

        metadata = {"title": title, "description": description}

        item = queue_youtube_content(account_id, topic, script, metadata, scheduled)
        queued.append(item)
        if get_verbose():
            info(f"Queued video concept: {title[:50]}...")

    success(f"Pre-generated {len(queued)} video concepts for YouTube queue.")
    return queued


def post_next_queued(platform: str) -> Optional[dict]:
    """
    Posts the next queued item that's due (scheduled_time <= now, or no scheduled_time).
    Returns the posted item or None if nothing is due.
    """
    items = get_queued_items(platform, status="queued")
    now = datetime.now()

    for item in items:
        scheduled = item.get("scheduled_time")
        if scheduled:
            scheduled_dt = datetime.strptime(scheduled, "%Y-%m-%d %H:%M:%S")
            if scheduled_dt > now:
                continue

        # This item is due — mark it and return it for the caller to post
        update_queue_item(platform, item["id"], {
            "status": "posting",
            "posted_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        })
        return item

    return None


def run_queue_scheduler(platforms: List[str], check_interval: int = 60) -> None:
    """
    Runs a loop that checks the queue and posts due items.
    This is meant to be run in a long-lived process.
    """
    import schedule as sched_lib

    info("Queue scheduler started. Press Ctrl+C to stop.")

    def check_and_post():
        for platform in platforms:
            item = post_next_queued(platform)
            if item:
                info(f"Due item found on {platform}: {item['content'][:40]}...")
                # The actual posting is handled by the caller
                # We just flag it as ready

    sched_lib.every(check_interval).seconds.do(check_and_post)

    try:
        while True:
            sched_lib.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        info("Queue scheduler stopped.")
