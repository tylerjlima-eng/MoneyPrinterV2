#!/usr/bin/env python3
"""
Assigns queued content to the correct account IDs.

Run this after setting up your accounts in the app:
    python scripts/load_queue.py

It will find your Twitter/YouTube accounts and update all PLACEHOLDER
entries in the content queue to use your actual account UUIDs.
"""
import os
import sys
import json

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "src"))

from cache import get_accounts


def main():
    queue_path = os.path.join(ROOT_DIR, ".mp", "content_queue.json")
    if not os.path.exists(queue_path):
        print("No content queue found at .mp/content_queue.json")
        return

    with open(queue_path, "r") as f:
        queue = json.load(f)

    # Twitter accounts
    tw_accounts = get_accounts("twitter")
    if tw_accounts:
        tw_id = tw_accounts[0]["id"]
        updated = 0
        for item in queue.get("twitter", []):
            if item["account_id"] == "PLACEHOLDER":
                item["account_id"] = tw_id
                updated += 1
        if updated:
            print(f"Assigned {updated} Twitter queue items to account: {tw_accounts[0]['nickname']} ({tw_id})")
    else:
        print("No Twitter accounts found. Set one up in the app first.")

    # YouTube accounts
    yt_accounts = get_accounts("youtube")
    if yt_accounts:
        yt_id = yt_accounts[0]["id"]
        updated = 0
        for item in queue.get("youtube", []):
            if item["account_id"] == "PLACEHOLDER":
                item["account_id"] = yt_id
                updated += 1
        if updated:
            print(f"Assigned {updated} YouTube queue items to account: {yt_accounts[0]['nickname']} ({yt_id})")
    else:
        print("No YouTube accounts found. Set one up in the app first.")

    with open(queue_path, "w") as f:
        json.dump(queue, f, indent=2)

    print("Done! Run 'python src/main.py' and use 'Post from Queue' to start posting.")


if __name__ == "__main__":
    main()
