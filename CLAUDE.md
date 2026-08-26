# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this project is

**Tímataka Race Tracker** — a Streamlit web app that scrapes Icelandic race
results from [timataka.net](https://timataka.net/) into a local SQLite
database and serves a runner-search dashboard on top of it.

- **Live at:** https://timataka-tracker.streamlit.app/
- **Repo:** https://github.com/Chrobbus/timataka-tracker (`main` branch)
- **Features today:** runner search with (name, birth year) disambiguation,
  race-history table with PB highlighting, progress-over-time chart, a
  two-runner comparison tab, a shareable "Tölfræði" stats card, and an
  Icelandic/English language toggle (Icelandic is the default).

## Who I'm working with

Daníel Ingi Þórarinsson — a beginner-to-intermediate Python developer.

**Teach while you work.** Explain *what* you're changing and *why* that
approach, not just the code to paste. When there's a Python or Streamlit
concept behind a change (caching, DataFrame indexing, regex, SQL joins), take
a sentence or two to explain it. Prefer clear, readable code over clever code —
this codebase is also a learning artifact.

## Environment

| | |
|---|---|
| OS | Windows 11 |
| Python | 3.14 |
| Shell | PowerShell |
| Project root | `C:\Users\Daniel\Documents\AI Project\timataka-tracker` |
| Virtualenv | `venv/` — activate with `.\venv\Scripts\activate` |
| Deploy | Push to `main` → Streamlit Community Cloud auto-deploys |

Dependencies (`requirements.txt`): `streamlit`, `pandas`, `beautifulsoup4`,
`requests`, `altair`.

## File map

| File | Role |
|---|---|
| `app.py` | The Streamlit dashboard — all UI, charts, the stats card, and its CSS. The only file the deployed app really runs. |
| `translations.py` | Every user-visible string, keyed `is`/`en`. `t("key", **kwargs)` reads the current language from `st.session_state["lang"]`. |
| `database.py` | SQLite schema (`races`, `results`), `init_db()` with in-place migrations, `save_race()`, `time_to_seconds()`. |
| `scraper.py` | Fetches and parses a timataka result page. Holds `COLUMN_NAME_MAP`, `DISTANCE_OVERRIDES`, `normalize_distance()`. `python scraper.py` = discover + scrape everything new. |
| `discovery.py` | Crawls the timataka index page to find running-event result URLs and the race date next to each one. Filters sport by slug keywords. |
| `refresh.py` | Maintenance pass: normalize distances, apply overrides, backfill dates, then find and re-scrape races the parser got wrong. |
| `scrape_one.py` | `python scrape_one.py <url>` — scrape one race, auto-looking up its date from the event page. |
| `audit.py` | `python audit.py <url>` — prints exactly what the parser sees on a page (headers, raw→normalized column names, first parsed rows). First stop when a race imports wrong. |
| `check.py` | Tiny ad-hoc query: how many runners in each race have a birth year. Edit `URL_FRAGMENT` at the top. |
| `debug.py` | Local-only (gitignored) User-Agent probe for when timataka returns unexpected HTML. |
| `race_results.db` | The SQLite database — **committed to git on purpose** (see gotchas). |
| `.streamlit/config.toml` | Dark theme, primary colour `#FF6B35` (the orange used throughout the app). |

## Key patterns & gotchas

**Icelandic vs. English column headers.** Older timataka pages label columns in
Icelandic (`Sæti`, `Nafn`, `F.ár`, `Flögutími`), newer ones in English.
`COLUMN_NAME_MAP` in `scraper.py` normalizes both into one set of English keys.
When a race imports with missing birth years or times, an unrecognized header is
almost always the cause — run `audit.py` on the URL and add the missing header
to the map.

**Distance parsing needs manual help sometimes.** `extract_distance()` reads the
distance out of page headings, but some events don't state it. Those get a slug
→ distance entry in `DISTANCE_OVERRIDES`. Separately, `normalize_distance()`
snaps anything in 20.5–21.5 km to 21.1 and 41.5–42.5 km to 42.2, because pages
label half and full marathons inconsistently. The stats card matches PB
distances by exact value (`5.0`, `10.0`, `21.1`, `42.2`), so this normalization
is what makes marathon PBs show up at all.

**Names are not unique — always key on (name, birth_year).** Iceland has many
runners sharing a name. Every lookup in `app.py` groups by
`["runner_name", "birth_year"]`, and `pick_runner()` shows a picker when more
than one match exists. Never write a query or a groupby keyed on name alone.

**`@st.cache_data` needs `_db_mtime()` passed in.** `load_results(db_mtime)` takes
the database's modification time as an argument purely so Streamlit's cache
invalidates when the DB changes. If you add another cached function that reads
the DB, pass `_db_mtime()` into it the same way — otherwise it will serve stale
data after a re-scrape.

**`st.markdown(..., unsafe_allow_html=True)` treats indented lines as code
blocks.** Any HTML you build for the stats card must be a flat, unindented
string. `render_stats_card()` builds a list of single-line strings and
`"".join()`s them for exactly this reason. Indenting that HTML to make it
"pretty" will render a literal code block instead of the card — this has broken
the app before.

**The database is committed to git.** Streamlit Community Cloud can't run the
scraper, so `race_results.db` ships in the repo. That means a data update is a
commit: scrape locally, then commit the changed `.db` file. It's ~17 MB, so
expect large diffs.

**Only "Overall" pages are scraped.** `discovery.py` collects URLs containing
`cat=overall`. Races that publish only gender/age splits won't appear.
`load_results()` also filters to rows where `chiptime_seconds IS NOT NULL`.

## Standard workflow

```powershell
.\venv\Scripts\activate

python scraper.py            # discover + scrape any new races
python refresh.py            # re-scrape races the parser got wrong
python scrape_one.py <url>   # add one specific race
python audit.py <url>        # debug what the parser sees on a page

streamlit run app.py         # test locally at http://localhost:8501

git add .
git commit -m "..."
git push                     # auto-deploys to Streamlit Cloud
```

Always test locally with `streamlit run app.py` before pushing — a push goes
straight to the live site.

## Ideas on the horizon

Done: PB highlighting, the Tölfræði stats card, Icelandic/English toggle.

Candidates next:

- **Series filters** — group races that recur as a series (Hlaupasería, etc.).
- **All-time records page** — fastest times per distance across the database.
- **Community percentile** — "faster than 78% of runners at this distance".
- **Club leaderboard** — aggregate by the `club` column.
- **Year-in-review card** — a per-year variant of the stats card.
- **GitHub Actions for scheduled scraping** — run the scraper on a cron and
  commit the updated DB automatically, so data refreshes without manual work.
