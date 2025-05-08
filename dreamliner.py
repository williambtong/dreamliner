# © 2025 William Tong. All rights reserved.

import os, json
from datetime import datetime
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout # type: ignore

# ——— CONFIG ———
SEARCH_PAGE = "https://www.aa.com/booking/search/find-flights"

raw_targets = os.getenv("SEARCH_TARGETS")
SEARCH_TARGETS = json.loads(raw_targets)

PUSHOVER_USER  = os.getenv("PUSHOVER_USER")
PUSHOVER_TOKEN = os.getenv("PUSHOVER_TOKEN")

def build_url(origin: str, dest: str, date: str):
    return f"https://www.aa.com/booking/search?locale=en_US&pax=1&adult=1&type=OneWay&searchType=Award&cabin=first&carriers=ALL&travelType=personal&slices=%5B%7B%22orig%22:%22{origin}%22,%22origNearby%22:false,%22dest%22:%22{dest}%22,%22destNearby%22:false,%22date%22:%22{date}%22%7D%5D"

def send_pushover(title: str, message: str, priority=0):
    print(f"[*] Sending Pushover → {title}", flush=True)
    requests.post(
        "https://api.pushover.net/1/messages.json",
        data={
            "token":   PUSHOVER_TOKEN,
            "user":    PUSHOVER_USER,
            "title":   title,
            "message": message,
            "priority": priority
        }
    )

def check_first_class(page, url: str, target):
    """Navigate page to URL, wait for results, check for First-Class header."""
    page.goto(url, timeout=60_000)
    page.wait_for_url("**/booking/choose-flights/**", timeout=60_000)

    page.wait_for_selector(".cabin-header", timeout=30_000)
    has_first = page.query_selector(".cabin-header.cabin-first") is not None

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if has_first:
        msg = f"[{ts}] {target['origin']} -> {target['dest']} on {target['date']}"
        print(f"[{ts}] 🎉 First-Class Available", flush=True)
        send_pushover("🎉 First-Class Available", msg)
    else:
        print(f"[{ts}] No First-Class", flush=True)


def check_business_class(page, url: str, target):
    """Navigate page to URL, wait for results, check for Business-Class header."""
    page.goto(url, timeout=60_000)
    page.wait_for_url("**/booking/choose-flights/**", timeout=60_000)

    page.wait_for_selector(".cabin-header", timeout=30_000)
    has_business = page.query_selector(".cabin-header.cabin-business") is not None

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if has_business:
        msg = f"[{ts}] {target['origin']} -> {target['dest']} on {target['date']}"
        print(f"[{ts}] 🎉 Business-Class Available", flush=True)
        send_pushover("🎉 Business-Class Available", msg)
    else:
        print(f"[{ts}] No Business-Class", flush=True)

def parse_miles(raw: str) -> int:
    num = float(raw.upper().replace("K", "")) * 1000
    return int(num)

def check_miles(page, url: str, target):
    """Navigate page to URL, wait for results, check carousel price against thresholds."""
    page.goto(url, timeout=60_000)
    page.wait_for_url("**/booking/choose-flights/**", timeout=60_000)

    # find the selected carousel slide
    slide = page.wait_for_selector("button.swiper-slide.selected-slide", timeout=30_000)
    price_span = slide.query_selector("span.price.weekly-price.award")
    raw = price_span.inner_text().strip()
    miles = parse_miles(raw)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    thresholds = target["thresholds"]
    if miles in thresholds:
        msg = f"[{ts}] {target['origin']} -> {target['dest']} on {target['date']}"
        print(f"[{ts}] 🎉 Found {raw}", flush=True)
        send_pushover(f"🎉 Found {raw}", msg)
    else:
        print(f"[{ts}] Found {raw}", flush=True)

def run_checks():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/135.0.7049.115 Safari/537.36"
        ))

        # Prime session
        print(f"[*] Priming session via find-flights page", flush=True)
        page.goto(SEARCH_PAGE, timeout=60_000)
        print("[*] Waiting for advanced-search form to load", flush=True)
        page.wait_for_selector("app-advanced-search form", timeout=30_000)

        # Run each target check back-to-back
        for i, target in enumerate(SEARCH_TARGETS):
            url = build_url(target["origin"], target["dest"], target["date"])
            mode = target["mode"]
            print(f"\n[*] → Checking ({mode}) for target {i}", flush=True)
            try:
                if mode == "first":
                    check_first_class(page, url, target)
                elif mode == "business":
                    check_business_class(page, url, target)
                elif mode == "miles":
                    check_miles(page, url, target)
                else:
                    print(f"[!] Unknown mode: {mode}", flush=True)
            except PlaywrightTimeout as e:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                err = f"[{ts}] Timeout during {mode} check for {target['origin']} -> {target['dest']} on {target['date']}"
                print("Timeout", flush=True)
                send_pushover("AA Checker Timeout", err, -1)
            except Exception as e:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                err = f"[{ts}] ERROR during {mode} check for {target['origin']} -> {target['dest']} on {target['date']}: {e}"
                print("ERROR", flush=True)
                send_pushover("AA Checker Error", err)

        browser.close()

if __name__ == "__main__":
    print("[*] Starting Dreamliner", flush=True)
    run_checks()