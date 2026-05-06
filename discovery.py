"""Discover all running-race result URLs (with dates) on timataka.net."""

import re
import sys
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, NavigableString

INDEX_URL = "https://www.timataka.net/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Timataka tracker - personal project)"}
REQUEST_DELAY = 0.5

RUNNING_KEYWORDS = ["hlaup", "marathon", "run", "ultra", "milan", "mile"]

NON_RUNNING_KEYWORDS = [
    "criterium", "dh-", "-dh-", "mtb", "xco", "xcm", "xc-", "cx_",
    "enduro", "fismot", "skidamot", "skidaskot", "biathlon",
    "sledahundar", "hjol", "cyclothon", "hyrox",
    "thrithrautin", "triathlon", "gangan",
    "fossavatn", "naeturfossavatn", "scandinavian-cup", "fljotamot",
    "vetrarmot-sled", "rr-", "tt-", "prologue", "motocross", "ulm",
]

DATE_PATTERN = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")


def looks_like_running(slug):
    s = slug.lower()
    if any(bad in s for bad in NON_RUNNING_KEYWORDS):
        return False
    return any(good in s for good in RUNNING_KEYWORDS)


def discover_events():
    resp = requests.get(INDEX_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    events = set()
    for link in soup.find_all("a", href=True):
        href = urljoin(INDEX_URL, link["href"])
        m = re.match(r"https?://(?:www\.)?timataka\.net/([^/?#]+)/?$", href)
        if not m:
            continue
        slug = m.group(1)
        if looks_like_running(slug):
            events.add(f"https://timataka.net/{slug}/")
    return sorted(events)


def discover_result_urls(event_url):
    """Find every cat=overall result URL on a race event page,
    each paired with the race date listed just above it (or None).

    Walks the page in document order so the most recent date
    string seen gets attached to each subsequent result link.
    Returns: dict {url: ISO_date_string or None}
    """
    resp = requests.get(event_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    last_date = None
    results = {}

    body = soup.body or soup
    for element in body.descendants:
        if isinstance(element, NavigableString):
            m = DATE_PATTERN.search(str(element))
            if m:
                day, month, year = m.groups()
                last_date = f"{year}-{int(month):02d}-{int(day):02d}"
        elif getattr(element, "name", None) == "a":
            href = element.get("href")
            if href:
                absolute = urljoin(event_url, href)
                if "cat=overall" in absolute and absolute not in results:
                    results[absolute] = last_date

    return results


def discover_all_result_urls():
    """Index page -> all events -> dict of {result_url: race_date}."""
    print("Fetching the timataka.net index page...")
    events = discover_events()
    print(f"Found {len(events)} running events.\n")

    all_results = {}
    for i, event_url in enumerate(events, 1):
        print(f"[{i}/{len(events)}] {event_url}")
        try:
            url_dates = discover_result_urls(event_url)
            all_results.update(url_dates)
            print(f"  -> {len(url_dates)} distance(s)")
        except Exception as e:
            print(f"  ! failed: {e}")
        time.sleep(REQUEST_DELAY)

    return all_results


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--events":
        for e in discover_events():
            print(e)
    else:
        urls = discover_all_result_urls()
        with_dates = sum(1 for d in urls.values() if d)
        print(f"\n{'=' * 60}")
        print(f"Total: {len(urls)} result URLs ({with_dates} with dates).\n")


if __name__ == "__main__":
    main()