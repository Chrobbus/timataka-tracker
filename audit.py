"""Inspect a single timataka.net page to see exactly what our parser sees.

Usage:
    python audit.py <url>

Example:
    python audit.py "https://timataka.net/raudavatnultra2025/urslit/?race=1&cat=overall"
"""

import sys
import requests
from bs4 import BeautifulSoup

from scraper import HEADERS, extract_metadata, parse_results, normalize_column_name


def audit(url):
    print(f"Fetching: {url}\n")

    resp = requests.get(url, headers=HEADERS, timeout=15)
    print(f"HTTP status:  {resp.status_code}")
    print(f"Final URL:    {resp.url}")
    print(f"Page size:    {len(resp.text):,} chars")

    soup = BeautifulSoup(resp.text, "html.parser")

    title = soup.find("title")
    print(f"Page title:   {title.get_text(strip=True) if title else '(none)'}")

    print("\n--- Headings (h1-h4) ---")
    for tag_name in ["h1", "h2", "h3", "h4"]:
        for h in soup.find_all(tag_name):
            text = h.get_text(strip=True)
            if text:
                print(f"  <{tag_name}> {text!r}")

    print("\n--- Metadata our scraper extracts ---")
    metadata = extract_metadata(soup, url)
    for key, value in metadata.items():
        print(f"  {key}: {value}")

    tables = soup.find_all("table")
    print(f"\n--- Tables found: {len(tables)} ---")

    if tables:
        first = tables[0]
        header_row = first.find("tr")
        if header_row:
            print("\nFirst table column headers (raw -> normalized):")
            for cell in header_row.find_all(["th", "td"]):
                raw = cell.get_text(strip=True)
                normalized = normalize_column_name(raw)
                marker = "" if raw.lower() == normalized or raw == "#" else "  <- TRANSLATED"
                print(f"  {raw!r:30} -> {normalized!r}{marker}")
        rows = first.find_all("tr")
        print(f"\nFirst table has {len(rows)} <tr> rows total.")

    runners = parse_results(soup)
    print(f"\n--- parse_results() returned {len(runners)} runners ---")
    if runners:
        print("\nFirst 3 parsed:")
        for r in runners[:3]:
            print(f"  {r}")
    else:
        print("\n  (Empty — usually means the rank or name column wasn't recognized.)")
        print("  Check the column headers above. Any unrecognised ones may need")
        print("  to be added to COLUMN_NAME_MAP in scraper.py.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python audit.py <url>")
        sys.exit(1)
    audit(sys.argv[1])