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
| `corsa.py` | Scraper for results.corsa.is — Reykjavíkurmaraþon 2024 onwards. `python corsa.py --list` shows what's available without saving. |
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

## Multiple sources

`races.source` records which site a race came from (`timataka` or `corsa`).
`results.gender` is populated only by sources that publish it — timataka's
overall tables never do, so it's null for the great majority of rows.

**Reykjavíkurmaraþon is split across sites by year.** timataka has 2018, 2019,
2022 and 2023; corsa has 2023 through 2026. 2023 exists on *both*, which is
why `database.find_race_by_identity()` exists: before saving, a scraper checks
whether the same (name, year, distance) is already stored **from a different
source** and skips it. The "different source" part matters — corsa splits one
distance into separate "Competition" and "General registration" result sets,
and both are wanted, so same-source matches must not be treated as duplicates.

`corsa.py` uses the name `Reykjavíkurmaraþon Íslandsbanka` deliberately: it's
what timataka called the event in 2019–2023, so a runner's history stays
continuous across the source change.

**corsa renders results client-side, but you don't need a browser.** The React
app builds its table in JavaScript, so there's no HTML table to parse — but
the full participant list is embedded as JSON in the server-rendered payload,
which plain `requests` can fetch. Two things to know:

* The data is only on the `/overall` sub-route. The bare result URL renders
  just the category navigation.
* Fetch it with `corsa.fetch()`, which undoes the payload's backslash-escaping,
  and pull the array with `extract_json_array()`. Don't use a regex to grab
  participant objects — they don't all carry the same fields, so a pattern
  anchored on the last field runs past one object into the next.

**Deciding who actually finished (corsa).** `chipTime` is an array of timing
points, `[start crossing, split, ..., finish]`, in milliseconds. Reading
`chipTime[-1]` naively invents finish times for people who stopped partway —
it produced a 13-second 10 km and a 25-minute one. Three conditions, all
needed, and all learned by finding bad data:

1. The array must be the full length for that race (taken as the most common
   length in the result set, since the number of mats isn't published).
2. The last entry must be non-null — a missed mat appears as `null` *inside*
   the array, and `None > 0` raises `TypeError`.
3. If the result set ranks anyone, the runner must have a rank. The fun run
   ranks nobody, so that rule can't apply there — a few implausible fun-run
   times survive as a result.

Runners who opt out of public listing appear with a null name and birth year
0, and are skipped.

## Standard workflow

```powershell
.\venv\Scripts\activate

python scraper.py            # discover + scrape any new races (timataka)
python corsa.py              # Reykjavíkurmaraþon 2024+ (corsa)
python corsa.py --list       # ...show what's there without saving
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

Done: PB highlighting, the Tölfræði stats card, Icelandic/English toggle,
multi-source scraping (corsa alongside timataka).

Now possible because corsa supplies gender for ~40,000 results:
gender splits on percentiles and records, and age-group comparisons.

Known gaps worth picking up:

- **Reykjavíkurmaraþon 2013–2017** exists only as PDFs on
  `marathon.cdn.prismic.io`. `urslit.marathon.is` looks like a results site
  but is a frozen mirror of **2023** — don't scrape it, it duplicates data
  timataka already has.
- **124 races have no distance** (~16,400 results invisible to every
  distance-based feature). Roughly 12 recurring events cover most of them, but
  8 are multi-distance, so `DISTANCE_OVERRIDES` (slug → one distance) can't
  express them as it stands. Backyard ultras genuinely have no fixed distance.
- **Club data is only 38% filled**, and inconsistently spelled — a club
  leaderboard would rank clubs by who bothered to enter a club name.

Candidates next:

- **Series filters** — group races that recur as a series (Hlaupasería, etc.).
- **All-time records page** — fastest times per distance across the database.
- **Community percentile** — "faster than 78% of runners at this distance".
- **Club leaderboard** — aggregate by the `club` column.
- **Year-in-review card** — a per-year variant of the stats card.
- **GitHub Actions for scheduled scraping** — run the scraper on a cron and
  commit the updated DB automatically, so data refreshes without manual work.
