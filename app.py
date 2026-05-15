"""Streamlit dashboard for the Tímataka race tracker."""

import os
import sqlite3

import altair as alt
import pandas as pd
import streamlit as st

DB_PATH = "race_results.db"

st.set_page_config(page_title="Tímataka Tracker", page_icon="🏃", layout="wide")
st.title("Tímataka Race Tracker 🏃")
st.markdown(
    "Track your running progress across races timed by "
    "**[timataka.net](https://timataka.net/)**."
)

# ─── DATA LOADING ────────────────────────────────────────────────────────────

def _db_mtime():
    """Used as a cache key so caches invalidate when the .db file is updated."""
    return os.path.getmtime(DB_PATH) if os.path.exists(DB_PATH) else 0


@st.cache_data
def load_results(db_mtime):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT
            races.name        AS race_name,
            races.year        AS race_year,
            races.race_date   AS race_date,
            races.distance_km AS distance_km,
            results.name      AS runner_name,
            results.rank      AS rank,
            results.chiptime  AS chiptime,
            results.chiptime_seconds AS chiptime_seconds,
            results.club      AS club,
            results.birth_year AS birth_year
          FROM results
          JOIN races ON races.id = results.race_id
         WHERE results.chiptime_seconds IS NOT NULL
    """, conn)
    conn.close()

    df["race_date_parsed"] = pd.to_datetime(df["race_date"], errors="coerce")
    fallback_mask = df["race_date_parsed"].isna() & df["race_year"].notna()
    df.loc[fallback_mask, "race_date_parsed"] = pd.to_datetime(
        df.loc[fallback_mask, "race_year"].astype(int).astype(str) + "-07-01"
    )
    return df


# ─── FORMATTING HELPERS ──────────────────────────────────────────────────────

def format_time(seconds):
    if pd.isna(seconds) or seconds is None:
        return "—"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def format_pace(seconds, distance_km):
    """Convert a finish time + distance into a min/km pace string."""
    if pd.isna(seconds) or pd.isna(distance_km) or distance_km == 0:
        return "—"
    pace_seconds = seconds / distance_km
    m = int(pace_seconds // 60)
    s = int(pace_seconds % 60)
    return f"{m}:{s:02d}/km"


def runner_display_label(name, birth_year, count):
    if pd.notna(birth_year):
        by = f"born {int(birth_year)}"
    else:
        by = "birth year unknown"
    races_word = "race" if count == 1 else "races"
    return f"{name} ({by}, {count} {races_word})"


# ─── SHARED WIDGETS ──────────────────────────────────────────────────────────

def pick_runner(df, label, key_prefix):
    """Search box + (optional) selectbox for picking one runner.

    Returns (runner_df, name, birth_year) or None if nothing chosen yet.
    """
    search = st.text_input(
        label, key=f"{key_prefix}_search", placeholder="e.g. Arnar Pétursson"
    )
    if not search:
        return None

    matches = df[df["runner_name"].str.contains(search, case=False, na=False)]
    if matches.empty:
        st.error(f"No runners found matching '{search}'.")
        return None

    runner_groups = (
        matches.groupby(["runner_name", "birth_year"], dropna=False)
        .size()
        .reset_index(name="race_count")
        .sort_values(["runner_name", "birth_year"])
    )
    runner_groups["label"] = runner_groups.apply(
        lambda r: runner_display_label(
            r["runner_name"], r["birth_year"], r["race_count"]
        ),
        axis=1,
    )

    if len(runner_groups) > 1:
        selected = st.selectbox(
            f"Found {len(runner_groups)} matching runners — pick one:",
            runner_groups["label"].tolist(),
            key=f"{key_prefix}_pick",
        )
        row = runner_groups[runner_groups["label"] == selected].iloc[0]
    else:
        row = runner_groups.iloc[0]

    name = row["runner_name"]
    birth_year = row["birth_year"]

    if pd.isna(birth_year):
        runner_df = df[(df["runner_name"] == name) & df["birth_year"].isna()]
    else:
        runner_df = df[
            (df["runner_name"] == name) & (df["birth_year"] == birth_year)
        ]

    runner_df = runner_df.sort_values(["race_date_parsed", "race_name"])
    return runner_df, name, birth_year


# ─── CHART HELPERS ───────────────────────────────────────────────────────────

MMSS_LABEL_FORMAT = (
    "floor(datum.value/60) + ':' + "
    "(datum.value%60 < 10 ? '0' : '') + (datum.value%60)"
)


def progress_chart(chart_df, color_field=None):
    """Build an Altair line chart of chiptime over date. Optionally colour
    by a categorical field (e.g. 'runner_label' for comparison view)."""
    chart_df = chart_df.copy()
    chart_df["time_label"] = chart_df["chiptime_seconds"].apply(format_time)

    encodings = dict(
        x=alt.X(
            "race_date_parsed:T",
            title="Date",
            axis=alt.Axis(format="%b %Y"),
        ),
        y=alt.Y(
            "chiptime_seconds:Q",
            title="Chip time",
            scale=alt.Scale(reverse=True, zero=False),
            axis=alt.Axis(labelExpr=MMSS_LABEL_FORMAT),
        ),
        tooltip=[
            alt.Tooltip("race_name:N", title="Race"),
            alt.Tooltip("race_date:N", title="Date"),
            alt.Tooltip("rank:Q", title="Rank"),
            alt.Tooltip("time_label:N", title="Chip time"),
        ],
    )

    if color_field:
        encodings["color"] = alt.Color(f"{color_field}:N", title="Runner")
        encodings["tooltip"].insert(
            0, alt.Tooltip(f"{color_field}:N", title="Runner")
        )

    line = (
        alt.Chart(chart_df)
        .mark_line(point=alt.OverlayMarkDef(size=100))
        .encode(**encodings)
    )
    return line.properties(height=400)


# ─── PROFILE VIEW (TAB 1) ────────────────────────────────────────────────────

def render_profile(runner, name, birth_year):
    st.header(name)
    if pd.notna(birth_year):
        st.caption(f"Born {int(birth_year)}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total races", len(runner))
    c2.metric("Years active", runner["race_year"].nunique())

    best_5k = runner.loc[runner["distance_km"] == 5.0, "chiptime_seconds"].min()
    best_10k = runner.loc[runner["distance_km"] == 10.0, "chiptime_seconds"].min()
    c3.metric("Best 5K", format_time(best_5k))
    c4.metric("Best 10K", format_time(best_10k))

    st.subheader("Race history")
    table = runner[[
        "race_date", "race_year", "race_name", "distance_km",
        "rank", "chiptime", "chiptime_seconds", "club"
    ]].copy()
    table["pace"] = table.apply(
        lambda r: format_pace(r["chiptime_seconds"], r["distance_km"]),
        axis=1,
    )
    display = table[[
        "race_date", "race_year", "race_name", "distance_km",
        "rank", "chiptime", "pace", "club"
    ]]
    display.columns = [
        "Date", "Year", "Race", "Distance (km)",
        "Rank", "Chip time", "Pace", "Club",
    ]
    st.dataframe(display, hide_index=True, use_container_width=True)

    st.subheader("Progress over time")

    distances = sorted(runner["distance_km"].dropna().unique())
    if not distances:
        st.caption("No distance information available for this runner's races.")
        return

    if len(distances) > 1:
        chosen = st.selectbox(
            "Distance:", distances,
            format_func=lambda x: f"{x} km",
            key="profile_distance",
        )
    else:
        chosen = distances[0]
        st.caption(f"Showing {chosen} km races")

    chart_df = runner[runner["distance_km"] == chosen]
    if chart_df.empty:
        st.caption("No data for this distance.")
        return
    st.altair_chart(progress_chart(chart_df), use_container_width=True)


# ─── COMPARE VIEW (TAB 2) ────────────────────────────────────────────────────

def render_comparison(r1, name1, by1, r2, name2, by2):
    label1 = f"{name1}" + (f" (born {int(by1)})" if pd.notna(by1) else "")
    label2 = f"{name2}" + (f" (born {int(by2)})" if pd.notna(by2) else "")

    col1, col2 = st.columns(2)
    for col, label, runner in [(col1, label1, r1), (col2, label2, r2)]:
        with col:
            st.subheader(label)
            a, b = st.columns(2)
            a.metric("Total races", len(runner))
            b.metric("Years active", runner["race_year"].nunique())
            best_5 = runner.loc[runner["distance_km"] == 5.0, "chiptime_seconds"].min()
            best_10 = runner.loc[runner["distance_km"] == 10.0, "chiptime_seconds"].min()
            a.metric("Best 5K", format_time(best_5))
            b.metric("Best 10K", format_time(best_10))

    st.subheader("Progress comparison")

    distances = sorted(set(r1["distance_km"].dropna()) | set(r2["distance_km"].dropna()))
    if not distances:
        st.caption("No distance data available for comparison.")
        return

    chosen = st.selectbox(
        "Distance:", distances,
        format_func=lambda x: f"{x} km",
        key="compare_distance",
    )

    a = r1[r1["distance_km"] == chosen].copy()
    a["runner_label"] = label1
    b = r2[r2["distance_km"] == chosen].copy()
    b["runner_label"] = label2
    combined = pd.concat([a, b], ignore_index=True)

    if combined.empty:
        st.caption(f"Neither runner has results at {chosen} km.")
        return

    st.altair_chart(
        progress_chart(combined, color_field="runner_label"),
        use_container_width=True,
    )


# ─── MAIN ────────────────────────────────────────────────────────────────────

df = load_results(_db_mtime())

if df.empty:
    st.warning("No data yet. Run `python scraper.py` to populate the database.")
    st.stop()

st.caption(
    f"Database contains {len(df):,} results across "
    f"{df['race_name'].nunique()} race events."
)

with st.expander("ℹ️ About the data"):
    st.markdown(
        "All race results are sourced from **[timataka.net](https://timataka.net/)**, "
        "the timing service used by most Icelandic running events. "
        "Only races available there appear in this dashboard — if a specific "
        "race or year is missing upstream, or a page is temporarily broken on "
        "timataka's side, it won't be here either. "
        "Results are limited to events that publish a *Heildarúrslit / Overall* "
        "page; some races only publish gender or age-split categories."
    )
profile_tab, compare_tab = st.tabs(["🏃 Runner profile", "⚖️ Compare two runners"])

with profile_tab:
    result = pick_runner(df, "🔎 Search runner by name", "profile")
    if result is None:
        st.info("Type a name above to see that runner's history and progress.")
    else:
        runner_df, name, birth_year = result
        render_profile(runner_df, name, birth_year)

with compare_tab:
    st.write("Search for two runners to put their stats and progression side by side.")
    col1, col2 = st.columns(2)
    with col1:
        result1 = pick_runner(df, "Runner 1", "compare1")
    with col2:
        result2 = pick_runner(df, "Runner 2", "compare2")

    if result1 is None or result2 is None:
        st.info("Pick two runners above to compare them.")
    else:
        df1, name1, by1 = result1
        df2, name2, by2 = result2
        render_comparison(df1, name1, by1, df2, name2, by2)