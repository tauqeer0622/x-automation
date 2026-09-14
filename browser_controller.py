import os
import time
import random
import urllib.parse
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright, BrowserContext, Page
from config import config
from database import add_log

class BrowserController:
    def __init__(self):
        self._playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.is_running = False

    def start(self, headless: Optional[bool] = None) -> bool:
        """Starts Playwright with persistent context to preserve login state."""
        if self.is_running and self.context:
            return True

        use_headless = config.headless if headless is None else headless
        data_dir = os.path.abspath(config.browser_data_dir)
        os.makedirs(data_dir, exist_ok=True)

        try:
            self._playwright = sync_playwright().start()
            
            # Anti-detection browser launch arguments
            args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--start-maximized"
            ]

            self.context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=data_dir,
                headless=use_headless,
                viewport={"width": 1280, "height": 850},
                args=args,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )

            # Prevent navigator.webdriver flag
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            self.is_running = True
            add_log("INFO", f"Browser controller started (headless={use_headless})")
            return True
        except Exception as e:
            add_log("ERROR", f"Failed to start browser: {str(e)}")
            self.stop()
            return False

    def stop(self):
        """Closes browser and cleans up resources."""
        try:
            if self.context:
                self.context.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        finally:
            self.context = None
            self.page = None
            self._playwright = None
            self.is_running = False
            add_log("INFO", "Browser controller stopped")

    def is_logged_in(self) -> bool:
        """Checks if the current session is logged into X."""
        if not self.is_running or not self.page:
            return False
        try:
            self.page.goto("https://x.com/home", timeout=25000, wait_until="domcontentloaded")
            time.sleep(2)
            # Check for standard logged-in navigation items
            account_btn = self.page.query_selector('[data-testid="SideNav_AccountSwitcher_Button"], [data-testid="AppTabBar_Profile_Link"]')
            return account_btn is not None
        except Exception as e:
            add_log("WARN", f"Session check encountered: {str(e)}")
            return False

    def search_tweets(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Searches X for the query (using 'Live' tab for latest tweets)
        and extracts tweet elements.
        """
        if not self.is_running or not self.page:
            if not self.start():
                return []

        results: List[Dict[str, Any]] = []
        encoded_query = urllib.parse.quote(f"{query} lang:en -is:retweet")
        search_url = f"https://x.com/search?q={encoded_query}&f=live"

        try:
            add_log("INFO", f"Scanning X for: '{query}'")
            self.page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(random.uniform(2.5, 4.0))

            # Scroll once or twice to populate feed
            for _ in range(2):
                self.page.mouse.wheel(0, 400)
                time.sleep(random.uniform(1.0, 1.8))

            articles = self.page.query_selector_all('article[data-testid="tweet"]')
            for art in articles:
                if len(results) >= max_results:
                    break

                try:
                    # Extract Tweet status URL and ID
                    status_link = art.query_selector('a[href*="/status/"]')
                    if not status_link:
                        continue
                    
                    href = status_link.get_attribute("href")
                    if not href or "/status/" not in href:
                        continue
                    
                    tweet_id = href.split("/status/")[1].split("?")[0].split("/")[0]
                    tweet_url = f"https://x.com{href}" if href.startswith("/") else href

                    # Extract Author handle
                    author = "unknown"
                    user_elem = art.query_selector('[data-testid="User-Name"]')
                    if user_elem:
                        user_text = user_elem.inner_text()
                        for part in user_text.split():
                            if part.startswith("@"):
                                author = part.replace("@", "")
                                break

                    # Extract Tweet Text
                    text_elem = art.query_selector('[data-testid="tweetText"]')
                    tweet_text = text_elem.inner_text() if text_elem else ""

                    if tweet_id and tweet_text:
                        results.append({
                            "tweet_id": tweet_id,
                            "author": author,
                            "content": tweet_text,
                            "url": tweet_url,
                            "matched_keyword": query
                        })
                except Exception:
                    continue

            add_log("INFO", f"Found {len(results)} tweets for query '{query}'")
            return results
        except Exception as e:
            add_log("ERROR", f"Search failed for '{query}': {str(e)}")
            return []

    def post_reply(self, tweet_id: str, tweet_url: str, reply_text: str, dry_run: bool = True) -> Dict[str, Any]:
        """
        Posts a reply to a tweet.
        If dry_run is True, simulates the action without clicking the final submit button.
        """
        if dry_run:
            add_log("INFO", f"[DRY RUN] Would reply to {tweet_url}: \"{reply_text}\"")
            return {"success": True, "mode": "dry_run", "message": "Dry run simulated successfully"}

        if not self.is_running or not self.page:
            if not self.start():
                return {"success": False, "mode": "live", "message": "Browser is not running"}

        try:
            target_url = tweet_url if tweet_url else f"https://x.com/i/web/status/{tweet_id}"
            add_log("INFO", f"Navigating to tweet: {target_url}")
            self.page.goto(target_url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(random.uniform(2.5, 4.0))

            # Look for reply input box on the tweet page
            # 1. First try direct inline reply box: [data-testid="tweetTextarea_0"]
            reply_box = self.page.query_selector('[data-testid="tweetTextarea_0"]')
            
            # 2. If not visible, click the reply icon button to open modal
            if not reply_box:
                reply_btn = self.page.query_selector('article button[data-testid="reply"]')
                if reply_btn:
                    reply_btn.click()
                    time.sleep(random.uniform(1.2, 2.0))
                    reply_box = self.page.query_selector('[data-testid="tweetTextarea_0"]')

            if not reply_box:
                # Also try generic textbox role
                reply_box = self.page.query_selector('div[role="textbox"]')

            if not reply_box:
                err_msg = "Could not find reply input box (May require login or post replies are restricted)."
                add_log("WARN", err_msg)
                return {"success": False, "mode": "live", "message": err_msg}

            # Focus and simulate human typing
            reply_box.click()
            time.sleep(random.uniform(0.5, 1.0))
            
            # Type naturally with variable keystroke delay
            for char in reply_text:
                self.page.keyboard.type(char)
                time.sleep(random.uniform(0.02, 0.08))

            time.sleep(random.uniform(1.5, 2.5))

            # Find Post / Reply button
            submit_btn = self.page.query_selector('[data-testid="tweetButtonInline"], [data-testid="tweetButton"]')
            if not submit_btn:
                err_msg = "Reply text entered but could not locate submit button."
                add_log("ERROR", err_msg)
                return {"success": False, "mode": "live", "message": err_msg}

            # Check if button is enabled
            if submit_btn.is_disabled():
                err_msg = "Submit reply button is disabled."
                add_log("ERROR", err_msg)
                return {"success": False, "mode": "live", "message": err_msg}

            # Click submit
            submit_btn.click()
            time.sleep(random.uniform(2.0, 3.5))

            add_log("SUCCESS", f"Live comment successfully posted to tweet {tweet_id}!")
            return {"success": True, "mode": "live", "message": "Reply published"}

        except Exception as e:
            err_msg = f"Failed to post reply: {str(e)}"
            add_log("ERROR", err_msg)
            return {"success": False, "mode": "live", "message": err_msg}

browser_controller = BrowserController()
