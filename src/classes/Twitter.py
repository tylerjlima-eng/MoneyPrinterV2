import re
import sys
import time
import os
import json

from cache import *
from config import *
from status import *
from llm_provider import generate_text
from typing import List, Optional
from datetime import datetime
from termcolor import colored
from selenium_firefox import *
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class Twitter:
    """
    Class for the Bot, that grows a Twitter account.
    """

    def __init__(
        self, account_uuid: str, account_nickname: str, fp_profile_path: str, topic: str
    ) -> None:
        """
        Initializes the Twitter Bot.

        Args:
            account_uuid (str): The account UUID
            account_nickname (str): The account nickname
            fp_profile_path (str): The path to the Firefox profile

        Returns:
            None
        """
        self.account_uuid: str = account_uuid
        self.account_nickname: str = account_nickname
        self.fp_profile_path: str = fp_profile_path
        self.topic: str = topic

        # Initialize the Firefox profile
        self.options: Options = Options()

        # Set headless state of browser
        if get_headless():
            self.options.add_argument("--headless")

        if not os.path.isdir(fp_profile_path):
            raise ValueError(
                f"Firefox profile path does not exist or is not a directory: {fp_profile_path}"
            )

        # Set the profile path
        self.options.add_argument("-profile")
        self.options.add_argument(fp_profile_path)

        # Set the service
        self.service: Service = Service(GeckoDriverManager().install())

        # Initialize the browser
        self.browser: webdriver.Firefox = webdriver.Firefox(
            service=self.service, options=self.options
        )
        self.wait: WebDriverWait = WebDriverWait(self.browser, 30)

    def post(self, text: Optional[str] = None) -> None:
        """
        Starts the Twitter Bot.

        Args:
            text (str): The text to post

        Returns:
            None
        """
        bot: webdriver.Firefox = self.browser
        verbose: bool = get_verbose()

        bot.get("https://x.com/compose/post")

        post_content: str = text if text is not None else self.generate_post()
        now: datetime = datetime.now()

        print(colored(" => Posting to Twitter:", "blue"), post_content[:30] + "...")
        body = post_content

        text_box = None
        text_box_selectors = [
            (By.CSS_SELECTOR, "div[data-testid='tweetTextarea_0'][role='textbox']"),
            (By.XPATH, "//div[@data-testid='tweetTextarea_0']//div[@role='textbox']"),
            (By.XPATH, "//div[@role='textbox']"),
        ]

        for selector in text_box_selectors:
            try:
                text_box = self.wait.until(EC.element_to_be_clickable(selector))
                text_box.click()
                text_box.send_keys(body)
                break
            except Exception:
                continue

        if text_box is None:
            raise RuntimeError(
                "Could not find tweet text box. Ensure you are logged into X in this Firefox profile."
            )


        post_button = None
        post_button_selectors = [
            (By.XPATH, "//button[@data-testid='tweetButtonInline']"),
            (By.XPATH, "//button[@data-testid='tweetButton']"),
            (By.XPATH, "//span[text()='Post']/ancestor::button"),
        ]

        for selector in post_button_selectors:
            try:
                post_button = self.wait.until(EC.element_to_be_clickable(selector))
                post_button.click()
                break
            except Exception:
                continue

        if post_button is None:
            raise RuntimeError("Could not find the Post button on X compose screen.")

        if verbose:
            print(colored(" => Pressed [ENTER] Button on Twitter..", "blue"))
        time.sleep(2)

        # Add the post to the cache
        self.add_post({"content": body, "date": now.strftime("%m/%d/%Y, %H:%M:%S")})

        success("Posted to Twitter successfully!")

    def get_posts(self) -> List[dict]:
        """
        Gets the posts from the cache.

        Returns:
            posts (List[dict]): The posts
        """
        if not os.path.exists(get_twitter_cache_path()):
            # Create the cache file
            with open(get_twitter_cache_path(), "w") as file:
                json.dump({"accounts": []}, file, indent=4)

        with open(get_twitter_cache_path(), "r") as file:
            parsed = json.load(file)

            # Find our account
            accounts = parsed["accounts"]
            for account in accounts:
                if account["id"] == self.account_uuid:
                    posts = account["posts"]

                    if posts is None:
                        return []

                    # Return the posts
                    return posts

        return []

    def add_post(self, post: dict) -> None:
        """
        Adds a post to the cache.

        Args:
            post (dict): The post to add

        Returns:
            None
        """
        posts = self.get_posts()
        posts.append(post)

        with open(get_twitter_cache_path(), "r") as file:
            previous_json = json.loads(file.read())

            # Find our account
            accounts = previous_json["accounts"]
            for account in accounts:
                if account["id"] == self.account_uuid:
                    account["posts"].append(post)

            # Commit changes
            with open(get_twitter_cache_path(), "w") as f:
                f.write(json.dumps(previous_json))

    def post_thread(self, tweets: Optional[List[str]] = None) -> None:
        """
        Posts a thread (multiple connected tweets) to Twitter/X.

        Args:
            tweets (List[str]): List of tweet texts. If None, generates a thread automatically.
        """
        bot: webdriver.Firefox = self.browser
        verbose: bool = get_verbose()

        thread_tweets: List[str] = tweets if tweets is not None else self.generate_thread()
        now: datetime = datetime.now()

        if verbose:
            info(f"Posting thread with {len(thread_tweets)} tweets...")

        for idx, tweet_text in enumerate(thread_tweets):
            if idx == 0:
                bot.get("https://x.com/compose/post")
            else:
                # Click the "Add another post" button to chain the thread
                add_button = None
                add_button_selectors = [
                    (By.XPATH, "//button[@data-testid='addButton']"),
                    (By.XPATH, "//button[contains(@aria-label, 'Add')]"),
                    (By.XPATH, "//div[@data-testid='addButton']"),
                ]
                for selector in add_button_selectors:
                    try:
                        add_button = self.wait.until(EC.element_to_be_clickable(selector))
                        add_button.click()
                        time.sleep(1)
                        break
                    except Exception:
                        continue

                if add_button is None:
                    warning(f"Could not find 'Add post' button for tweet {idx + 1}. Posting what we have.")
                    break

            # Find the latest textbox (for threads, each new tweet gets a new textbox)
            text_box = None
            text_box_selectors = [
                (By.CSS_SELECTOR, f"div[data-testid='tweetTextarea_{idx}'][role='textbox']"),
                (By.XPATH, f"//div[@data-testid='tweetTextarea_{idx}']//div[@role='textbox']"),
                (By.XPATH, "(//div[@role='textbox'])[last()]"),
            ]

            for selector in text_box_selectors:
                try:
                    text_box = self.wait.until(EC.element_to_be_clickable(selector))
                    text_box.click()
                    text_box.send_keys(tweet_text)
                    break
                except Exception:
                    continue

            if text_box is None:
                warning(f"Could not find textbox for tweet {idx + 1}. Posting what we have.")
                break

            if verbose:
                info(f" => Wrote tweet {idx + 1}/{len(thread_tweets)}: {tweet_text[:40]}...")

        # Click the "Post all" button
        post_button = None
        post_button_selectors = [
            (By.XPATH, "//button[@data-testid='tweetButtonInline']"),
            (By.XPATH, "//button[@data-testid='tweetButton']"),
            (By.XPATH, "//span[text()='Post all']/ancestor::button"),
            (By.XPATH, "//span[text()='Post']/ancestor::button"),
        ]

        for selector in post_button_selectors:
            try:
                post_button = self.wait.until(EC.element_to_be_clickable(selector))
                post_button.click()
                break
            except Exception:
                continue

        if post_button is None:
            raise RuntimeError("Could not find the Post button for the thread.")

        time.sleep(2)

        # Cache the thread as a single post entry
        self.add_post({
            "content": " | ".join(thread_tweets),
            "type": "thread",
            "tweet_count": len(thread_tweets),
            "date": now.strftime("%m/%d/%Y, %H:%M:%S"),
        })

        success(f"Posted thread with {len(thread_tweets)} tweets!")

    def generate_thread(self, num_tweets: int = 4) -> List[str]:
        """
        Generates a Twitter thread (multiple connected tweets) about the topic.

        Args:
            num_tweets (int): Number of tweets in the thread (default 4).

        Returns:
            tweets (List[str]): List of tweet texts.
        """
        completion = generate_text(
            f"Generate a Twitter thread about: {self.topic} in {get_twitter_language()}. "
            f"The thread should have exactly {num_tweets} tweets. "
            "Each tweet must be under 260 characters. "
            "The first tweet should hook the reader with a bold claim or question. "
            "The middle tweets should provide value, tips, or insights. "
            "The last tweet should have a call-to-action. "
            "Return ONLY a JSON array of strings, one per tweet. Example: "
            '["First tweet here", "Second tweet here", "Third tweet here", "Last tweet here"]'
        )

        # Clean markdown
        completion = completion.replace("```json", "").replace("```", "").strip()

        try:
            tweets = json.loads(completion)
            if isinstance(tweets, list) and all(isinstance(t, str) for t in tweets):
                # Truncate any that are too long
                result = []
                for t in tweets:
                    t = re.sub(r"\*", "", t).replace('"', "")
                    if len(t) >= 260:
                        parts = t[:257].rsplit(" ", 1)
                        t = (parts[0] if len(parts) > 1 else t[:257]) + "..."
                    result.append(t)
                return result
        except (json.JSONDecodeError, TypeError):
            pass

        # Fallback: split by newlines and filter
        lines = [line.strip().lstrip("0123456789.)- ") for line in completion.split("\n") if line.strip()]
        if len(lines) >= 2:
            return [l[:260] for l in lines[:num_tweets]]

        # Last resort: generate single tweets
        warning("Could not parse thread. Falling back to single tweet.")
        return [self.generate_post()]

    def generate_post(self) -> str:
        """
        Generates a post for the Twitter account based on the topic.

        Returns:
            post (str): The post
        """
        completion = generate_text(
            f"Generate a Twitter post about: {self.topic} in {get_twitter_language()}. "
            "The Limit is 2 sentences. Choose a specific sub-topic of the provided topic."
        )

        if get_verbose():
            info("Generating a post...")

        if completion is None:
            error("Failed to generate a post. Please try again.")
            sys.exit(1)

        # Apply Regex to remove all *
        completion = re.sub(r"\*", "", completion).replace('"', "")

        if get_verbose():
            info(f"Length of post: {len(completion)}")
        if len(completion) >= 260:
            parts = completion[:257].rsplit(" ", 1)
            truncated = parts[0] if len(parts) > 1 else completion[:257]
            return truncated + "..."

        return completion
