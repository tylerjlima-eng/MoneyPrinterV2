"""
Cross-Platform Posting

Adapts content between Twitter and YouTube formats and posts to both platforms.
- Tweet/thread -> YouTube Short script (text-to-video adaptation)
- YouTube script -> Tweet thread (summarize for Twitter)
"""

import re
import json
from typing import List, Optional
from datetime import datetime

from config import get_verbose, get_twitter_language, get_script_sentence_length
from llm_provider import generate_text
from status import info, success, warning, error


def tweet_to_video_script(tweet_content: str, language: str = None) -> dict:
    """
    Adapts a tweet or thread into a YouTube Short script with metadata.

    Args:
        tweet_content: The tweet text (or thread tweets joined by " | ")
        language: Target language for the script

    Returns:
        dict with keys: topic, script, metadata (title, description)
    """
    lang = language or get_twitter_language()
    sentence_length = get_script_sentence_length()

    # Generate an expanded video script from the tweet
    script = generate_text(
        f"Take this tweet and expand it into a {sentence_length}-sentence video script "
        f"in {lang}. The tweet: \"{tweet_content}\". "
        "Get straight to the point, no introductions. "
        "No markdown, no formatting. Only return the script."
    )
    script = re.sub(r"\*", "", script)

    # Generate title
    title = generate_text(
        f"Generate a YouTube Short title (under 100 chars, include hashtags) "
        f"for a video based on this tweet: \"{tweet_content}\". Only return the title."
    )
    if len(title) > 100:
        title = title[:97] + "..."

    # Generate description
    description = generate_text(
        f"Generate a YouTube description for a video with this script: {script}. "
        "Only return the description."
    )

    return {
        "topic": tweet_content[:100],
        "script": script,
        "metadata": {"title": title, "description": description},
    }


def video_script_to_thread(script: str, title: str, num_tweets: int = 4) -> List[str]:
    """
    Adapts a YouTube Short script into a Twitter thread.

    Args:
        script: The video script text
        title: The video title
        num_tweets: Number of tweets in the thread

    Returns:
        List of tweet strings
    """
    completion = generate_text(
        f"Convert this YouTube Short script into a Twitter thread of {num_tweets} tweets. "
        f"Video title: \"{title}\". Script: \"{script}\". "
        "Each tweet must be under 260 characters. "
        "First tweet should hook with a bold claim or question. "
        "Last tweet should have a call-to-action. "
        "Return ONLY a JSON array of strings."
    )
    completion = completion.replace("```json", "").replace("```", "").strip()

    try:
        tweets = json.loads(completion)
        if isinstance(tweets, list) and all(isinstance(t, str) for t in tweets):
            return [re.sub(r"\*", "", t).replace('"', "")[:260] for t in tweets]
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: split by newlines
    lines = [line.strip().lstrip("0123456789.)- ") for line in completion.split("\n") if line.strip()]
    if len(lines) >= 2:
        return [l[:260] for l in lines[:num_tweets]]

    # Last resort: summarize as single tweet
    summary = generate_text(
        f"Summarize this video script as a single tweet under 260 chars: {script}"
    )
    return [re.sub(r"\*", "", summary).replace('"', "")[:260]]


def video_script_to_tweet(script: str, title: str) -> str:
    """
    Adapts a YouTube Short script into a single tweet.

    Args:
        script: The video script text
        title: The video title

    Returns:
        Tweet text string
    """
    completion = generate_text(
        f"Summarize this YouTube Short into a single tweet under 260 characters. "
        f"Title: \"{title}\". Script: \"{script}\". "
        "Make it engaging and include relevant hashtags. Only return the tweet."
    )
    completion = re.sub(r"\*", "", completion).replace('"', "")
    if len(completion) > 260:
        parts = completion[:257].rsplit(" ", 1)
        completion = (parts[0] if len(parts) > 1 else completion[:257]) + "..."
    return completion


def crosspost_tweet_to_youtube(twitter_instance, youtube_instance, tts_instance,
                               tweet_content: str, language: str = None,
                               auto_upload: bool = False) -> Optional[str]:
    """
    Takes a tweet, adapts it to a video script, generates the video, and optionally uploads.

    Args:
        twitter_instance: Twitter class instance (for reference)
        youtube_instance: YouTube class instance
        tts_instance: TTS instance
        tweet_content: The tweet text to adapt
        language: Target language
        auto_upload: Whether to upload after generation

    Returns:
        Path to generated video, or None on failure
    """
    info("Cross-posting tweet to YouTube...")

    adapted = tweet_to_video_script(tweet_content, language)

    # Set YouTube instance state
    youtube_instance.subject = adapted["topic"]
    youtube_instance.script = adapted["script"]
    youtube_instance.metadata = adapted["metadata"]

    if get_verbose():
        info(f"Adapted title: {adapted['metadata']['title']}")

    # Generate image prompts and images
    youtube_instance.generate_prompts()
    for prompt in youtube_instance.image_prompts:
        youtube_instance.generate_image(prompt)

    # Generate TTS
    youtube_instance.generate_script_to_speech(tts_instance)

    # Combine into video
    path = youtube_instance.combine()
    youtube_instance.video_path = path

    success(f"Generated cross-post video: {path}")

    if auto_upload:
        uploaded = youtube_instance.upload_video()
        if uploaded:
            success("Cross-post video uploaded to YouTube!")
        else:
            warning("Cross-post video upload failed.")

    return path


def crosspost_video_to_twitter(youtube_instance, twitter_instance,
                                as_thread: bool = True) -> None:
    """
    Takes the latest YouTube video's script and posts it as a tweet or thread on Twitter.

    Args:
        youtube_instance: YouTube class instance
        twitter_instance: Twitter class instance
        as_thread: If True, post as a thread; otherwise as a single tweet
    """
    script = getattr(youtube_instance, "script", None)
    title = youtube_instance.metadata.get("title", "") if hasattr(youtube_instance, "metadata") else ""

    if not script:
        warning("No video script found. Generate a video first.")
        return

    info("Cross-posting video to Twitter...")

    if as_thread:
        tweets = video_script_to_thread(script, title)
        twitter_instance.post_thread(tweets=tweets)
    else:
        tweet = video_script_to_tweet(script, title)
        twitter_instance.post(text=tweet)

    success("Cross-posted to Twitter!")
