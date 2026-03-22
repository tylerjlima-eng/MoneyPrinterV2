#!/usr/bin/env python3
"""
Quick Post — Post pre-generated content to X/Twitter from the queue.

No Ollama needed. Just needs Firefox with a logged-in X profile.

Usage:
    python scripts/quick_post.py --profile /path/to/firefox/profile
    python scripts/quick_post.py --profile /path/to/firefox/profile --list
    python scripts/quick_post.py --profile /path/to/firefox/profile --post 1
    python scripts/quick_post.py --profile /path/to/firefox/profile --post all
    python scripts/quick_post.py --profile /path/to/firefox/profile --headless

Finding your Firefox profile path:
    - Open Firefox, go to about:profiles
    - Copy the "Root Directory" path of the profile that's logged into X
    - On macOS: ~/Library/Application Support/Firefox/Profiles/xxxxxxxx.default-release
    - On Linux: ~/.mozilla/firefox/xxxxxxxx.default-release
    - On Windows: %APPDATA%\\Mozilla\\Firefox\\Profiles\\xxxxxxxx.default-release
"""

import os
import sys
import json
import time
import argparse
import re

# Add src/ to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "src"))


def load_queue():
    queue_path = os.path.join(ROOT_DIR, ".mp", "content_queue.json")
    if not os.path.exists(queue_path):
        print("No content queue found. Run the main app first or check .mp/content_queue.json")
        sys.exit(1)
    with open(queue_path, "r") as f:
        return json.load(f)


def save_queue(queue):
    queue_path = os.path.join(ROOT_DIR, ".mp", "content_queue.json")
    with open(queue_path, "w") as f:
        json.dump(queue, f, indent=2)


def list_queue(queue):
    items = [i for i in queue.get("twitter", []) if i["status"] == "queued"]
    if not items:
        print("Queue is empty! All items have been posted.")
        return

    print(f"\n{'='*60}")
    print(f"  TWITTER QUEUE — {len(items)} items ready to post")
    print(f"{'='*60}\n")

    for idx, item in enumerate(items):
        ctype = item.get("content_type", "single")
        marker = "THREAD" if ctype == "thread" else "TWEET "
        content = item["content"][:55].replace("\n", " ")
        print(f"  {idx + 1}. [{marker}] {content}...")
        if ctype == "thread":
            tweets = item.get("tweets", [])
            print(f"             ({len(tweets)} tweets in thread)")
    print()


def post_single(driver, wait, text):
    """Post a single tweet."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC

    driver.get("https://x.com/compose/post")
    time.sleep(3)

    # Find textbox
    text_box = None
    selectors = [
        (By.CSS_SELECTOR, "div[data-testid='tweetTextarea_0'][role='textbox']"),
        (By.XPATH, "//div[@data-testid='tweetTextarea_0']//div[@role='textbox']"),
        (By.XPATH, "//div[@role='textbox']"),
    ]
    for selector in selectors:
        try:
            text_box = wait.until(EC.element_to_be_clickable(selector))
            text_box.click()
            text_box.send_keys(text)
            break
        except Exception:
            continue

    if text_box is None:
        print("  ERROR: Could not find tweet textbox. Is Firefox logged into X?")
        return False

    time.sleep(1)

    # Click Post
    post_selectors = [
        (By.XPATH, "//button[@data-testid='tweetButtonInline']"),
        (By.XPATH, "//button[@data-testid='tweetButton']"),
        (By.XPATH, "//span[text()='Post']/ancestor::button"),
    ]
    for selector in post_selectors:
        try:
            btn = wait.until(EC.element_to_be_clickable(selector))
            btn.click()
            time.sleep(2)
            return True
        except Exception:
            continue

    print("  ERROR: Could not find Post button.")
    return False


def post_thread(driver, wait, tweets):
    """Post a thread (multiple connected tweets)."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC

    driver.get("https://x.com/compose/post")
    time.sleep(3)

    for idx, tweet_text in enumerate(tweets):
        if idx > 0:
            # Click "Add another post"
            add_selectors = [
                (By.XPATH, "//button[@data-testid='addButton']"),
                (By.XPATH, "//button[contains(@aria-label, 'Add')]"),
                (By.XPATH, "//div[@data-testid='addButton']"),
            ]
            added = False
            for selector in add_selectors:
                try:
                    btn = wait.until(EC.element_to_be_clickable(selector))
                    btn.click()
                    time.sleep(1)
                    added = True
                    break
                except Exception:
                    continue
            if not added:
                print(f"  WARNING: Could not add tweet {idx + 1}. Posting what we have.")
                break

        # Find textbox for this tweet
        text_box = None
        selectors = [
            (By.CSS_SELECTOR, f"div[data-testid='tweetTextarea_{idx}'][role='textbox']"),
            (By.XPATH, f"//div[@data-testid='tweetTextarea_{idx}']//div[@role='textbox']"),
            (By.XPATH, "(//div[@role='textbox'])[last()]"),
        ]
        for selector in selectors:
            try:
                text_box = wait.until(EC.element_to_be_clickable(selector))
                text_box.click()
                text_box.send_keys(tweet_text)
                break
            except Exception:
                continue

        if text_box is None:
            print(f"  WARNING: Could not find textbox for tweet {idx + 1}.")
            break

        print(f"    Tweet {idx + 1}/{len(tweets)}: {tweet_text[:40]}...")

    time.sleep(1)

    # Click "Post all"
    post_selectors = [
        (By.XPATH, "//button[@data-testid='tweetButtonInline']"),
        (By.XPATH, "//button[@data-testid='tweetButton']"),
        (By.XPATH, "//span[text()='Post all']/ancestor::button"),
        (By.XPATH, "//span[text()='Post']/ancestor::button"),
    ]
    for selector in post_selectors:
        try:
            btn = wait.until(EC.element_to_be_clickable(selector))
            btn.click()
            time.sleep(2)
            return True
        except Exception:
            continue

    print("  ERROR: Could not find Post button.")
    return False


def start_browser(profile_path, headless=False):
    """Start Firefox with the given profile."""
    from selenium import webdriver
    from selenium.webdriver.firefox.service import Service
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from webdriver_manager.firefox import GeckoDriverManager

    if not os.path.isdir(profile_path):
        print(f"ERROR: Firefox profile not found at: {profile_path}")
        print("\nTo find your profile path:")
        print("  1. Open Firefox")
        print("  2. Go to about:profiles")
        print("  3. Copy the 'Root Directory' of the profile logged into X")
        sys.exit(1)

    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("-profile")
    options.add_argument(profile_path)

    print("Starting Firefox...")
    service = Service(GeckoDriverManager().install())
    driver = webdriver.Firefox(service=service, options=options)
    wait = WebDriverWait(driver, 30)
    print("Browser ready.\n")
    return driver, wait


def main():
    parser = argparse.ArgumentParser(
        description="Quick Post — post pre-generated content to X/Twitter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--profile", required=True, help="Path to Firefox profile logged into X")
    parser.add_argument("--list", action="store_true", help="List queued items without posting")
    parser.add_argument("--post", default=None, help="Post item by number, 'next', or 'all'")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    args = parser.parse_args()

    queue = load_queue()
    queued = [i for i in queue.get("twitter", []) if i["status"] == "queued"]

    if args.list or args.post is None:
        list_queue(queue)
        if args.post is None:
            print("Usage examples:")
            print(f"  python {sys.argv[0]} --profile {args.profile} --post 1      # post item 1")
            print(f"  python {sys.argv[0]} --profile {args.profile} --post all    # post everything")
            print(f"  python {sys.argv[0]} --profile {args.profile} --post next   # post next due item")
        return

    if not queued:
        print("Queue is empty!")
        return

    # Figure out what to post
    if args.post == "all":
        to_post = queued
    elif args.post == "next":
        to_post = [queued[0]]
    elif args.post.isdigit() and 1 <= int(args.post) <= len(queued):
        to_post = [queued[int(args.post) - 1]]
    else:
        print(f"Invalid --post value: {args.post}")
        print(f"Use a number (1-{len(queued)}), 'next', or 'all'")
        return

    print(f"Will post {len(to_post)} item(s).\n")

    driver, wait = start_browser(args.profile, args.headless)

    try:
        for idx, item in enumerate(to_post):
            ctype = item.get("content_type", "single")
            print(f"[{idx + 1}/{len(to_post)}] Posting {ctype}...")

            if ctype == "thread" and item.get("tweets"):
                ok = post_thread(driver, wait, item["tweets"])
            else:
                ok = post_single(driver, wait, item["content"])

            if ok:
                item["status"] = "posted"
                save_queue(queue)
                print(f"  POSTED!\n")
            else:
                item["status"] = "failed"
                save_queue(queue)
                print(f"  FAILED.\n")

            if idx < len(to_post) - 1:
                print("  Waiting 5 seconds before next post...")
                time.sleep(5)

    finally:
        driver.quit()
        print("Done. Browser closed.")

    posted = len([i for i in to_post if i["status"] == "posted"])
    failed = len([i for i in to_post if i["status"] == "failed"])
    remaining = len([i for i in queue.get("twitter", []) if i["status"] == "queued"])
    print(f"\nResults: {posted} posted, {failed} failed, {remaining} still in queue.")


if __name__ == "__main__":
    main()
