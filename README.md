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

## Local AI mode (optional)

When none of the nine fixed answers fits a question, the Python chatbot can ask a **local** model to write one SQL query. It is free, needs no key, and nothing leaves your computer. The public website never uses it.

1. Install [Ollama](https://ollama.com) and start it (it listens on `http://localhost:11434`).
2. `ollama pull qwen2.5-coder:3b` (change the model with the `OLLAMA_MODEL` environment variable).
3. `pip install -r requirements-extras.txt`, then `python -m chatbot.chat "which jobs mention both docker and kubernetes"`. Add `--no-local-ai` to switch it off.

How it stays safe (all checked in code, not only in the prompt):
- A fixed answer is always tried first; the AI is only a fallback.
- Off-topic or "ignore your rules" questions are refused by a keyword check, then a yes/no check, with 3 example questions shown.
- The SQL is parsed with sqlglot: exactly one `SELECT`, no `INSERT/UPDATE/DELETE/DROP/ATTACH/PRAGMA`, only the tables `jobs`, `job_skills`, `skills`, `roles` and their columns, and a short list of allowed functions.
- `LIMIT 20` is forced, the database is opened read-only, and a query is stopped after 5 seconds.
- A failing query goes back to the model once; a second failure ends in a polite refusal.
- Every AI answer shows the SQL under "AI-generated query, check before relying on it".
- If Ollama is not running, you get the usual "can't answer" message and nothing crashes. Tests use a fake model, so CI needs no Ollama.

Demo video: _(link coming soon)_

## Answers from real reports (RAG, optional, local only)

The jobs database is synthetic, but some questions ("How many jobs will be created and displaced by 2030?", "What degree do Egyptian job ads ask for?") are about the **real labour market**. For those, the Python chatbot can answer from five published documents. It is free, needs no key, runs only on your computer, and is not part of the website.

How it works: fixed answers first, then retrieval over the documents (no model call needed to decide), then the local SQL fallback, then a refusal. If the best matching passage scores at least 0.37 (cosine similarity), a local Ollama model writes 3-5 sentences using only the numbered excerpts, with citations. Every number in the answer must appear in the excerpts, otherwise two quotes are shown instead. Answers start with **"From the reports"** and end with a sources list (title, year, page); database answers keep their own labels.

| Source | Publisher | Year / data period | Link |
|---|---|---|---|
| The Future of Jobs Report 2025 (pages 1-111) | World Economic Forum | January 2025 | https://www.weforum.org/publications/the-future-of-jobs-report-2025/ |
| ECES Working Paper 241, Egyptian online job postings (pages 2-30) | Egyptian Center for Economic Studies | data Q4 2021 - Q4 2024 | no link recorded |
| Labour market transitions of young women and men in Egypt | ILO | June 2014 (survey from 2012) | no link recorded |
| Egypt Jobs Issue Brief No. 4 (pages 1-2) | World Bank | c. 2014 | https://www.albankaldawli.org/content/dam/Worldbank/Feature%20Story/mena/Egypt/Egypt-Doc/egy-jobs-issue-brief-4-ENG-ARA.pdf |
| The Complete Data Science Resume Guide in 2025 | 365 Data Science | 17 January 2025 | https://365datascience.com/data-science-resume/ |

**The documents are not in this repository** (they are listed in `rag/sources.json` and git-ignored, like the index). Download them yourself, save them in `rag/docs/` as `wef-fojr-2025.pdf`, `eces-wp241.pdf`, `ilo-swts-egypt.pdf`, `wb-egypt-brief4.pdf` and `365ds-resume-guide.txt` (the guide as plain text), then:

```
pip install -r requirements-extras.txt
python -m rag.ingest                       # builds rag/index (chunks + embeddings, all-MiniLM-L6-v2)
python -m rag.calibrate                    # prints the best retrieval score of every test question
ollama pull qwen2.5:3b                     # recommended; any installed model is used if it is missing
python -m chatbot.chat "What degree do Egyptian job ads ask for?"     # --no-rag switches it off
pytest tests/test_rag.py --runslow         # includes the tests that call a real model
```

Without the documents or the index, the RAG route is skipped and its tests skip. Set `OLLAMA_MODEL` to choose the model.

Limits: two sources are old (the ILO survey is from 2012 and the World Bank brief is about 2014), so their figures describe the labour market of that time. The ECES paper covers online postings only. A small local model can misread an excerpt, so check the cited page. The jobs database stays synthetic and is never mixed with the reports: an answer is either "From the reports" or from the database.

## Keeping Python and the browser identical

`make_router_golden.py` writes `tests/data/router_golden.json`: what the Python chatbot answers for 350+ questions. `node --test` replays every one in JavaScript, and a Python test fails if the file is stale. Change the router, answers or sample data, then run `python make_router_golden.py`.

## Layout

`config.py` shared lists and limits · `mock_source/` generator · `collect/` · `clean/` (rules, cleaner, quality) · `db/` · `chatbot/` (router, queries, text, service, AI) · `site/` static website · `export_site_data.py` · `tests/`, `tests_js/` · `docs/` (accuracy, UI brief) · `show.py` prints a table from the database.

More: `CHANGES.md` lists what changed and why. Franco-Arabic ("kam wazifa") is deliberately not supported.
