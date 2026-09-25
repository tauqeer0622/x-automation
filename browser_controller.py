import os
import time
import random
import urllib.parse
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright, BrowserContext, Page
from config import config
from database import add_log, is_user_restricted, add_restricted_user

class BrowserController:
    def __init__(self):
        self._playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.is_running = False

    def is_alive(self) -> bool:
        """Verifies if the browser and page are still alive and responsive."""
        if not self.is_running or not self.context or not self.page:
            return False
        try:
            return not self.page.is_closed()
        except Exception:
            return False

    def ensure_active(self, headless: Optional[bool] = None) -> bool:
        """Ensures a live browser session is ready, auto-recovering if closed."""
        if not self.is_alive():
            self.stop()
            return self.start(headless=headless)
        return True

    def start(self, headless: Optional[bool] = None) -> bool:
        """Starts Playwright with persistent context to preserve login state."""
        if self.is_alive():
            return True

        self.stop()  # Clean any stale resources

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

            # Page initialization & anti-detection script
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            # If X_AUTH_TOKEN is configured, inject cookie directly
            if config.x_auth_token and config.x_auth_token.strip():
                token = config.x_auth_token.strip()
                self.context.add_cookies([
                    {"name": "auth_token", "value": token, "domain": ".x.com", "path": "/", "httpOnly": True, "secure": True},
                    {"name": "auth_token", "value": token, "domain": ".twitter.com", "path": "/", "httpOnly": True, "secure": True}
                ])
                add_log("INFO", "Injected X auth_token cookie into browser session.")

            self.is_running = True
            add_log("INFO", f"Browser controller started (headless={use_headless})")
            return True
        except Exception as e:
            add_log("ERROR", f"Failed to start browser: {str(e)}")
            self.stop()
            return False

    def stop(self):
        """Closes browser and cleans up resources cleanly."""
        try:
            if self.context:
                self.context.close()
        except Exception:
            pass

        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass

        self.context = None
        self.page = None
        self._playwright = None
        self.is_running = False

    def is_logged_in(self) -> bool:
        """Checks if the current session is logged into X."""
        if not self.ensure_active():
            return False
        try:
            self.page.goto("https://x.com/home", timeout=25000, wait_until="domcontentloaded")
            time.sleep(2)
            account_btn = self.page.query_selector('[data-testid="SideNav_AccountSwitcher_Button"], [data-testid="AppTabBar_Profile_Link"]')
            return account_btn is not None
        except Exception as e:
            add_log("WARN", f"Session check encountered: {str(e)}")
            return False

    def search_tweets(self, query: str, max_results: int = 10, retry: bool = True) -> List[Dict[str, Any]]:
        """
        Searches X for the query (using 'Live' tab for latest tweets)
        and extracts tweet elements with auto-recovery.
        """
        if not self.ensure_active():
            return []

        results: List[Dict[str, Any]] = []
        encoded_query = urllib.parse.quote(f"{query} -is:retweet -is:reply")
        search_url = f"https://x.com/search?q={encoded_query}&f=live"

        try:
            add_log("INFO", f"Scanning X for: '{query}' (Original Posts Only)")
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
                    # Skip if this tweet is a reply or comment in a thread
                    art_text = art.inner_text()
                    if "Replying to @" in art_text or "replying to @" in art_text:
                        continue

                    # Extract Tweet status URL and ID
                    status_link = art.query_selector('a[href*="/status/"]')
                    if not status_link:
                        continue

                    href = status_link.get_attribute("href")
                    if not href or "/status/" not in href:
                        continue

                    tweet_id = href.split("/status/")[1].split("?")[0].split("/")[0]
                    tweet_url = f"https://x.com{href}" if href.startswith("/") else href

                    # Extract Author handle, display name & badges
                    author = "unknown"
                    display_name = ""
                    badge_label = ""
                    user_elem = art.query_selector('[data-testid="User-Name"]')
                    if user_elem:
                        user_text = user_elem.inner_text()
                        display_name = user_text
                        for part in user_text.split():
                            if part.startswith("@"):
                                author = part.replace("@", "")
                                break
                        badge_elem = user_elem.query_selector('svg[data-testid="icon-verified"], [aria-label*="Government"], [aria-label*="Official"], [aria-label*="State-affiliated"]')
                        if badge_elem:
                            badge_label = badge_elem.get_attribute("aria-label") or ""

                    # RESTRICTED USER FILTER: Check if user was previously flagged as having restricted replies
                    if is_user_restricted(author):
                        continue

                    # PROTECTED ACCOUNT FILTER: Skip private/protected accounts (lock icon)
                    lock_elem = art.query_selector('svg[data-testid="icon-lock"], [aria-label*="Protected"]')
                    if lock_elem:
                        add_restricted_user(author, reason="protected_account")
                        continue


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
            err_str = str(e)
            add_log("ERROR", f"Search failed for '{query}': {err_str}")
            # If browser/page was closed, auto-restart and retry once
            if retry and ("closed" in err_str.lower() or "crashed" in err_str.lower()):
                add_log("WARN", "Browser was closed. Auto-recovering session...")
                self.stop()
                if self.start():
                    return self.search_tweets(query, max_results=max_results, retry=False)
            return []

    def post_reply(self, tweet_id: str, tweet_url: str, reply_text: str, dry_run: bool = True, retry: bool = True) -> Dict[str, Any]:
        """
        Posts a reply to a tweet with auto-recovery on browser disconnect.
        If dry_run is True, simulates the action without clicking the final submit button.
        """
        if dry_run:
            add_log("INFO", f"[DRY RUN] Would reply to {tweet_url}: \"{reply_text}\"")
            return {"success": True, "mode": "dry_run", "message": "Dry run simulated successfully"}

        if not self.ensure_active():
            return {"success": False, "mode": "live", "message": "Browser is not running and could not be started"}

        try:
            target_url = tweet_url if tweet_url else f"https://x.com/i/web/status/{tweet_id}"
            add_log("INFO", f"Navigating to tweet: {target_url}")
            self.page.goto(target_url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(random.uniform(2.5, 4.0))


            # Look for reply input box on the tweet page
            # 1. First try direct inline reply box
            reply_box = self.page.query_selector('[data-testid="tweetTextarea_0"]')

            # 2. If not visible, click the reply icon button on the article
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
                # Extract author from page and add to restricted list so future tweets are auto-skipped
                author_hdr = self.page.query_selector('[data-testid="User-Name"]')
                if author_hdr:
                    for part in author_hdr.inner_text().split():
                        if part.startswith("@"):
                            flagged_user = part.replace("@", "")
                            add_restricted_user(flagged_user, reason="replies_restricted")
                            add_log("INFO", f"Added @{flagged_user} to restricted users list (author restricts replies).")
                            break

                page_text = self.page.inner_text("body").lower()
                if "these posts are protected" in page_text or "only confirmed followers" in page_text:
                    err_msg = "Skipped: Post or account is protected / private."
                    add_log("INFO", f"Tweet {tweet_id}: {err_msg}")
                    return {"success": False, "mode": "live", "message": err_msg, "reason": "restricted"}

                if "who can reply" in page_text or "can reply" in page_text or "replies are limited" in page_text:
                    err_msg = "Skipped: Post author restricted replies (e.g. only accounts they follow or verified users can reply)."
                    add_log("INFO", f"Tweet {tweet_id}: {err_msg}")
                    return {"success": False, "mode": "live", "message": err_msg, "reason": "restricted"}

                err_msg = "Could not find reply input box (Post replies restricted by author or thread closed)."
                add_log("INFO", f"Tweet {tweet_id}: {err_msg}")
                return {"success": False, "mode": "live", "message": err_msg, "reason": "restricted"}

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
            time.sleep(random.uniform(2.5, 4.0))

            add_log("SUCCESS", f"Live comment successfully posted to tweet {tweet_id}!")
            return {"success": True, "mode": "live", "message": "Reply published"}

        except Exception as e:
            err_msg = str(e)
            add_log("ERROR", f"Failed to post reply: {err_msg}")
            # If browser/page was closed, auto-recover and retry once
            if retry and ("closed" in err_msg.lower() or "crashed" in err_msg.lower()):
                add_log("WARN", "Browser disconnected during reply. Auto-recovering session...")
                self.stop()
                if self.start():
                    return self.post_reply(tweet_id, tweet_url, reply_text, dry_run=dry_run, retry=False)
            return {"success": False, "mode": "live", "message": f"Failed to post reply: {err_msg}"}

browser_controller = BrowserController()
