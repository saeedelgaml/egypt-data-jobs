# Egypt data jobs

A pipeline that collects data-job postings, cleans them, stores them in DuckDB, and answers questions about them through a chatbot. The chatbot can list new data engineer postings, show salaries for a role, and name the top skills.

All data in this repository is synthetic. A small program generates fake job postings with messy city names, salary formats and duplicates, so the cleaning steps have real work to do. No real job board text is stored here, and none of the numbers describe the real Egyptian job market. Company names are invented, and any match with a real company is a coincidence.

## Status

Phases 1 to 6 are done: the repository layout, the DuckDB tables, the generator for fake job postings, the collector that stores each day's postings, the cleaner that turns them into tidy tables, and the manager script that runs both once a day. The chatbot comes in later phases.

## Setup

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

On Windows, activate the environment with `.venv\Scripts\activate`.

## Running the pipeline

```
python run_pipeline.py
```

This collects every day since the last run, up to today, and then cleans the new postings. If the computer was off for a few days, the next run collects the missed days. Running it twice on the same day changes nothing. The first run on an empty database collects only today, unless you pass a start date with `--since 2026-10-01`.

Each run adds one line to `data/pipeline.log` and exits with 0 when it worked and 1 when it failed. On Windows, Task Scheduler can run the command once a day and show that exit code.
