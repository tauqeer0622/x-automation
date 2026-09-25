import time
import random
import threading
from typing import Optional, Dict, Any
from config import config
from database import (
    is_tweet_processed, save_post, update_post_status,
    save_comment, get_daily_comment_count, add_log,
    is_user_restricted
)
from comment_generator import generator
from browser_controller import browser_controller

class AutomationEngine:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.state = "stopped"  # "stopped", "running", "paused"
        self.current_activity = "Idle"
        self.last_run_time: Optional[float] = None

    def get_status(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "activity": self.current_activity,
            "dry_run": config.dry_run,
            "daily_limit": config.daily_comment_limit,
            "comments_today": get_daily_comment_count(),
            "browser_active": browser_controller.is_running
        }

    def start(self):
        """Starts the autonomous background loop."""
        if self.state == "running":
            return
        
        self._stop_event.clear()
        self.state = "running"
        self.current_activity = "Initializing automation engine..."
        add_log("INFO", "Automation engine started")
        
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stops the autonomous loop and signals worker thread."""
        if self.state == "stopped":
            return

        self.current_activity = "Stopping..."
        self._stop_event.set()
        add_log("INFO", "Automation engine stopping...")

        # Wait briefly for thread to finish cleanly if alive
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=4.0)

        self.state = "stopped"
        self.current_activity = "Idle (Stopped)"
        add_log("INFO", "Automation engine stopped")

    def _sleep_with_cancel(self, seconds: float) -> bool:
        """Sleeps in small increments, returning False if cancelled."""
        steps = int(seconds * 2)
        for _ in range(steps):
            if self._stop_event.is_set():
                return False
            time.sleep(0.5)
        return True

    def _run_loop(self):
        """Continuous execution loop (owns browser lifecycle on this thread)."""
        self.current_activity = "Starting browser session..."
        try:
            if not browser_controller.start():
                self.state = "stopped"
                self.current_activity = "Browser launch failed. Engine halted."
                add_log("ERROR", "Engine stopped due to browser startup failure.")
                return

            while not self._stop_event.is_set():
                try:
                    # 1. Check daily quota
                    comments_today = get_daily_comment_count()
                    if comments_today >= config.daily_comment_limit:
                        self.current_activity = f"Daily limit reached ({comments_today}/{config.daily_comment_limit}). Cooldown active."
                        add_log("WARN", f"Daily comment quota reached ({comments_today}). Pausing until quota window refreshes.")
                        if not self._sleep_with_cancel(1800):  # Wait 30 mins
                            break
                        continue

                    # 2. Iterate through configured target keywords
                    keywords = config.target_keywords
                    if not keywords:
                        self.current_activity = "No target keywords configured."
                        if not self._sleep_with_cancel(10):
                            break
                        continue

                    for keyword in keywords:
                        if self._stop_event.is_set():
                            break

                        self.current_activity = f"Searching posts for: '{keyword}'"
                        posts = browser_controller.search_tweets(keyword, max_results=6)

                        for post in posts:
                            if self._stop_event.is_set():
                                break

                            tweet_id = post["tweet_id"]
                            author = post["author"]
                            content = post["content"]
                            url = post["url"]

                            # Check deduplication
                            if is_tweet_processed(tweet_id):
                                continue

                            # Check negative keywords
                            content_lower = content.lower()
                            if any(neg in content_lower for neg in config.negative_keywords):
                                save_post(tweet_id, author, content, keyword, url, status="ignored")
                                add_log("INFO", f"Skipped tweet {tweet_id} (matched negative filter)")
                                continue


                            # Check restricted / locked reply user blacklist
                            if is_user_restricted(author):
                                save_post(tweet_id, author, content, keyword, url, status="ignored_restricted")
                                continue

                            # Record discovered post
                            save_post(tweet_id, author, content, keyword, url, status="scanned")

                            # Generate contextual comment
                            self.current_activity = f"Generating contextual reply for @{author}..."
                            reply_text = generator.generate(content, author, keyword)

                            # Post or dry-run reply
                            self.current_activity = f"Replying to @{author} ({'DRY RUN' if config.dry_run else 'LIVE'})..."
                            result = browser_controller.post_reply(
                                tweet_id=tweet_id,
                                tweet_url=url,
                                reply_text=reply_text,
                                dry_run=config.dry_run
                            )

                            status = "success" if result["success"] else ("restricted" if result.get("reason") == "restricted" else "failed")
                            mode = "dry_run" if config.dry_run else "live"
                            error_msg = result.get("message") if not result["success"] else None

                            save_comment(tweet_id, author, reply_text, mode, status, error_msg)
                            update_post_status(tweet_id, status="replied" if result["success"] else status)

                            # If comment succeeded, apply pacing delay
                            if result["success"]:
                                delay = random.randint(config.min_delay_seconds, config.max_delay_seconds)
                                self.current_activity = f"Cooling down for {delay}s (Anti-spam protection)..."
                                add_log("INFO", f"Pacing delay active: waiting {delay}s before next interaction.")
                                if not self._sleep_with_cancel(delay):
                                    break

                        # Pause between keywords
                        if not self._sleep_with_cancel(random.randint(10, 20)):
                            break

                    # Cycle pause
                    self.current_activity = "Cycle completed. Waiting for next scan..."
                    if not self._sleep_with_cancel(60):
                        break

                except Exception as e:
                    add_log("ERROR", f"Error in automation loop: {str(e)}")
                    self.current_activity = f"Recovering from error: {str(e)}"
                    if not self._sleep_with_cancel(15):
                        break

        finally:
            # Always close browser from the same thread that started it
            try:
                browser_controller.stop()
            except Exception:
                pass
            self.state = "stopped"
            self.current_activity = "Idle (Stopped)"
            add_log("INFO", "Automation engine thread finished.")

engine = AutomationEngine()
