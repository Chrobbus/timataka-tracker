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

def format_pace_seconds(pace_sec):
    """Format a pace in seconds-per-km as M:SS/km."""
    if pd.isna(pace_sec):
        return "—"
    m = int(pace_sec // 60)
    s = int(pace_sec % 60)
    return f"{m}:{s:02d}/km"


STATS_CARD_CSS = """
<style>
.tt-stats-card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid rgba(255, 107, 53, 0.4);
    border-radius: 16px;
    padding: 28px;
    margin: 16px 0 24px 0;
    color: #f5f5f5;
}
.tt-brand {
    font-size: 11px;
    color: #FF6B35;
    letter-spacing: 3px;
    font-weight: 600;
    margin-bottom: 8px;
}
.tt-name {
    font-size: 28px;
    font-weight: 700;
    color: #ffffff;
    margin: 0;
}
.tt-birth {
    font-size: 13px;
    color: #aaa;
    margin: 4px 0 20px 0;
}
.tt-stats-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 12px;
    margin-bottom: 24px;
}
.tt-stat {
    background: rgba(255, 107, 53, 0.08);
    border: 1px solid rgba(255, 107, 53, 0.2);
    border-radius: 10px;
    padding: 14px;
    text-align: center;
}
.tt-stat-value {
    font-size: 22px;
    font-weight: 700;
    color: #FF6B35;
    font-variant-numeric: tabular-nums;
}
.tt-stat-label {
    font-size: 11px;
    color: #aaa;
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.tt-pbs {
    border-top: 1px solid rgba(255, 107, 53, 0.2);
    padding-top: 16px;
}
.tt-pbs-title {
    font-size: 11px;
    color: #FF6B35;
    letter-spacing: 3px;
    font-weight: 600;
    margin-bottom: 12px;
    text-transform: uppercase;
}
.tt-pb-row {
    display: flex;
    align-items: center;
    padding: 10px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    font-size: 14px;
}
.tt-pb-row:last-child {
    border-bottom: none;
}
.tt-pb-distance {
    font-weight: 600;
    color: #fff;
    width: 70px;
}
.tt-pb-time {
    font-weight: 700;
    color: #FF6B35;
    width: 90px;
    font-variant-numeric: tabular-nums;
}
.tt-pb-detail {
    color: #aaa;
    font-size: 13px;
    text-align: right;
    flex: 1;
}
.tt-pb-none {
    color: #555;
    text-align: right;
    flex: 1;
    font-size: 13px;
    font-style: italic;
}
.tt-footer {
    text-align: center;
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    font-size: 11px;
    color: #777;
    letter-spacing: 1px;
}
</style>
"""


def render_stats_card(runner, name, birth_year):
    """Render a shareable Tölfræði stats card."""
    total_races = len(runner)
    total_km = runner["distance_km"].sum()
    years_active = runner["race_year"].nunique()

    pace_eligible = runner.dropna(subset=["chiptime_seconds", "distance_km"])
    pace_eligible = pace_eligible[pace_eligible["distance_km"] > 0]
    if not pace_eligible.empty:
        pace_per_km = pace_eligible["chiptime_seconds"] / pace_eligible["distance_km"]
        fastest_pace = format_pace_seconds(pace_per_km.min())
    else:
        fastest_pace = "—"

    distance_labels = [(5.0, "5K"), (10.0, "10K"), (21.1, "21.1K"), (42.2, "42.2K")]
    pb_rows = []
    for dist, label in distance_labels:
        d_races = runner[runner["distance_km"] == dist]
        if d_races.empty or d_races["chiptime_seconds"].dropna().empty:
            continue
        pb_idx = d_races["chiptime_seconds"].idxmin()
        pb_row = d_races.loc[pb_idx]
        pb_time = format_time(pb_row["chiptime_seconds"])
        race_name = pb_row["race_name"]
        year = int(pb_row["race_year"]) if pd.notna(pb_row["race_year"]) else ""
        pb_rows.append(
            f'<div class="tt-pb-row">'
            f'<div class="tt-pb-distance">{label}</div>'
            f'<div class="tt-pb-time">{pb_time}</div>'
            f'<div class="tt-pb-detail">{race_name} · {year}</div>'
            f'</div>'
        )
        else:
            pb_idx = d_races["chiptime_seconds"].idxmin()
            pb_row = d_races.loc[pb_idx]
            pb_time = format_time(pb_row["chiptime_seconds"])
            race_name = pb_row["race_name"]
            year = int(pb_row["race_year"]) if pd.notna(pb_row["race_year"]) else ""
            pb_rows.append(
                f'<div class="tt-pb-row">'
                f'<div class="tt-pb-distance">{label}</div>'
                f'<div class="tt-pb-time">{pb_time}</div>'
                f'<div class="tt-pb-detail">{race_name} · {year}</div>'
                f'</div>'
            )

    birth_str = t("born_short", year=int(birth_year)) if pd.notna(birth_year) else ""

    html_parts = [
        STATS_CARD_CSS,
        '<div class="tt-stats-card">',
        f'<div class="tt-brand">{t("stats_card_brand")}</div>',
        f'<div class="tt-name">{name}</div>',
        f'<div class="tt-birth">{birth_str}</div>',
        '<div class="tt-stats-row">',
        f'<div class="tt-stat"><div class="tt-stat-value">{total_races}</div><div class="tt-stat-label">{t("metric_total_races")}</div></div>',
        f'<div class="tt-stat"><div class="tt-stat-value">{total_km:.0f} km</div><div class="tt-stat-label">{t("metric_total_distance")}</div></div>',
        f'<div class="tt-stat"><div class="tt-stat-value">{years_active}</div><div class="tt-stat-label">{t("metric_years_active")}</div></div>',
        f'<div class="tt-stat"><div class="tt-stat-value">{fastest_pace}</div><div class="tt-stat-label">{t("metric_fastest_pace")}</div></div>',
        '</div>',
        '<div class="tt-footer">timataka-tracker.streamlit.app</div>',
        '</div>',
    ]
    if pb_rows:
        html_parts.insert(
            -2,  # before the footer and the closing card div
            '<div class="tt-pbs">'
            + f'<div class="tt-pbs-title">{t("section_personal_bests")}</div>'
            + "".join(pb_rows)
            + '</div>'
        )
    html = "".join(html_parts)

    st.markdown(html, unsafe_allow_html=True)

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
    render_stats_card(runner, name, birth_year)

    st.subheader(t("section_race_history"))
    table = runner[[
        "race_date", "race_year", "race_name", "distance_km",
        "rank", "chiptime", "chiptime_seconds", "club"
    ]].copy()
    table["pace"] = table.apply(
        lambda r: format_pace(r["chiptime_seconds"], r["distance_km"]),
        axis=1,
    )

    # Identify the PB row at each distance — the row index with the
    # smallest chiptime_seconds. We use a set of indices for a fast lookup.
    pb_indices = set()
    for dist, group in table.dropna(subset=["distance_km"]).groupby("distance_km"):
        times = group["chiptime_seconds"].dropna()
        if not times.empty:
            pb_indices.add(times.idxmin())
    table["pb_mark"] = table.index.map(lambda i: "🏆" if i in pb_indices else "")

    display = table[[
        "race_date", "race_year", "race_name", "distance_km",
        "rank", "chiptime", "pace", "club", "pb_mark"
    ]].copy()
    pb_col_name = t("col_pb")
    display.columns = [
        t("col_date"), t("col_year"), t("col_race"), t("col_distance"),
        t("col_rank"), t("col_chiptime"), t("col_pace"), t("col_club"),
        pb_col_name,
    ]

    def style_pb_rows(row):
        if row[pb_col_name]:
            return ["font-weight: 600; color: #FF6B35"] * len(row)
        return [""] * len(row)

    styled = display.style.apply(style_pb_rows, axis=1).format({
        t("col_distance"): "{:g}",
    })
    st.dataframe(styled, hide_index=True, use_container_width=True)

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