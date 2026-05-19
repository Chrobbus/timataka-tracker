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

def normalize_existing_distances():
    """Snap any half/full marathon distances that crept in as 21.0 or 42.0
    to their official rounded values."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE races SET distance_km = 21.1 "
        "WHERE distance_km BETWEEN 20.5 AND 21.5 AND distance_km != 21.1"
    )
    half = cur.rowcount
    cur.execute(
        "UPDATE races SET distance_km = 42.2 "
        "WHERE distance_km BETWEEN 41.5 AND 42.5 AND distance_km != 42.2"
    )
    full = cur.rowcount
    conn.commit()
    conn.close()
    return half, full

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
    """Races with no year, no distance, no runners,
    runners-but-no-birth-years (column-mapping miss),
    or runners-but-no-chiptimes (gun-time-only event scraped before fallback)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.id, r.url, r.name, r.year, r.distance_km,
               (SELECT COUNT(*) FROM results WHERE race_id = r.id) AS runners,
               (SELECT COUNT(*) FROM results
                 WHERE race_id = r.id AND birth_year IS NOT NULL) AS with_bday,
               (SELECT COUNT(*) FROM results
                 WHERE race_id = r.id AND chiptime_seconds IS NOT NULL) AS with_chiptime
          FROM races r
         WHERE r.year IS NULL
            OR r.distance_km IS NULL
            OR (SELECT COUNT(*) FROM results WHERE race_id = r.id) = 0
            OR (
                  (SELECT COUNT(*) FROM results WHERE race_id = r.id) >= 3
                  AND (SELECT COUNT(*) FROM results
                        WHERE race_id = r.id AND birth_year IS NOT NULL) = 0
               )
            OR (
                  (SELECT COUNT(*) FROM results WHERE race_id = r.id) >= 3
                  AND (SELECT COUNT(*) FROM results
                        WHERE race_id = r.id AND chiptime_seconds IS NOT NULL) = 0
               )
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
    init_db()
    half, full = normalize_existing_distances()
    print(f"Normalised distances: {half} half-marathon, {full} marathon races.\n")
    updated = apply_distance_overrides()
    print(f"Distance overrides applied: {updated} race(s) updated.\n")

    print("=" * 60)
    print("Discovering race dates from event pages...")
    print("=" * 60 + "\n")
    discovered = discover_all_result_urls()
    backfilled = update_existing_dates(discovered)
    print(f"\nBackfilled race_date on {backfilled} existing races.\n")

    problems = find_problem_races()
    print(f"Found {len(problems)} problem races to re-scrape.\n")

    if not problems:
        print("Nothing else to fix.")
        return

    fixed = 0
    for race_id, url, name, year, distance, runners, with_bday, with_chiptime in problems:
        reasons = []
        if year is None:
            reasons.append("no year")
        if distance is None:
            reasons.append("no distance")
        if runners == 0:
            reasons.append("no runners")
        if runners > 0 and with_bday == 0:
            reasons.append("no birth years")
        if runners > 0 and with_chiptime == 0:
            reasons.append("no chiptimes")
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