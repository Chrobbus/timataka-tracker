"""Translation strings for the Tímataka Race Tracker.

Every user-visible string lives here so the dashboard can switch between
Icelandic (default) and English without changes scattered through app.py.
"""

import streamlit as st


TRANSLATIONS = {
    "is": {
        # Header
        "app_title": "Tímataka Race Tracker 🏃",
        "tagline_md": (
            "Fylgstu með framvindu þinni í hlaupum sem "
            "**[timataka.net](https://timataka.net/)** tímatekur."
        ),
        "stats_caption": (
            "Gagnagrunnurinn inniheldur {n_results:,} niðurstöður "
            "úr {n_races} hlaupum."
        ),
        "about_expander": "ℹ️ Um gögnin",
        "about_text": (
            "Allar hlaupaniðurstöður eru fengnar frá "
            "**[timataka.net](https://timataka.net/)**, "
            "tímatökuþjónustunni sem flest hlaup á Íslandi nota. "
            "Aðeins hlaup sem birtast þar koma fram hér — ef tiltekið "
            "hlaup eða ár vantar þar, eða ef síða er tímabundið bilað, "
            "þá vantar það líka hér. Niðurstöður takmarkast við "
            "viðburði sem birta *Heildarúrslit / Overall* síðu; sum "
            "hlaup birta aðeins skiptingu eftir kyni eða aldri."
        ),

        # Tabs
        "tab_profile": "🏃 Hlaupari",
        "tab_compare": "⚖️ Samanburður",

        # Search + picker
        "search_label": "🔎 Leita að hlaupara",
        "search_placeholder": "t.d. Arnar Pétursson",
        "search_prompt": (
            "Skrifaðu nafn hér að ofan til að sjá hlaupasögu og framvindu."
        ),
        "no_matches": "Engir hlauparar fundust sem passa við '{search}'.",
        "pick_one": "{n} hlauparar fundust — veldu einn:",
        "born_short": "f. {year}",
        "born_unknown": "fæðingarár óþekkt",
        "race_unit_singular": "hlaup",
        "race_unit_plural": "hlaup",

        # Profile
        "born_caption": "Fæðingarár: {year}",
        "metric_total_races": "Heildarfjöldi hlaupa",
        "metric_years_active": "Árafjöldi hlaupa",
        "metric_best_5k": "Besta 5K",
        "metric_best_10k": "Besta 10K",
        "section_race_history": "Hlaupasaga",
        "col_date": "Dagsetning",
        "col_year": "Ár",
        "col_race": "Hlaup",
        "col_distance": "Vegalengd (km)",
        "col_rank": "Sæti",
        "col_chiptime": "Flögutími",
        "col_pace": "Hraði",
        "col_club": "Félag",
        "section_progress": "Framvinda yfir tíma",
        "select_distance": "Vegalengd:",
        "no_distance_info": (
            "Engar upplýsingar um vegalengd fyrir hlaup þessa hlaupara."
        ),
        "showing_distance": "Sýni hlaup á {distance} km",
        "no_data_distance": "Engin gögn fyrir þessa vegalengd.",

        # Chart
        "axis_date": "Dagsetning",
        "axis_chiptime": "Flögutími",
        "tooltip_runner": "Hlaupari",
        "tooltip_race": "Hlaup",
        "tooltip_date": "Dagsetning",
        "tooltip_rank": "Sæti",
        "tooltip_chiptime": "Flögutími",

        # Compare
        "compare_intro": (
            "Leita að tveimur hlaupurum til að bera saman tölfræði "
            "og framvindu."
        ),
        "runner_1": "Hlaupari 1",
        "runner_2": "Hlaupari 2",
        "pick_two_runners": (
            "Veldu tvo hlaupara hér að ofan til að bera þá saman."
        ),
        "section_compare_progress": "Samanburður framvindu",
        "no_compare_distance": "Engin gögn um vegalengd til samanburðar.",
        "neither_runner_distance": (
            "Hvorugur hlauparinn er með niðurstöður á {distance} km."
        ),
    },
    "en": {
        # Header
        "app_title": "Tímataka Race Tracker 🏃",
        "tagline_md": (
            "Track your running progress across races timed by "
            "**[timataka.net](https://timataka.net/)**."
        ),
        "stats_caption": (
            "Database contains {n_results:,} results across "
            "{n_races} race events."
        ),
        "about_expander": "ℹ️ About the data",
        "about_text": (
            "All race results are sourced from "
            "**[timataka.net](https://timataka.net/)**, "
            "the timing service used by most Icelandic running events. "
            "Only races available there appear in this dashboard — if a "
            "specific race or year is missing upstream, or a page is "
            "temporarily broken on timataka's side, it won't be here "
            "either. Results are limited to events that publish a "
            "*Heildarúrslit / Overall* page; some races only publish "
            "gender or age-split categories."
        ),

        # Tabs
        "tab_profile": "🏃 Runner profile",
        "tab_compare": "⚖️ Compare two runners",

        # Search + picker
        "search_label": "🔎 Search runner by name",
        "search_placeholder": "e.g. Arnar Pétursson",
        "search_prompt": (
            "Type a name above to see that runner's history and progress."
        ),
        "no_matches": "No runners found matching '{search}'.",
        "pick_one": "Found {n} matching runners — pick one:",
        "born_short": "born {year}",
        "born_unknown": "birth year unknown",
        "race_unit_singular": "race",
        "race_unit_plural": "races",

        # Profile
        "born_caption": "Born {year}",
        "metric_total_races": "Total races",
        "metric_years_active": "Years active",
        "metric_best_5k": "Best 5K",
        "metric_best_10k": "Best 10K",
        "section_race_history": "Race history",
        "col_date": "Date",
        "col_year": "Year",
        "col_race": "Race",
        "col_distance": "Distance (km)",
        "col_rank": "Rank",
        "col_chiptime": "Chip time",
        "col_pace": "Pace",
        "col_club": "Club",
        "section_progress": "Progress over time",
        "select_distance": "Distance:",
        "no_distance_info": (
            "No distance information available for this runner's races."
        ),
        "showing_distance": "Showing {distance} km races",
        "no_data_distance": "No data for this distance.",

        # Chart
        "axis_date": "Date",
        "axis_chiptime": "Chip time",
        "tooltip_runner": "Runner",
        "tooltip_race": "Race",
        "tooltip_date": "Date",
        "tooltip_rank": "Rank",
        "tooltip_chiptime": "Chip time",

        # Compare
        "compare_intro": (
            "Search for two runners to put their stats and progression "
            "side by side."
        ),
        "runner_1": "Runner 1",
        "runner_2": "Runner 2",
        "pick_two_runners": "Pick two runners above to compare them.",
        "section_compare_progress": "Progress comparison",
        "no_compare_distance": "No distance data available for comparison.",
        "neither_runner_distance": (
            "Neither runner has results at {distance} km."
        ),
    },
}


def t(key, **kwargs):
    """Return the translated string for the current language.

    Falls back to English if missing in Icelandic, and to the key itself
    if missing in English too. Use {placeholder} syntax + kwargs:

        t("born_short", year=1985)   # 'f. 1985'  or  'born 1985'
    """
    lang = st.session_state.get("lang", "is")
    template = (
        TRANSLATIONS.get(lang, {}).get(key)
        or TRANSLATIONS["en"].get(key)
        or key
    )
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template
    return template