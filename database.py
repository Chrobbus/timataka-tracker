"""Database setup and operations for the Tímataka race tracker."""

import re
import sqlite3
from datetime import datetime

DB_PATH = "race_results.db"


def normalize_name(name):
    """Collapse runs of whitespace inside a runner's name.

    timataka publishes names with stray double spaces ('Rúnar  Sigurðsson'),
    and the same person is often entered both ways across races. Since the
    dashboard identifies a runner by the exact (name, birth_year) pair, an
    extra space silently splits one person's history into two — this was
    affecting roughly 4,700 runners. Normalising on the way in keeps them
    together, and refresh.normalize_existing_names() fixes older rows.
    """
    if not name:
        return name
    return re.sub(r"\s+", " ", name).strip()


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    """Create the tables if needed, and migrate older databases."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS races (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            year        INTEGER,
            distance_km REAL,
            url         TEXT NOT NULL UNIQUE,
            scraped_at  TEXT NOT NULL
        )
    """)

    # Migration: add race_date column if it's missing (older DB).
    cur.execute("PRAGMA table_info(races)")
    columns = [row[1] for row in cur.fetchall()]
    if "race_date" not in columns:
        cur.execute("ALTER TABLE races ADD COLUMN race_date TEXT")

    # Migration: tag every race with the site it was scraped from. Everything
    # already in the database predates multi-source support, so it's timataka.
    if "source" not in columns:
        cur.execute("ALTER TABLE races ADD COLUMN source TEXT")
        cur.execute("UPDATE races SET source = 'timataka' WHERE source IS NULL")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id          INTEGER NOT NULL,
            rank             INTEGER,
            bib              TEXT,
            name             TEXT NOT NULL,
            birth_year       INTEGER,
            club             TEXT,
            chiptime         TEXT,
            chiptime_seconds INTEGER,
            FOREIGN KEY (race_id) REFERENCES races(id)
        )
    """)

    # Migration: gender. timataka's overall tables never expose it, but other
    # Icelandic results sites publish a Kyn column, so it stays optional and
    # is populated only by sources that provide it.
    cur.execute("PRAGMA table_info(results)")
    result_columns = [row[1] for row in cur.fetchall()]
    if "gender" not in result_columns:
        cur.execute("ALTER TABLE results ADD COLUMN gender TEXT")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_results_name ON results(name)")

    conn.commit()
    conn.close()


def time_to_seconds(time_str):
    if not time_str:
        return None
    parts = time_str.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        return None
    return None


def save_race(metadata, runners):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")

    cur.execute("SELECT id FROM races WHERE url = ?", (metadata["url"],))
    existing = cur.fetchone()

    if existing:
        race_id = existing[0]
        cur.execute("DELETE FROM results WHERE race_id = ?", (race_id,))
        cur.execute("""
            UPDATE races
               SET name = ?, year = ?, distance_km = ?,
                   race_date = ?, source = ?, scraped_at = ?
             WHERE id = ?
        """, (
            metadata["name"], metadata["year"], metadata["distance_km"],
            metadata.get("race_date"), metadata.get("source", "timataka"),
            now, race_id,
        ))
    else:
        cur.execute("""
            INSERT INTO races
              (name, year, distance_km, race_date, source, url, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            metadata["name"], metadata["year"], metadata["distance_km"],
            metadata.get("race_date"), metadata.get("source", "timataka"),
            metadata["url"], now,
        ))
        race_id = cur.lastrowid

    for r in runners:
        rank = r.get("rank", "").strip()
        birth_year = r.get("year", "").strip()
        chiptime = r.get("chiptime", "").strip() or r.get("time", "").strip() or None

        cur.execute("""
            INSERT INTO results
              (race_id, rank, bib, name, birth_year, club,
               chiptime, chiptime_seconds, gender)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            race_id,
            int(rank) if rank.isdigit() else None,
            r.get("bib", "") or None,
            normalize_name(r.get("name", "")),
            int(birth_year) if birth_year.isdigit() else None,
            r.get("club", "") or None,
            chiptime,
            time_to_seconds(chiptime),
            (r.get("gender", "") or "").strip().upper() or None,
        ))

    conn.commit()
    conn.close()
    return race_id


def find_runner(name_query):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT races.name, races.year, races.distance_km,
               results.name, results.rank, results.chiptime
          FROM results
          JOIN races ON races.id = results.race_id
         WHERE LOWER(results.name) LIKE LOWER(?)
         ORDER BY races.year, races.name
    """, (f"%{name_query}%",))
    rows = cur.fetchall()
    conn.close()
    return rows


def is_url_scraped(url):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM races WHERE url = ?", (url,))
    found = cur.fetchone() is not None
    conn.close()
    return found