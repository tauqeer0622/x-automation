import time
import sys
from browser_controller import browser_controller
from database import add_log

def main():
    print("=" * 60)
    print("   X ACCOUNT LOGIN HELPER")
    print("=" * 60)
    print("[*] Launching visible Chrome browser...")
    
    success = browser_controller.start(headless=False)
    if not success or not browser_controller.page:
        print("[!] Failed to launch browser. Please ensure Playwright Chromium is installed.")
        sys.exit(1)

    print("[*] Navigating to https://x.com/login ...")
    browser_controller.page.goto("https://x.com/login")
    
    print("\n" + "=" * 60)
    print(" ACTION REQUIRED:")
    print(" 1. In the browser window that just opened, log into your new X account.")
    print(" 2. Complete any 2FA or verification steps if prompted.")
    print(" 3. Once you see your X home timeline / feed, come back here.")
    print("=" * 60 + "\n")

    try:
        input(">>> Press [ENTER] in this terminal when you have completed login... ")
    except KeyboardInterrupt:
        print("\n[*] Aborted by user.")
    
    # Verify login
    print("[*] Checking if session is active...")
    if browser_controller.is_logged_in():
        print("\n[SUCCESS] Login verified! Your session is permanently saved to ./browser_data.")
        add_log("SUCCESS", "Manual login verified and saved.")
    else:
        print("\n[NOTE] Could not auto-detect the home timeline, but your browser data has been saved.")
    
    browser_controller.stop()
    print("[*] Browser closed. You are ready to start the automation!")

if __name__ == "__main__":
    main()
