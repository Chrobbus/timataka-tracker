\# Tímataka Race Tracker 🏃



A community dashboard for the Icelandic running scene. Search any

runner who has competed in a timataka.net-timed race and see their

full history — race times, year-over-year progress, personal bests

at every distance.



Built by Daníel Ingi Þórarinsson with \[Streamlit](https://streamlit.io/),

\[Python](https://www.python.org/), and SQLite.



\## Run it locally



```bash

python -m venv venv

.\\venv\\Scripts\\Activate.ps1

pip install -r requirements.txt

python scraper.py        # populate the database (first time only)

streamlit run app.py     # open the dashboard

```



\## How it works



\- `scraper.py` + `discovery.py` crawl timataka.net, extract race

&#x20; results into a local SQLite database.

\- `app.py` is a Streamlit dashboard that reads from that database.

\- `refresh.py` is a one-off maintenance script for re-scraping

&#x20; races where the parser made a mistake.

\- `audit.py` is a debug tool for inspecting any single race page

&#x20; to see what the parser is reading.

