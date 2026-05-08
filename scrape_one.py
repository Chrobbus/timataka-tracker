"""Scrape and save a single race URL.

Usage: python scrape_one.py <url>

Automatically derives the event page (e.g. timataka.net/gamlarshlaup2025/)
from the result URL and looks up the race date there before saving.
"""

import re
import sys

from database import init_db
from discovery import discover_result_urls
from scraper import scrape_and_save

if len(sys.argv) < 2:
    print("Usage: python scrape_one.py <url>")
    sys.exit(1)

url = sys.argv[1]
init_db()

# A result URL looks like 'https://timataka.net/<event-slug>/urslit/?race=1&cat=overall'.
# Derive the event page URL (everything up to and including the slug) so we
# can read the race date from there.
race_date = None
event_match = re.match(r"(https?://(?:www\.)?timataka\.net/[^/]+/)", url)
if event_match:
    event_url = event_match.group(1)
    print(f"Looking up race date from {event_url}")
    try:
        url_dates = discover_result_urls(event_url)
        race_date = url_dates.get(url)
        if race_date:
            print(f"  -> date: {race_date}")
        else:
            print("  -> URL not in event-page links (date will be missing)")
    except Exception as e:
        print(f"  -> couldn't fetch event page: {e}")

scrape_and_save(url, race_date=race_date)
print("Done.")