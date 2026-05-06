"""Database setup and operations for the Tímataka race tracker."""

import sqlite3
from datetime import datetime

DB_PATH = "race_results.db"


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
                   race_date = ?, scraped_at = ?
             WHERE id = ?
        """, (
            metadata["name"], metadata["year"], metadata["distance_km"],
            metadata.get("race_date"), now, race_id,
        ))
    else:
        cur.execute("""
            INSERT INTO races (name, year, distance_km, race_date, url, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            metadata["name"], metadata["year"], metadata["distance_km"],
            metadata.get("race_date"), metadata["url"], now,
        ))
        race_id = cur.lastrowid

    for r in runners:
        rank = r.get("rank", "").strip()
        birth_year = r.get("year", "").strip()
        chiptime = r.get("chiptime", "").strip() or None

        cur.execute("""
            INSERT INTO results
              (race_id, rank, bib, name, birth_year, club,
               chiptime, chiptime_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            race_id,
            int(rank) if rank.isdigit() else None,
            r.get("bib", "") or None,
            r.get("name", ""),
            int(birth_year) if birth_year.isdigit() else None,
            r.get("club", "") or None,
            chiptime,
            time_to_seconds(chiptime),
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