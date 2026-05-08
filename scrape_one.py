"""Scrape and save a single race URL.

Usage: python scrape_one.py <url>

Useful for one-off additions (e.g. when timataka fixes a previously broken
page) without re-running the full discovery + scrape pipeline.
"""

import sys

from database import init_db
from scraper import scrape_and_save

if len(sys.argv) < 2:
    print("Usage: python scrape_one.py <url>")
    sys.exit(1)

url = sys.argv[1]
init_db()
scrape_and_save(url)
print("Done.")