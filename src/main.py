import time
import schedule
import subprocess

from art import *
from cache import *
from utils import *
from config import *
from status import *
from uuid import uuid4
from constants import *
from classes.Tts import TTS
from termcolor import colored
from classes.Twitter import Twitter
from classes.YouTube import YouTube
from prettytable import PrettyTable
from classes.Outreach import Outreach
from classes.AFM import AffiliateMarketing
from llm_provider import list_models, select_model, get_active_model
from config import validate_config
from scheduler import (
    pre_generate_twitter_content, pre_generate_youtube_content,
    get_queued_items, post_next_queued, update_queue_item, clear_queue,
)
from crosspost import (
    crosspost_tweet_to_youtube, crosspost_video_to_twitter,
)
from revenue import print_revenue_dashboard, log_milestone

def main():
    """Main entry point for the application, providing a menu-driven interface
    to manage YouTube, Twitter bots, Affiliate Marketing, and Outreach tasks.

    This function allows users to:
    1. Start the YouTube Shorts Automater to manage YouTube accounts, 
       generate and upload videos, and set up CRON jobs.
    2. Start a Twitter Bot to manage Twitter accounts, post tweets, and 
       schedule posts using CRON jobs.
    3. Manage Affiliate Marketing by creating pitches and sharing them via 
       Twitter accounts.
    4. Initiate an Outreach process for engagement and promotion tasks.
    5. Exit the application.

    The function continuously prompts users for input, validates it, and 
    executes the selected option until the user chooses to quit.

    Args:
        None

    Returns:
        None"""

    # Get user input
    # user_input = int(question("Select an option: "))
    valid_input = False
    while not valid_input:
        try:
    # Show user options
            info("\n============ OPTIONS ============", False)

            for idx, option in enumerate(OPTIONS):
                print(colored(f" {idx + 1}. {option}", "cyan"))

            info("=================================\n", False)
            user_input = input("Select an option: ").strip()
            if user_input == '':
                print("\n" * 100)
                raise ValueError("Empty input is not allowed.")
            user_input = int(user_input)
            valid_input = True
        except ValueError as e:
            print("\n" * 100)
            print(f"Invalid input: {e}")


    # Start the selected option
    if user_input == 1:
        info("Starting YT Shorts Automater...")

        cached_accounts = get_accounts("youtube")

        if len(cached_accounts) == 0:
            warning("No accounts found in cache. Create one now?")
            user_input = question("Yes/No: ")

            if user_input.lower() == "yes":
                generated_uuid = str(uuid4())

                success(f" => Generated ID: {generated_uuid}")
                nickname = question(" => Enter a nickname for this account: ")
                fp_profile = question(" => Enter the path to the Firefox profile: ")
                niche = question(" => Enter the account niche: ")
                language = question(" => Enter the account language: ")

                account_data = {
                    "id": generated_uuid,
                    "nickname": nickname,
                    "firefox_profile": fp_profile,
                    "niche": niche,
                    "language": language,
                    "videos": [],
                }

                add_account("youtube", account_data)

                success("Account configured successfully!")
        else:
            table = PrettyTable()
            table.field_names = ["ID", "UUID", "Nickname", "Niche"]

            for account in cached_accounts:
                table.add_row([cached_accounts.index(account) + 1, colored(account["id"], "cyan"), colored(account["nickname"], "blue"), colored(account["niche"], "green")])

            print(table)
            info("Type 'd' to delete an account.", False)

            user_input = question("Select an account to start (or 'd' to delete): ").strip()

            if user_input.lower() == "d":
                delete_input = question("Enter account number to delete: ").strip()
                account_to_delete = None

                for account in cached_accounts:
                    if str(cached_accounts.index(account) + 1) == delete_input:
                        account_to_delete = account
                        break

                if account_to_delete is None:
                    error("Invalid account selected. Please try again.", "red")
                else:
                    confirm = question(f"Are you sure you want to delete '{account_to_delete['nickname']}'? (Yes/No): ").strip().lower()

                    if confirm == "yes":
                        remove_account("youtube", account_to_delete["id"])
                        success("Account removed successfully!")
                    else:
                        warning("Account deletion canceled.", False)

                return

            selected_account = None

            for account in cached_accounts:
                if str(cached_accounts.index(account) + 1) == user_input:
                    selected_account = account

            if selected_account is None:
                error("Invalid account selected. Please try again.", "red")
                main()
            else:
                youtube = YouTube(
                    selected_account["id"],
                    selected_account["nickname"],
                    selected_account["firefox_profile"],
                    selected_account["niche"],
                    selected_account["language"]
                )

                while True:
                    rem_temp_files()
                    info("\n============ OPTIONS ============", False)

                    for idx, youtube_option in enumerate(YOUTUBE_OPTIONS):
                        print(colored(f" {idx + 1}. {youtube_option}", "cyan"))

                    info("=================================\n", False)

                    # Get user input
                    user_input = int(question("Select an option: "))
                    tts = TTS()

                    if user_input == 1:
                        youtube.generate_video(tts)
                        upload_to_yt = question("Do you want to upload this video to YouTube? (Yes/No): ")
                        if upload_to_yt.lower() == "yes":
                            youtube.upload_video()
                    elif user_input == 2:
                        # Batch generate
                        count_str = question("How many videos to generate? (default 3): ").strip()
                        count = int(count_str) if count_str.isdigit() and int(count_str) > 0 else 3
                        auto_upload_input = question("Auto-upload each video? (Yes/No): ").strip().lower()
                        auto_upload = auto_upload_input == "yes"
                        youtube.generate_batch(tts, count=count, auto_upload=auto_upload)
                    elif user_input == 3:
                        videos = youtube.get_videos()

                        if len(videos) > 0:
                            videos_table = PrettyTable()
                            videos_table.field_names = ["ID", "Date", "Title"]

                            for video in videos:
                                videos_table.add_row([
                                    videos.index(video) + 1,
                                    colored(video["date"], "blue"),
                                    colored(video["title"][:60] + "...", "green")
                                ])

                            print(videos_table)
                        else:
                            warning(" No videos found.")
                    elif user_input == 4:
                        info("How often do you want to upload?")

                        info("\n============ OPTIONS ============", False)
                        for idx, cron_option in enumerate(YOUTUBE_CRON_OPTIONS):
                            print(colored(f" {idx + 1}. {cron_option}", "cyan"))

                        info("=================================\n", False)

                        user_input = int(question("Select an Option: "))

                        cron_script_path = os.path.join(ROOT_DIR, "src", "cron.py")
                        command = ["python", cron_script_path, "youtube", selected_account['id'], get_active_model()]

                        def job():
                            subprocess.run(command)

                        if user_input == 1:
                            # Upload Once
                            schedule.every(1).day.do(job)
                            success("Set up CRON Job.")
                        elif user_input == 2:
                            # Upload Twice a day
                            schedule.every().day.at("10:00").do(job)
                            schedule.every().day.at("16:00").do(job)
                            success("Set up CRON Job.")
                        else:
                            break

                        # Run the scheduler loop
                        info("Scheduler is now running. Press Ctrl+C to stop.", False)
                        try:
                            while True:
                                schedule.run_pending()
                                time.sleep(60)
                        except KeyboardInterrupt:
                            info("Scheduler stopped.")
                            break
                    elif user_input == 5:
                        # Analytics
                        videos = youtube.get_videos()
                        info("\n========== ANALYTICS ==========", False)
                        print(colored(f"  Total videos uploaded: {len(videos)}", "cyan"))
                        if len(videos) > 0:
                            # Videos per day breakdown
                            from collections import Counter
                            dates = []
                            for v in videos:
                                date_str = v.get("date", "")
                                day = date_str.split(" ")[0] if " " in date_str else date_str
                                if day:
                                    dates.append(day)
                            day_counts = Counter(dates)
                            if day_counts:
                                print(colored(f"  Days with uploads: {len(day_counts)}", "cyan"))
                                avg = len(videos) / len(day_counts)
                                print(colored(f"  Avg videos/day: {avg:.1f}", "cyan"))
                                most_common_day, most_count = day_counts.most_common(1)[0]
                                print(colored(f"  Best day: {most_common_day} ({most_count} videos)", "green"))
                            last = videos[-1]
                            print(colored(f"  Latest: \"{last.get('title', 'N/A')[:50]}\" on {last.get('date', 'N/A')}", "cyan"))
                        info("===============================\n", False)
                    elif user_input == 6:
                        # Pre-Generate Content Queue
                        count_str = question("How many items to pre-generate? (default 5): ").strip()
                        count = int(count_str) if count_str.isdigit() and int(count_str) > 0 else 5
                        include_threads = question("Include threads? (Yes/No, default Yes): ").strip().lower()
                        include_threads = include_threads != "no"
                        pre_generate_youtube_content(
                            selected_account["id"],
                            selected_account["niche"],
                            selected_account["language"],
                            count=count,
                        )
                    elif user_input == 7:
                        # Generate from Queue
                        queued = get_queued_items("youtube", status="queued")
                        if not queued:
                            warning("No queued YouTube content. Use 'Pre-Generate Content Queue' first.")
                        else:
                            info(f"{len(queued)} items in queue.")
                            for idx, item in enumerate(queued[:5]):
                                title = item.get("metadata", {}).get("title", item.get("topic", ""))[:50]
                                scheduled = item.get("scheduled_time", "manual")
                                print(colored(f"  {idx + 1}. {title}  [{scheduled}]", "cyan"))

                            pick = question("Generate which item? (number, or 'all'): ").strip()
                            if pick.lower() == "all":
                                items_to_gen = queued[:5]
                            elif pick.isdigit() and 1 <= int(pick) <= len(queued[:5]):
                                items_to_gen = [queued[int(pick) - 1]]
                            else:
                                warning("Invalid selection.")
                                items_to_gen = []

                            for item in items_to_gen:
                                youtube.subject = item["topic"]
                                youtube.script = item["script"]
                                youtube.metadata = item.get("metadata", {"title": item["topic"], "description": ""})
                                youtube.images = []

                                youtube.generate_prompts()
                                for prompt in youtube.image_prompts:
                                    youtube.generate_image(prompt)
                                youtube.generate_script_to_speech(tts)
                                path = youtube.combine()
                                youtube.video_path = path
                                update_queue_item("youtube", item["id"], {"status": "generated", "video_path": path})
                                success(f"Generated video: {path}")

                                upload_input = question("Upload this video? (Yes/No): ").strip().lower()
                                if upload_input == "yes":
                                    uploaded = youtube.upload_video()
                                    if uploaded:
                                        update_queue_item("youtube", item["id"], {"status": "posted"})
                                        success("Uploaded!")
                                    else:
                                        update_queue_item("youtube", item["id"], {"status": "failed"})
                                        warning("Upload failed.")

                                rem_temp_files()
                    elif user_input == 8:
                        # Cross-Post to Twitter
                        if not hasattr(youtube, 'script') or not youtube.script:
                            warning("Generate a video first before cross-posting.")
                        else:
                            # Need a Twitter account for cross-posting
                            tw_accounts = get_accounts("twitter")
                            if not tw_accounts:
                                warning("No Twitter accounts found. Set one up first.")
                            else:
                                info("Select a Twitter account for cross-posting:")
                                for idx, acc in enumerate(tw_accounts):
                                    print(colored(f"  {idx + 1}. {acc['nickname']}", "cyan"))
                                tw_pick = question("Account number: ").strip()
                                tw_acc = None
                                if tw_pick.isdigit() and 1 <= int(tw_pick) <= len(tw_accounts):
                                    tw_acc = tw_accounts[int(tw_pick) - 1]

                                if tw_acc:
                                    as_thread = question("Post as thread? (Yes/No, default Yes): ").strip().lower() != "no"
                                    tw = Twitter(tw_acc["id"], tw_acc["nickname"], tw_acc["firefox_profile"], tw_acc["topic"])
                                    crosspost_video_to_twitter(youtube, tw, as_thread=as_thread)
                                else:
                                    warning("Invalid selection.")
                    elif user_input == 9:
                        if get_verbose():
                            info(" => Climbing Options Ladder...", False)
                        break
    elif user_input == 2:
        info("Starting Twitter Bot...")

        cached_accounts = get_accounts("twitter")

        if len(cached_accounts) == 0:
            warning("No accounts found in cache. Create one now?")
            user_input = question("Yes/No: ")

            if user_input.lower() == "yes":
                generated_uuid = str(uuid4())

                success(f" => Generated ID: {generated_uuid}")
                nickname = question(" => Enter a nickname for this account: ")
                fp_profile = question(" => Enter the path to the Firefox profile: ")
                topic = question(" => Enter the account topic: ")

                add_account("twitter", {
                    "id": generated_uuid,
                    "nickname": nickname,
                    "firefox_profile": fp_profile,
                    "topic": topic,
                    "posts": []
                })
        else:
            table = PrettyTable()
            table.field_names = ["ID", "UUID", "Nickname", "Account Topic"]

            for account in cached_accounts:
                table.add_row([cached_accounts.index(account) + 1, colored(account["id"], "cyan"), colored(account["nickname"], "blue"), colored(account["topic"], "green")])

            print(table)
            info("Type 'd' to delete an account.", False)

            user_input = question("Select an account to start (or 'd' to delete): ").strip()

            if user_input.lower() == "d":
                delete_input = question("Enter account number to delete: ").strip()
                account_to_delete = None

                for account in cached_accounts:
                    if str(cached_accounts.index(account) + 1) == delete_input:
                        account_to_delete = account
                        break

                if account_to_delete is None:
                    error("Invalid account selected. Please try again.", "red")
                else:
                    confirm = question(f"Are you sure you want to delete '{account_to_delete['nickname']}'? (Yes/No): ").strip().lower()

                    if confirm == "yes":
                        remove_account("twitter", account_to_delete["id"])
                        success("Account removed successfully!")
                    else:
                        warning("Account deletion canceled.", False)

                return

            selected_account = None

            for account in cached_accounts:
                if str(cached_accounts.index(account) + 1) == user_input:
                    selected_account = account

            if selected_account is None:
                error("Invalid account selected. Please try again.", "red")
                main()
            else:
                twitter = Twitter(selected_account["id"], selected_account["nickname"], selected_account["firefox_profile"], selected_account["topic"])

                while True:
                    
                    info("\n============ OPTIONS ============", False)

                    for idx, twitter_option in enumerate(TWITTER_OPTIONS):
                        print(colored(f" {idx + 1}. {twitter_option}", "cyan"))

                    info("=================================\n", False)

                    # Get user input
                    user_input = int(question("Select an option: "))

                    if user_input == 1:
                        twitter.post()
                    elif user_input == 2:
                        # Post a Thread
                        num_str = question("How many tweets in the thread? (default 4): ").strip()
                        num_tweets = int(num_str) if num_str.isdigit() and 2 <= int(num_str) <= 10 else 4
                        thread_tweets = twitter.generate_thread(num_tweets=num_tweets)
                        twitter.post_thread(tweets=thread_tweets)
                    elif user_input == 3:
                        posts = twitter.get_posts()

                        posts_table = PrettyTable()

                        posts_table.field_names = ["ID", "Date", "Type", "Content"]

                        for post in posts:
                            post_type = post.get("type", "single")
                            posts_table.add_row([
                                posts.index(post) + 1,
                                colored(post["date"], "blue"),
                                colored(post_type, "yellow"),
                                colored(post["content"][:50] + "...", "green")
                            ])

                        print(posts_table)
                    elif user_input == 4:
                        info("How often do you want to post?")

                        info("\n============ OPTIONS ============", False)
                        for idx, cron_option in enumerate(TWITTER_CRON_OPTIONS):
                            print(colored(f" {idx + 1}. {cron_option}", "cyan"))

                        info("=================================\n", False)

                        user_input = int(question("Select an Option: "))

                        cron_script_path = os.path.join(ROOT_DIR, "src", "cron.py")
                        command = ["python", cron_script_path, "twitter", selected_account['id'], get_active_model()]

                        def job():
                            subprocess.run(command)

                        if user_input == 1:
                            # Post Once a day
                            schedule.every(1).day.do(job)
                            success("Set up CRON Job.")
                        elif user_input == 2:
                            # Post twice a day
                            schedule.every().day.at("10:00").do(job)
                            schedule.every().day.at("16:00").do(job)
                            success("Set up CRON Job.")
                        elif user_input == 3:
                            # Post thrice a day
                            schedule.every().day.at("08:00").do(job)
                            schedule.every().day.at("12:00").do(job)
                            schedule.every().day.at("18:00").do(job)
                            success("Set up CRON Job.")
                        else:
                            break

                        # Run the scheduler loop
                        info("Scheduler is now running. Press Ctrl+C to stop.", False)
                        try:
                            while True:
                                schedule.run_pending()
                                time.sleep(60)
                        except KeyboardInterrupt:
                            info("Scheduler stopped.")
                            break
                    elif user_input == 5:
                        # Analytics
                        posts = twitter.get_posts()
                        info("\n========== ANALYTICS ==========", False)
                        print(colored(f"  Total posts: {len(posts)}", "cyan"))
                        if len(posts) > 0:
                            threads = [p for p in posts if p.get("type") == "thread"]
                            singles = len(posts) - len(threads)
                            print(colored(f"  Single posts: {singles}", "cyan"))
                            print(colored(f"  Threads: {len(threads)}", "cyan"))
                            if threads:
                                total_tweets_in_threads = sum(p.get("tweet_count", 1) for p in threads)
                                print(colored(f"  Total tweets in threads: {total_tweets_in_threads}", "cyan"))
                            from collections import Counter
                            dates = []
                            for p in posts:
                                date_str = p.get("date", "")
                                day = date_str.split(",")[0] if "," in date_str else date_str.split(" ")[0]
                                if day:
                                    dates.append(day)
                            day_counts = Counter(dates)
                            if day_counts:
                                print(colored(f"  Days with posts: {len(day_counts)}", "cyan"))
                                avg = len(posts) / len(day_counts)
                                print(colored(f"  Avg posts/day: {avg:.1f}", "cyan"))
                            last = posts[-1]
                            print(colored(f"  Latest: \"{last.get('content', '')[:40]}...\" on {last.get('date', 'N/A')}", "cyan"))
                        info("===============================\n", False)
                    elif user_input == 6:
                        # Pre-Generate Content Queue
                        count_str = question("How many items to pre-generate? (default 5): ").strip()
                        count = int(count_str) if count_str.isdigit() and int(count_str) > 0 else 5
                        include_threads = question("Include threads? (Yes/No, default Yes): ").strip().lower()
                        include_threads = include_threads != "no"
                        pre_generate_twitter_content(
                            selected_account["id"],
                            selected_account["topic"],
                            count=count,
                            include_threads=include_threads,
                        )
                    elif user_input == 7:
                        # Post from Queue
                        queued = get_queued_items("twitter", status="queued")
                        if not queued:
                            warning("No queued Twitter content. Use 'Pre-Generate Content Queue' first.")
                        else:
                            info(f"{len(queued)} items in queue.")
                            for idx, item in enumerate(queued[:10]):
                                ctype = item.get("content_type", "single")
                                scheduled = item.get("scheduled_time", "manual")
                                print(colored(f"  {idx + 1}. [{ctype}] {item['content'][:45]}...  [{scheduled}]", "cyan"))

                            pick = question("Post which item? (number, 'next' for next due, or 'all'): ").strip()
                            if pick.lower() == "next":
                                item = post_next_queued("twitter")
                                if item:
                                    if item.get("content_type") == "thread" and item.get("tweets"):
                                        twitter.post_thread(tweets=item["tweets"])
                                    else:
                                        twitter.post(text=item["content"])
                                    update_queue_item("twitter", item["id"], {"status": "posted"})
                                else:
                                    warning("No items due right now.")
                            elif pick.lower() == "all":
                                for item in queued[:10]:
                                    if item.get("content_type") == "thread" and item.get("tweets"):
                                        twitter.post_thread(tweets=item["tweets"])
                                    else:
                                        twitter.post(text=item["content"])
                                    update_queue_item("twitter", item["id"], {"status": "posted"})
                                    time.sleep(5)
                            elif pick.isdigit() and 1 <= int(pick) <= len(queued[:10]):
                                item = queued[int(pick) - 1]
                                if item.get("content_type") == "thread" and item.get("tweets"):
                                    twitter.post_thread(tweets=item["tweets"])
                                else:
                                    twitter.post(text=item["content"])
                                update_queue_item("twitter", item["id"], {"status": "posted"})
                            else:
                                warning("Invalid selection.")
                    elif user_input == 8:
                        # Cross-Post to YouTube
                        last_posts = twitter.get_posts()
                        if not last_posts:
                            warning("No posts found. Post something first.")
                        else:
                            info("Select a post to cross-post as a YouTube Short:")
                            for idx, post in enumerate(last_posts[-5:]):
                                print(colored(f"  {idx + 1}. {post['content'][:50]}...", "cyan"))

                            pick = question("Post number: ").strip()
                            if pick.isdigit() and 1 <= int(pick) <= len(last_posts[-5:]):
                                selected_post = last_posts[-5:][int(pick) - 1]

                                # Need a YouTube account for cross-posting
                                yt_accounts = get_accounts("youtube")
                                if not yt_accounts:
                                    warning("No YouTube accounts found. Set one up first.")
                                else:
                                    info("Select a YouTube account for cross-posting:")
                                    for idx, acc in enumerate(yt_accounts):
                                        print(colored(f"  {idx + 1}. {acc['nickname']} ({acc['niche']})", "cyan"))
                                    yt_pick = question("Account number: ").strip()
                                    yt_acc = None
                                    if yt_pick.isdigit() and 1 <= int(yt_pick) <= len(yt_accounts):
                                        yt_acc = yt_accounts[int(yt_pick) - 1]

                                    if yt_acc:
                                        yt = YouTube(
                                            yt_acc["id"], yt_acc["nickname"],
                                            yt_acc["firefox_profile"],
                                            yt_acc["niche"], yt_acc["language"]
                                        )
                                        tts = TTS()
                                        auto_upload = question("Auto-upload to YouTube? (Yes/No): ").strip().lower() == "yes"
                                        crosspost_tweet_to_youtube(
                                            twitter, yt, tts,
                                            selected_post["content"],
                                            auto_upload=auto_upload,
                                        )
                                    else:
                                        warning("Invalid selection.")
                            else:
                                warning("Invalid selection.")
                    elif user_input == 9:
                        if get_verbose():
                            info(" => Climbing Options Ladder...", False)
                        break
    elif user_input == 3:
        info("Starting Affiliate Marketing...")

        cached_products = get_products()

        if len(cached_products) == 0:
            warning("No products found in cache. Create one now?")
            user_input = question("Yes/No: ")

            if user_input.lower() == "yes":
                affiliate_link = question(" => Enter the affiliate link: ")
                twitter_uuid = question(" => Enter the Twitter Account UUID: ")

                # Find the account
                account = None
                for acc in get_accounts("twitter"):
                    if acc["id"] == twitter_uuid:
                        account = acc

                add_product({
                    "id": str(uuid4()),
                    "affiliate_link": affiliate_link,
                    "twitter_uuid": twitter_uuid
                })

                afm = AffiliateMarketing(affiliate_link, account["firefox_profile"], account["id"], account["nickname"], account["topic"])

                afm.generate_pitch()
                afm.share_pitch("twitter")
        else:
            table = PrettyTable()
            table.field_names = ["ID", "Affiliate Link", "Twitter Account UUID"]

            for product in cached_products:
                table.add_row([cached_products.index(product) + 1, colored(product["affiliate_link"], "cyan"), colored(product["twitter_uuid"], "blue")])

            print(table)

            user_input = question("Select a product to start: ")

            selected_product = None

            for product in cached_products:
                if str(cached_products.index(product) + 1) == user_input:
                    selected_product = product

            if selected_product is None:
                error("Invalid product selected. Please try again.", "red")
                main()
            else:
                # Find the account
                account = None
                for acc in get_accounts("twitter"):
                    if acc["id"] == selected_product["twitter_uuid"]:
                        account = acc

                afm = AffiliateMarketing(selected_product["affiliate_link"], account["firefox_profile"], account["id"], account["nickname"], account["topic"])

                afm.generate_pitch()
                afm.share_pitch("twitter")

    elif user_input == 4:
        info("Starting Outreach...")

        outreach = Outreach()

        outreach.start()
    elif user_input == 5:
        info("Loading Revenue Dashboard...")
        print_revenue_dashboard()
    elif user_input == 6:
        if get_verbose():
            print(colored(" => Quitting...", "blue"))
        sys.exit(0)
    else:
        error("Invalid option selected. Please try again.", "red")
        main()
    

if __name__ == "__main__":
    # Print ASCII Banner
    print_banner()

    first_time = get_first_time_running()

    if first_time:
        print(colored("Hey! It looks like you're running MoneyPrinter V2 for the first time. Let's get you setup first!", "yellow"))

    # Validate config
    config_errors = validate_config()
    if config_errors:
        for err in config_errors:
            error(err)
        print(colored("\nPlease fix config.json and try again. See config.example.json for reference.", "yellow"))
        sys.exit(1)

    # Setup file tree
    assert_folder_structure()

    # Remove temporary files
    rem_temp_files()

    # Fetch MP3 Files
    fetch_songs()

    # Select Ollama model — use config value if set, otherwise pick interactively
    configured_model = get_ollama_model()
    if configured_model:
        select_model(configured_model)
        success(f"Using configured model: {configured_model}")
    else:
        try:
            models = list_models()
        except Exception as e:
            error(f"Could not connect to Ollama: {e}")
            sys.exit(1)

        if not models:
            error("No models found on Ollama. Pull a model first (e.g. 'ollama pull llama3.2:3b').")
            sys.exit(1)

        info("\n========== OLLAMA MODELS =========", False)
        for idx, model_name in enumerate(models):
            print(colored(f" {idx + 1}. {model_name}", "cyan"))
        info("==================================\n", False)

        model_choice = None
        while model_choice is None:
            raw = input(colored("Select a model: ", "magenta")).strip()
            try:
                choice_idx = int(raw) - 1
                if 0 <= choice_idx < len(models):
                    model_choice = models[choice_idx]
                else:
                    warning("Invalid selection. Try again.")
            except ValueError:
                warning("Please enter a number.")

        select_model(model_choice)
        success(f"Using model: {model_choice}")

    while True:
        main()
