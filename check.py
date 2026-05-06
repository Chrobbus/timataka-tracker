"""Quick check: how many runners in each race have a birth year?"""
import sqlite3

URL_FRAGMENT = "vestmannaeyja"  # change as needed

conn = sqlite3.connect("race_results.db")
cur = conn.cursor()

cur.execute("""
    SELECT races.id, races.year, races.url,
           COUNT(*) AS runners,
           COUNT(birth_year) AS with_bday
      FROM results
      JOIN races ON races.id = results.race_id
     WHERE races.url LIKE ?
     GROUP BY races.id
     ORDER BY races.year
""", (f"%{URL_FRAGMENT}%",))

print(f"{'ID':<6} {'Year':<6} {'Runners':<8} {'With YOB':<10} URL")
print("-" * 100)
for race_id, year, url, runners, with_bday in cur.fetchall():
    flag = "" if with_bday == runners else "  ← MISMATCH"
    print(f"{race_id:<6} {year or '?':<6} {runners:<8} {with_bday:<10} {url}{flag}")

conn.close()