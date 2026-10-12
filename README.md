# Egypt Data Jobs

[![Tests and deploy site](https://github.com/saeedelgaml/egypt-data-jobs/actions/workflows/pages.yml/badge.svg)](https://github.com/saeedelgaml/egypt-data-jobs/actions/workflows/pages.yml)

**Live site: https://saeedelgaml.github.io/egypt-data-jobs/** (ask questions like "What does an AI engineer earn in Cairo?")

> **The data is synthetic.** Every posting comes from `mock_source/generator.py`, a program that invents messy job ads. Company names are made up and nothing here describes the real Egyptian job market. The pipeline is built to accept a real source later: only the `source` function passed to the collector has to change.

## What it is, in 30 seconds

A small data-engineering project, end to end:

```
mock_source/generator.py ─▶ collect (raw_jobs) ─▶ clean (jobs, job_skills) ─▶ DuckDB ─▶ export_site_data.py ─▶ site/data/jobs.json
        daily on Windows Task Scheduler (run_pipeline.py)                                        │
                                                             GitHub Pages page: rule-based chatbot + Insights charts, in the browser
```

- **Pipeline** (`run_pipeline.py`): collects every missed day, cleans messy cities, salaries (EGP, yearly or foreign amounts handled), titles and skills into 14 data roles, skips duplicates, writes a data-quality report and logs failures.
- **Chatbot**: a free rule-based router reads a question and picks one of nine fixed, parameter-checked answers. It never writes free-form SQL, is read-only, caps results at 20 rows and 90 days, and says how it understood you ("Read as ..."). About 80% right on questions it was not built around (`docs/accuracy.md`).
- **Website** (`site/`): static, no server. The same router and answers run in your browser on one JSON file, so nothing you type leaves the page. It has an Insights section (Chart.js) and shows "Data last updated".
- **Optional paid AI router**: `python -m chatbot.chat --ai ...` runs locally only. No key is ever in the site or the repository.

## What it demonstrates

Scheduled catch-up ETL with idempotent runs, rule-based cleaning with tests, a guarded query layer, one shared config (`config.py`), a Python and JavaScript implementation kept identical by a golden-file test, accessible static front end, and CI that tests then deploys.

## Roles covered

Data analyst, BI developer, business analyst, data engineer, analytics engineer, data scientist, ML engineer, AI engineer, MLOps engineer, NLP engineer, computer vision engineer, data architect, big data engineer and GenAI/LLM engineer, plus "other". Each has its own skills, seniority levels and (invented) salary bands in `config.py`, and aliases such as "AI eng", "ML eng" and "LLM".

## Run it

```
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                            # Python tests
node --test                       # browser chatbot tests (Node 20+)
```

`requirements.txt` is enough for the pipeline, the chatbot and the export; `requirements-extras.txt` adds the local Streamlit page (`streamlit run app.py`) and the AI router.

```
python run_pipeline.py                  # collect missed days, clean, quality report
python run_pipeline.py --export-site    # same, then refresh site/data/jobs.json
python make_sample_db.py                # rebuild data/sample.duckdb (60 synthetic days)
python export_site_data.py --db data/sample.duckdb
python -m chatbot.chat "what does a data analyst earn in Cairo?"
python -m http.server 8000 --directory site    # preview the site locally
```

The daily run stays on Windows Task Scheduler (`python run_pipeline.py`, optionally with `--export-site`). Each run adds a line to `data/pipeline.log` and exits 0 or 1; a failed run is also a row in `pipeline_runs`. After a refresh, commit `site/data/jobs.json` and push: the workflow deploys it.

## Keeping Python and the browser identical

`make_router_golden.py` writes `tests/data/router_golden.json`: what the Python chatbot answers for 350+ questions. `node --test` replays every one in JavaScript, and a Python test fails if the file is stale. Change the router, answers or sample data, then run `python make_router_golden.py`.

## Layout

`config.py` shared lists and limits · `mock_source/` generator · `collect/` · `clean/` (rules, cleaner, quality) · `db/` · `chatbot/` (router, queries, text, service, AI) · `site/` static website · `export_site_data.py` · `tests/`, `tests_js/` · `docs/` (accuracy, UI brief) · `show.py` prints a table from the database.

More: `CHANGES.md` lists what changed and why. Franco-Arabic ("kam wazifa") is deliberately not supported.
