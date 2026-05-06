"""Scraper for timataka.net race results — saves to SQLite."""

import re
import time
import requests
from bs4 import BeautifulSoup

from database import init_db, save_race, find_runner, is_url_scraped, get_connection
from discovery import discover_all_result_urls

HEADERS = {"User-Agent": "Mozilla/5.0 (Timataka tracker - personal project)"}
REQUEST_DELAY = 0.5

EXTRA_URLS = []

# Translates Icelandic-language column headers into our standard English keys.
COLUMN_NAME_MAP = {
    "sæti": "rank",                                # Icelandic for rank
    "rásnr.": "bib", "rásnr": "bib", "bib nr": "bib",
    "nafn": "name",
    "f.ár": "year", "fár": "year", "fæðingarár": "year",
    "félag": "club", "félagsskapur": "club",
    "þjóðerni": "nationality",
    "lokatími": "time", "tími": "time",
    "flögutími": "chiptime", "nettótími": "chiptime",
    "vegalengd": "distance",                       # for timed events (km covered)
    "hringir": "laps", "hringur": "laps",
}

DISTANCE_OVERRIDES = {
    "hlaupaseriafh": 5.0,
}

NAMED_DISTANCE_PATTERNS = [
    (re.compile(r"^marathon$", re.I), 42.2),
    (re.compile(r"^maraþon$", re.I), 42.2),
    (re.compile(r"^maraton$", re.I), 42.2),
    (re.compile(r"^half[\s-]*marathon$", re.I), 21.1),
    (re.compile(r"^hálfmaraþon$", re.I), 21.1),
    (re.compile(r"^halfmaraton$", re.I), 21.1),
]


def normalize_column_name(raw):
    name = raw.strip().lower()
    if name == "#":
        return "rank"
    return COLUMN_NAME_MAP.get(name, name)


def fetch_page(url):
    response = requests.get(url, headers=HEADERS, timeout=10)
    response.raise_for_status()
    return response.text


def extract_distance(soup):
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        text = tag.get_text(strip=True)
        if not text:
            continue
        if re.search(r"\b\d{4}\b", text):
            continue
        lowered = text.lower()
        m = re.search(r"\b(\d+(?:[,\.]\d+)?)\s*k(?:m|\b)", lowered)
        if m:
            try:
                value = float(m.group(1).replace(",", "."))
                if 0.5 <= value <= 250:
                    return value
            except ValueError:
                pass
        for pattern, dist in NAMED_DISTANCE_PATTERNS:
            if pattern.match(text):
                return dist
    return None


def extract_metadata(soup, url):
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    title = title.replace("TÍMATAKA:", "").strip()

    year_match = re.search(r"(\d{4})", title)
    year = int(year_match.group(1)) if year_match else None

    if year is None:
        slug_match = re.search(r"timataka\.net/([^/?#]+)", url)
        if slug_match:
            slug_year_match = re.search(r"(\d{4})", slug_match.group(1))
            if slug_year_match:
                year = int(slug_year_match.group(1))

    name = re.sub(r"\s*\d{4}\s*$", "", title).strip() or title

    distance_km = extract_distance(soup)
    if distance_km is None:
        for slug_fragment, override in DISTANCE_OVERRIDES.items():
            if slug_fragment in url.lower():
                distance_km = override
                break

    return {"name": name, "year": year, "distance_km": distance_km, "url": url}


def parse_results(soup):
    table = soup.find("table")
    if table is None:
        return []

    header_row = table.find("tr")
    column_names = [
        normalize_column_name(cell.get_text(strip=True))
        for cell in header_row.find_all(["th", "td"])
    ]

    runners = []
    for row_index, row in enumerate(table.find_all("tr")[1:], start=1):
        cells = row.find_all("td")
        if not cells:
            continue
        runner = {}
        for col_name, cell in zip(column_names, cells):
            if col_name:
                runner[col_name] = cell.get_text(strip=True)

        # Fallback: if the rank column wasn't recognised but we have a name,
        # use the row's position so we don't lose the runner entirely.
        if not runner.get("rank") and runner.get("name"):
            runner["rank"] = str(row_index)

        if not runner.get("name"):
            continue
        runners.append(runner)

    return runners


def scrape_and_save(url, race_date=None):
    html = fetch_page(url)
    soup = BeautifulSoup(html, "html.parser")
    metadata = extract_metadata(soup, url)
    if race_date:
        metadata["race_date"] = race_date
    runners = parse_results(soup)
    print(f"  -> {metadata['name']} {metadata['year']} "
          f"({metadata['distance_km']} km)"
          f"{' on ' + race_date if race_date else ''}, "
          f"{len(runners)} runners")
    save_race(metadata, runners)


def update_existing_dates(url_dates):
    conn = get_connection()
    cur = conn.cursor()
    updated = 0
    for url, date in url_dates.items():
        if not date:
            continue
        cur.execute(
            "UPDATE races SET race_date = ? WHERE url = ? AND race_date IS NULL",
            (date, url),
        )
        updated += cur.rowcount
    conn.commit()
    conn.close()
    return updated


def main():
    init_db()

    print("=" * 60)
    print("PHASE 1: Discovering race URLs and dates")
    print("=" * 60 + "\n")

    discovered = discover_all_result_urls()
    for extra in EXTRA_URLS:
        discovered.setdefault(extra, None)

    backfilled = update_existing_dates(discovered)
    print(f"\nBackfilled race_date on {backfilled} existing races.")

    new_urls = {u: d for u, d in discovered.items() if not is_url_scraped(u)}
    skipped = len(discovered) - len(new_urls)

    print(f"\n{'=' * 60}")
    print("PHASE 2: Scraping new races")
    print(f"{'=' * 60}")
    print(f"  {len(discovered)} URLs discovered")
    print(f"  {skipped} already in the database (skipping)")
    print(f"  {len(new_urls)} new races to scrape\n")

    for i, (url, date) in enumerate(new_urls.items(), 1):
        print(f"[{i}/{len(new_urls)}] {url}")
        try:
            scrape_and_save(url, race_date=date)
        except Exception as e:
            print(f"  ! failed: {e}")
        time.sleep(REQUEST_DELAY)

    print(f"\nDone. Quick query — runners named 'Arnar':")
    rows = find_runner("Arnar")
    print(f"  {len(rows)} results found.")


if __name__ == "__main__":
    main()