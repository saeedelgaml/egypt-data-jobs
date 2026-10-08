# Egypt data jobs

A pipeline that collects data-job postings, cleans them, stores them in DuckDB, and answers questions about them through a chatbot. The chatbot can list new data engineer postings, show salaries for a role, and name the top skills.

All data in this repository is synthetic. A small program generates fake job postings with messy city names, salary formats and duplicates, so the cleaning steps have real work to do. No real job board text is stored here, and none of the numbers describe the real Egyptian job market.

## Status

Phase 1 is done: the repository layout and a smoke test. The pipeline, database and chatbot come in later phases.

## Setup

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

On Windows, activate the environment with .venv\Scripts\activate.
