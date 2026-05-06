"""Find and re-scrape races with parser problems, plus apply overrides
and backfill dates from discovery."""

import time

from database import init_db, get_connection
from scraper import (
    scrape_and_save,
    update_existing_dates,
    REQUEST_DELAY,
    DISTANCE_OVERRIDES,
)
from discovery import discover_all_result_urls


def apply_distance_overrides():
    conn = get_connection()
    cur = conn.cursor()
    total_updated = 0
    for slug_fragment, distance in DISTANCE_OVERRIDES.items():
        cur.execute(
            "UPDATE races SET distance_km = ? "
            "WHERE distance_km IS NULL AND LOWER(url) LIKE ?",
            (distance, f"%{slug_fragment}%"),
        )
        total_updated += cur.rowcount
    conn.commit()
    conn.close()
    return total_updated


def find_problem_races():
    """Races with no year, no distance, or no runners."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.id, r.url, r.name, r.year, r.distance_km,
               (SELECT COUNT(*) FROM results WHERE race_id = r.id) AS runners
          FROM races r
         WHERE r.year IS NULL
            OR r.distance_km IS NULL
            OR (SELECT COUNT(*) FROM results WHERE race_id = r.id) = 0
         ORDER BY r.id
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def delete_race(race_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM results WHERE race_id = ?", (race_id,))
    cur.execute("DELETE FROM races WHERE id = ?", (race_id,))
    conn.commit()
    conn.close()


def main():
    init_db()  # Runs schema migration if needed.

    # 1) Cheap fixes first: hard-coded distance overrides.
    updated = apply_distance_overrides()
    print(f"Distance overrides applied: {updated} race(s) updated.\n")

    # 2) Crawl event pages to discover dates, backfill them onto existing rows.
    print("=" * 60)
    print("Discovering race dates from event pages...")
    print("=" * 60 + "\n")
    discovered = discover_all_result_urls()
    backfilled = update_existing_dates(discovered)
    print(f"\nBackfilled race_date on {backfilled} existing races.\n")

    # 3) Find and re-scrape rows with structural problems.
    problems = find_problem_races()
    print(f"Found {len(problems)} problem races to re-scrape.\n")

    if not problems:
        print("Nothing else to fix.")
        return

    fixed = 0
    for race_id, url, name, year, distance, runners in problems:
        reasons = []
        if year is None:
            reasons.append("no year")
        if distance is None:
            reasons.append("no distance")
        if runners == 0:
            reasons.append("no runners")
        print(f"  [{race_id}] {name} ({', '.join(reasons)})")

        delete_race(race_id)
        race_date = discovered.get(url)
        try:
            scrape_and_save(url, race_date=race_date)
            fixed += 1
        except Exception as e:
            print(f"  ! failed: {e}")
        time.sleep(REQUEST_DELAY)

    print(f"\nDone. {fixed} of {len(problems)} successfully re-scraped.")


if __name__ == "__main__":
    main()