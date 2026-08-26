"""Scraper for Reykjavíkurmaraþon Íslandsbanka results on results.corsa.is.

timataka.net stopped hosting the Reykjavík Marathon after 2023; from 2024 on
it lives here. corsa is a React site that renders its results client-side, so
there's no HTML table for BeautifulSoup to read. What it *does* do is embed
the whole participant list as JSON inside the server-rendered React Server
Components payload, which plain requests can fetch — so no browser is needed.

The JSON is richer than timataka's tables: it carries birth year, gender and
nationality for every runner, and both gun and chip times in milliseconds.

Two quirks worth knowing:

* From 2025 each distance is split into two result sets, "Competition" and
  "General registration", which are separate races here — a runner appears in
  exactly one of them.
* Runners who opt out of public listing still appear, but with a null name and
  a birth year of 0. Those are skipped.

Usage:
    python corsa.py                 # scrape every year not already stored
    python corsa.py --year 2026     # just one year
    python corsa.py --list          # show what's available, scrape nothing
"""

import argparse
import json
import re
import time
from collections import Counter

import requests

from database import find_race_by_identity, init_db, save_race
from scraper import HEADERS, REQUEST_DELAY

RESULTS_BASE = "https://results.corsa.is"
EVENT_SLUG = "reykjavikur-marathon"

# Match the name timataka used for 2019-2023 so a runner's history stays
# continuous across the two sources.
EVENT_NAME = "Reykjavíkurmaraþon Íslandsbanka"

# The pages don't publish the race date in any machine-readable form, so the
# known dates live here. Add a line each August.
RACE_DATES = {
    2023: "2023-08-19",
    2024: "2024-08-24",
    2025: "2025-08-23",
    2026: "2026-08-22",
}

# Result-set titles vary by year: "Marathon - Competition" (2026),
# "Marathon - Elite/Competition" (2025), "Marathon" (2024), "42.2 km" (2023).
# Half marathon has to be tested before marathon so it doesn't match first.
DISTANCE_FROM_TITLE = [
    (re.compile(r"^half\s*marathon", re.I), 21.1),
    (re.compile(r"^marathon", re.I), 42.2),
    (re.compile(r"^10\s*k", re.I), 10.0),
    (re.compile(r"^fun\s*run", re.I), 3.0),
    (re.compile(r"^skemmtiskokk", re.I), 3.0),
    (re.compile(r"^42[.,]2", re.I), 42.2),
    (re.compile(r"^21[.,]1", re.I), 21.1),
]

GENDER_MAP = {"male": "M", "female": "F", "nonbinary": "X"}

# The payload has several "title" keys (nav items are titles too), so match
# the kicker and title together — that pair only occurs on the results header.
KICKER_TITLE_RE = re.compile(r'"kicker":"([^"]*)","title":"([^"]*)"')
RESULT_ID_RE = re.compile(r'/%s/(\d+)"' % EVENT_SLUG)
PARTICIPANTS_KEY = '"participants":['


def extract_json_array(text, key):
    """Pull one complete JSON array out of a larger blob of text.

    A regex can't do this reliably: participant objects don't all carry the
    same fields in the same order, so a pattern anchored on the last field
    can run past the end of one object and into the next. Instead we find the
    opening bracket and walk forward counting brackets, skipping anything
    inside a string, until the matching close bracket.
    """
    start = text.find(key)
    if start == -1:
        return []
    i = start + len(key) - 1          # position of the '['
    depth = 0
    in_string = False
    escaped = False
    for j in range(i, len(text)):
        c = text[j]
        if in_string:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_string = False
            continue
        if c == '"':
            in_string = True
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                return json.loads(text[i:j + 1])
    return []


def fetch(url):
    """Fetch a page and undo the backslash-escaping in the RSC payload."""
    response = requests.get(url, headers=HEADERS, timeout=60)
    response.raise_for_status()
    return response.text.replace('\\"', '"')


def distance_from_title(title):
    for pattern, distance in DISTANCE_FROM_TITLE:
        if pattern.match(title.strip()):
            return distance
    return None


def format_time(milliseconds):
    """Turn corsa's millisecond total into timataka's HH:MM:SS string."""
    if not milliseconds or milliseconds <= 0:
        return ""
    total = int(round(milliseconds / 1000))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def discover_result_ids():
    """Every result-set id linked from the event's results index."""
    html = fetch(f"{RESULTS_BASE}/{EVENT_SLUG}")
    return sorted({int(i) for i in RESULT_ID_RE.findall(html)})


def parse_result_set(result_id):
    """Fetch one result set and return (metadata, runners).

    The '/overall' route is what actually server-renders the participant
    list; the bare result URL only renders the category navigation.
    """
    url = f"{RESULTS_BASE}/{EVENT_SLUG}/{result_id}/overall"
    html = fetch(url)

    header = KICKER_TITLE_RE.search(html)
    kicker, title = header.groups() if header else ("", "")

    year_match = re.search(r"(\d{4})", kicker)
    year = int(year_match.group(1)) if year_match else None

    metadata = {
        "name": EVENT_NAME,
        "year": year,
        "distance_km": distance_from_title(title),
        "race_date": RACE_DATES.get(year),
        "url": url,
        "source": "corsa",
        "title": title,
    }

    participants = extract_json_array(html, PARTICIPANTS_KEY)

    # How many timing points does a completed run have? Every race has its own
    # answer (the 10 km has four, the fun run two), and it isn't published, so
    # take it from the data: nearly everyone finishes, so the most common
    # array length is the full one. Anyone with a shorter array stopped at a
    # mat partway round, and their last split must not be read as a finish —
    # that's what produced a 20-minute "10 km".
    lengths = Counter(
        len(p.get("chipTime") or [])
        for p in participants
        if (p.get("name") or "").strip()
    )
    full_length = lengths.most_common(1)[0][0] if lengths else 0

    # Where corsa ranks anyone, it ranks everyone it counts as an official
    # finisher, so an unranked entry in such a set is not one however complete
    # its splits look. The fun run is never ranked, so there the rule can't
    # apply and a full set of splits is the only evidence available.
    ranks_finishers = any(p.get("rankOverall") for p in participants)

    runners = []
    for p in participants:
        # Runners who opted out of public listing have no name and a birth
        # year of 0. Their times are real, but there's nothing to attribute
        # them to, so they can't be used.
        name = (p.get("name") or "").strip()
        if not name:
            continue

        chip = p.get("chipTime") or []
        gun = p.get("gunTime") or []
        birthyear = p.get("birthyear") or 0

        # A missed timing point shows up as a null inside the array, so the
        # final entry has to be checked for real before it can be a finish.
        finished = (
            full_length >= 2
            and len(chip) == full_length
            and chip[-1] is not None
            and chip[-1] > 0
            and (p.get("rankOverall") or not ranks_finishers)
        )

        runners.append({
            "rank": str(p["rankOverall"]) if p.get("rankOverall") else "",
            "bib": p.get("bib") or "",
            "name": name,
            "year": str(birthyear) if birthyear > 1900 else "",
            "gender": GENDER_MAP.get(p.get("gender") or "", ""),
            "nationality": p.get("nationality") or "",
            "chiptime": format_time(chip[-1]) if finished else "",
            "time": format_time(gun[-1]) if finished and gun else "",
        })

    return metadata, runners


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, help="only scrape this year")
    parser.add_argument("--list", action="store_true",
                        help="list available result sets and exit")
    parser.add_argument("--allow-duplicates", action="store_true",
                        help="save even if the same race is already stored "
                             "from another source")
    args = parser.parse_args()

    init_db()

    print("Discovering result sets...")
    result_ids = discover_result_ids()
    print(f"Found {len(result_ids)} result sets.\n")

    saved = skipped = 0
    for result_id in result_ids:
        try:
            metadata, runners = parse_result_set(result_id)
        except Exception as e:
            print(f"[{result_id}] ! failed: {e}")
            time.sleep(REQUEST_DELAY)
            continue

        label = (f"{metadata['year']} {metadata['title']!r} "
                 f"-> {metadata['distance_km']} km, {len(runners)} runners")

        if args.list:
            print(f"[{result_id}] {label}")
            time.sleep(REQUEST_DELAY)
            continue

        if args.year and metadata["year"] != args.year:
            time.sleep(REQUEST_DELAY)
            continue

        print(f"[{result_id}] {label}")

        if metadata["distance_km"] is None:
            print("    ! couldn't work out the distance — skipping")
            skipped += 1
        elif not runners:
            print("    ! no runners parsed — skipping")
            skipped += 1
        else:
            existing = None
            if not args.allow_duplicates:
                existing = find_race_by_identity(
                    metadata["name"], metadata["year"],
                    metadata["distance_km"], other_than_source="corsa",
                )
            if existing:
                print(f"    already stored from {existing[2]} "
                      f"(race id {existing[0]}) — skipping")
                skipped += 1
            else:
                save_race(metadata, runners)
                saved += 1

        time.sleep(REQUEST_DELAY)

    if not args.list:
        print(f"\nDone. {saved} result sets saved, {skipped} skipped.")


if __name__ == "__main__":
    main()
