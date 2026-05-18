"""Streamlit dashboard for the Tímataka race tracker."""

import os
import sqlite3

import altair as alt
import pandas as pd
import streamlit as st

from translations import t

DB_PATH = "race_results.db"

st.set_page_config(
    page_title="Tímataka Tracker", page_icon="🏃", layout="wide"
)

# ─── HEADER + LANGUAGE SELECTOR ──────────────────────────────────────────────

header_col, lang_col = st.columns([5, 1])
with header_col:
    st.title(t("app_title"))
with lang_col:
    st.selectbox(
        "Tungumál / Language",
        options=["is", "en"],
        format_func=lambda x: "🇮🇸 Íslenska" if x == "is" else "🇬🇧 English",
        index=0,
        key="lang",
        label_visibility="collapsed",
    )

st.markdown(t("tagline_md"))


# ─── DATA LOADING ────────────────────────────────────────────────────────────

def _db_mtime():
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
    if pd.isna(seconds) or pd.isna(distance_km) or distance_km == 0:
        return "—"
    pace_seconds = seconds / distance_km
    m = int(pace_seconds // 60)
    s = int(pace_seconds % 60)
    return f"{m}:{s:02d}/km"


def runner_display_label(name, birth_year, count):
    if pd.notna(birth_year):
        by = t("born_short", year=int(birth_year))
    else:
        by = t("born_unknown")
    unit = t("race_unit_singular" if count == 1 else "race_unit_plural")
    return f"{name} ({by}, {count} {unit})"


# ─── SHARED WIDGETS ──────────────────────────────────────────────────────────

def pick_runner(df, label, key_prefix):
    search = st.text_input(
        label,
        key=f"{key_prefix}_search",
        placeholder=t("search_placeholder"),
    )
    if not search:
        return None

    matches = df[df["runner_name"].str.contains(search, case=False, na=False)]
    if matches.empty:
        st.error(t("no_matches", search=search))
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
            t("pick_one", n=len(runner_groups)),
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


# ─── CHART HELPER ────────────────────────────────────────────────────────────

MMSS_LABEL_FORMAT = (
    "floor(datum.value/60) + ':' + "
    "(datum.value%60 < 10 ? '0' : '') + (datum.value%60)"
)


def progress_chart(chart_df, color_field=None):
    chart_df = chart_df.copy()
    chart_df["time_label"] = chart_df["chiptime_seconds"].apply(format_time)

    encodings = dict(
        x=alt.X(
            "race_date_parsed:T",
            title=t("axis_date"),
            axis=alt.Axis(format="%b %Y"),
        ),
        y=alt.Y(
            "chiptime_seconds:Q",
            title=t("axis_chiptime"),
            scale=alt.Scale(reverse=True, zero=False),
            axis=alt.Axis(labelExpr=MMSS_LABEL_FORMAT),
        ),
        tooltip=[
            alt.Tooltip("race_name:N", title=t("tooltip_race")),
            alt.Tooltip("race_date:N", title=t("tooltip_date")),
            alt.Tooltip("rank:Q", title=t("tooltip_rank")),
            alt.Tooltip("time_label:N", title=t("tooltip_chiptime")),
        ],
    )

    if color_field:
        encodings["color"] = alt.Color(
            f"{color_field}:N", title=t("tooltip_runner")
        )
        encodings["tooltip"].insert(
            0, alt.Tooltip(f"{color_field}:N", title=t("tooltip_runner"))
        )

    line = (
        alt.Chart(chart_df)
        .mark_line(point=alt.OverlayMarkDef(size=100))
        .encode(**encodings)
    )
    return line.properties(height=400)


# ─── PROFILE VIEW ────────────────────────────────────────────────────────────

def render_profile(runner, name, birth_year):
    st.header(name)
    if pd.notna(birth_year):
        st.caption(t("born_caption", year=int(birth_year)))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("metric_total_races"), len(runner))
    c2.metric(t("metric_years_active"), runner["race_year"].nunique())

    best_5k = runner.loc[runner["distance_km"] == 5.0, "chiptime_seconds"].min()
    best_10k = runner.loc[runner["distance_km"] == 10.0, "chiptime_seconds"].min()
    c3.metric(t("metric_best_5k"), format_time(best_5k))
    c4.metric(t("metric_best_10k"), format_time(best_10k))

    st.subheader(t("section_race_history"))
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
        t("col_date"), t("col_year"), t("col_race"), t("col_distance"),
        t("col_rank"), t("col_chiptime"), t("col_pace"), t("col_club"),
    ]
    st.dataframe(display, hide_index=True, use_container_width=True)

    st.subheader(t("section_progress"))

    distances = sorted(runner["distance_km"].dropna().unique())
    if not distances:
        st.caption(t("no_distance_info"))
        return

    if len(distances) > 1:
        chosen = st.selectbox(
            t("select_distance"), distances,
            format_func=lambda x: f"{x} km",
            key="profile_distance",
        )
    else:
        chosen = distances[0]
        st.caption(t("showing_distance", distance=chosen))

    chart_df = runner[runner["distance_km"] == chosen]
    if chart_df.empty:
        st.caption(t("no_data_distance"))
        return
    st.altair_chart(progress_chart(chart_df), use_container_width=True)


# ─── COMPARE VIEW ────────────────────────────────────────────────────────────

def render_comparison(r1, name1, by1, r2, name2, by2):
    def display_label(name, birth_year):
        if pd.notna(birth_year):
            return f"{name} ({t('born_short', year=int(birth_year))})"
        return name

    label1, label2 = display_label(name1, by1), display_label(name2, by2)

    col1, col2 = st.columns(2)
    for col, label, runner in [(col1, label1, r1), (col2, label2, r2)]:
        with col:
            st.subheader(label)
            a, b = st.columns(2)
            a.metric(t("metric_total_races"), len(runner))
            b.metric(t("metric_years_active"), runner["race_year"].nunique())
            best_5 = runner.loc[runner["distance_km"] == 5.0, "chiptime_seconds"].min()
            best_10 = runner.loc[runner["distance_km"] == 10.0, "chiptime_seconds"].min()
            a.metric(t("metric_best_5k"), format_time(best_5))
            b.metric(t("metric_best_10k"), format_time(best_10))

    st.subheader(t("section_compare_progress"))

    distances = sorted(set(r1["distance_km"].dropna()) | set(r2["distance_km"].dropna()))
    if not distances:
        st.caption(t("no_compare_distance"))
        return

    chosen = st.selectbox(
        t("select_distance"), distances,
        format_func=lambda x: f"{x} km",
        key="compare_distance",
    )

    a = r1[r1["distance_km"] == chosen].copy()
    a["runner_label"] = label1
    b = r2[r2["distance_km"] == chosen].copy()
    b["runner_label"] = label2
    combined = pd.concat([a, b], ignore_index=True)

    if combined.empty:
        st.caption(t("neither_runner_distance", distance=chosen))
        return

    st.altair_chart(
        progress_chart(combined, color_field="runner_label"),
        use_container_width=True,
    )


# ─── MAIN ────────────────────────────────────────────────────────────────────

df = load_results(_db_mtime())

if df.empty:
    st.warning("Engin gögn enn. / No data yet.")
    st.stop()

st.caption(t("stats_caption", n_results=len(df), n_races=df["race_name"].nunique()))

with st.expander(t("about_expander")):
    st.markdown(t("about_text"))

profile_tab, compare_tab = st.tabs([t("tab_profile"), t("tab_compare")])

with profile_tab:
    result = pick_runner(df, t("search_label"), "profile")
    if result is None:
        st.info(t("search_prompt"))
    else:
        runner_df, name, birth_year = result
        render_profile(runner_df, name, birth_year)

with compare_tab:
    st.write(t("compare_intro"))
    col1, col2 = st.columns(2)
    with col1:
        result1 = pick_runner(df, t("runner_1"), "compare1")
    with col2:
        result2 = pick_runner(df, t("runner_2"), "compare2")

    if result1 is None or result2 is None:
        st.info(t("pick_two_runners"))
    else:
        df1, name1, by1 = result1
        df2, name2, by2 = result2
        render_comparison(df1, name1, by1, df2, name2, by2)