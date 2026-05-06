"""Streamlit dashboard for the Tímataka race tracker."""

import sqlite3
import pandas as pd
import altair as alt
import streamlit as st

DB_PATH = "race_results.db"

st.set_page_config(page_title="Tímataka Tracker", page_icon="🏃", layout="wide")
st.title("Tímataka Race Tracker 🏃")
st.caption("Track your running progress across races on timataka.net")


@st.cache_data
def load_results():
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


def format_time(seconds):
    if pd.isna(seconds) or seconds is None:
        return "—"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


df = load_results()

if df.empty:
    st.warning("No data yet. Run `python scraper.py` to populate the database.")
    st.stop()

st.caption(
    f"Database contains {len(df):,} results across "
    f"{df['race_name'].nunique()} race events."
)

search = st.text_input("🔎 Search runner by name", placeholder="e.g. Arnar Pétursson")

if not search:
    st.info("Type a name above to see that runner's history and progress.")
    st.stop()

matches = df[df["runner_name"].str.contains(search, case=False, na=False)]
if matches.empty:
    st.error(f"No runners found matching '{search}'.")
    st.stop()

# Group by (name + birth_year) so two runners with the same name but
# different ages stay separate. Birth year always appears on timataka results.
runner_groups = (
    matches.groupby(["runner_name", "birth_year"], dropna=False)
    .size()
    .reset_index(name="race_count")
    .sort_values(["runner_name", "birth_year"])
)


def runner_label(name, birth_year, count):
    if pd.notna(birth_year):
        by = f"born {int(birth_year)}"
    else:
        by = "birth year unknown"
    races_word = "race" if count == 1 else "races"
    return f"{name} ({by}, {count} {races_word})"


runner_groups["label"] = runner_groups.apply(
    lambda r: runner_label(r["runner_name"], r["birth_year"], r["race_count"]),
    axis=1,
)

if len(runner_groups) > 1:
    selected_label = st.selectbox(
        f"Found {len(runner_groups)} matching runners — pick one:",
        runner_groups["label"].tolist(),
    )
    selected_row = runner_groups[runner_groups["label"] == selected_label].iloc[0]
else:
    selected_row = runner_groups.iloc[0]

selected_name = selected_row["runner_name"]
selected_birth_year = selected_row["birth_year"]

# Match on BOTH name and birth year — never mix two different people.
if pd.isna(selected_birth_year):
    runner = df[(df["runner_name"] == selected_name) & df["birth_year"].isna()]
else:
    runner = df[
        (df["runner_name"] == selected_name)
        & (df["birth_year"] == selected_birth_year)
    ]
runner = runner.sort_values(["race_date_parsed", "race_name"])

st.header(selected_name)
if pd.notna(selected_birth_year):
    st.caption(f"Born {int(selected_birth_year)}")

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
    "rank", "chiptime", "club"
]].copy()
table.columns = ["Date", "Year", "Race", "Distance (km)", "Rank", "Chip time", "Club"]
st.dataframe(table, hide_index=True, use_container_width=True)

st.subheader("Progress over time")

distances = sorted(runner["distance_km"].dropna().unique())
if not distances:
    st.caption("No distance information available for this runner's races.")
    st.stop()

if len(distances) > 1:
    chosen = st.selectbox("Distance:", distances, format_func=lambda x: f"{x} km")
else:
    chosen = distances[0]
    st.caption(f"Showing {chosen} km races")

chart_df = runner[runner["distance_km"] == chosen].copy()
chart_df["time_label"] = chart_df["chiptime_seconds"].apply(format_time)

mmss_format = (
    "floor(datum.value/60) + ':' + "
    "(datum.value%60 < 10 ? '0' : '') + (datum.value%60)"
)

line = alt.Chart(chart_df).mark_line(point=alt.OverlayMarkDef(size=100)).encode(
    x=alt.X(
        "race_date_parsed:T",
        title="Date",
        axis=alt.Axis(format="%b %Y"),
    ),
    y=alt.Y(
        "chiptime_seconds:Q",
        title="Chip time",
        scale=alt.Scale(reverse=True, zero=False),
        axis=alt.Axis(labelExpr=mmss_format),
    ),
    tooltip=[
        alt.Tooltip("race_name:N", title="Race"),
        alt.Tooltip("race_date:N", title="Date"),
        alt.Tooltip("rank:Q", title="Rank"),
        alt.Tooltip("time_label:N", title="Chip time"),
    ],
)

st.altair_chart(line.properties(height=400), use_container_width=True)