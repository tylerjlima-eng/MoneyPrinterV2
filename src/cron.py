# RUN THIS N AMOUNT OF TIMES
import sys

from status import *
from cache import get_accounts
from config import get_verbose
from classes.Tts import TTS
from classes.Twitter import Twitter
from classes.YouTube import YouTube
from llm_provider import select_model
from scheduler import post_next_queued, update_queue_item

def main():
    """Main function to post content to Twitter or upload videos to YouTube.

    This function determines its operation based on command-line arguments:
    - If the purpose is "twitter", it initializes a Twitter account and posts a message.
    - If the purpose is "youtube", it initializes a YouTube account, generates a video with TTS, and uploads it.

    Command-line arguments:
        sys.argv[1]: A string indicating the purpose, either "twitter" or "youtube".
        sys.argv[2]: A string representing the account UUID.

    The function also handles verbose output based on user settings and reports success or errors as appropriate.

    Args:
        None. The function uses command-line arguments accessed via sys.argv.

    Returns:
        None. The function performs operations based on the purpose and account UUID and does not return any value."""
    purpose = str(sys.argv[1])
    account_id = str(sys.argv[2])
    model = str(sys.argv[3]) if len(sys.argv) > 3 else None

    if model:
        select_model(model)
    else:
        error("No Ollama model specified. Pass model name as third argument.")
        sys.exit(1)

    verbose = get_verbose()

    if purpose == "twitter":
        accounts = get_accounts("twitter")

        if not account_id:
            error("Account UUID cannot be empty.")
            sys.exit(1)

        account = None
        for acc in accounts:
            if acc["id"] == account_id:
                account = acc
                break

        if account is None:
            error(f"Twitter account with UUID '{account_id}' not found.")
            sys.exit(1)

        if verbose:
            info("Initializing Twitter...")
        twitter = Twitter(
            account["id"],
            account["nickname"],
            account["firefox_profile"],
            account["topic"]
        )
        # Check queue first — post from queue if items are due
        queued_item = post_next_queued("twitter")
        if queued_item:
            if queued_item.get("content_type") == "thread" and queued_item.get("tweets"):
                twitter.post_thread(tweets=queued_item["tweets"])
            else:
                twitter.post(text=queued_item["content"])
            update_queue_item("twitter", queued_item["id"], {"status": "posted"})
            if verbose:
                success(f"Posted queued item: {queued_item['content'][:40]}...")
        else:
            twitter.post()
        if verbose:
            success("Done posting.")

    elif purpose == "youtube":
        tts = TTS()

        accounts = get_accounts("youtube")

        if not account_id:
            error("Account UUID cannot be empty.")
            sys.exit(1)

        account = None
        for acc in accounts:
            if acc["id"] == account_id:
                account = acc
                break

        if account is None:
            error(f"YouTube account with UUID '{account_id}' not found.")
            sys.exit(1)

        if verbose:
            info("Initializing YouTube...")
        youtube = YouTube(
            account["id"],
            account["nickname"],
            account["firefox_profile"],
            account["niche"],
            account["language"]
        )
        # Check queue first — use pre-generated content if available
        queued_item = post_next_queued("youtube")
        if queued_item:
            youtube.subject = queued_item["topic"]
            youtube.script = queued_item["script"]
            youtube.metadata = queued_item.get("metadata", {"title": queued_item["topic"], "description": ""})
            youtube.generate_prompts()
            for prompt in youtube.image_prompts:
                youtube.generate_image(prompt)
            youtube.generate_script_to_speech(tts)
            path = youtube.combine()
            youtube.video_path = path
            update_queue_item("youtube", queued_item["id"], {"status": "generated"})
            if verbose:
                info(f"Generated from queue: {queued_item['topic'][:40]}...")
        else:
            youtube.generate_video(tts)
        youtube.upload_video()
        if verbose:
            success("Uploaded Short.")

    else:
        error("Invalid Purpose, exiting...")
        sys.exit(1)

if __name__ == "__main__":
    main()
