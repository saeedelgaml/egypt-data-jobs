# Egypt data jobs

A pipeline that collects data-job postings, cleans them, stores them in DuckDB, and answers questions about them through a chatbot. The chatbot answers questions typed in plain English about salaries, skills, companies, cities and new postings. It is free to run and needs no account or key.

All data in this repository is synthetic. A small program generates fake job postings with messy city names, salary formats and duplicates, so the cleaning steps have real work to do. No real job board text is stored here, and none of the numbers describe the real Egyptian job market. Company names are invented, and any match with a real company is a coincidence.

## Status

Phases 1 to 10 are done: the repository layout, the DuckDB tables, the generator for fake job postings, the collector that stores each day's postings, the cleaner that turns them into tidy tables, the manager script that runs both once a day, the nine fixed answers the chatbot can give, and a free rule-based router that reads a typed question and picks one of them. An optional AI router is also included. A Streamlit web page sits on top of them.

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

## Asking questions

The chatbot has nine answers. Each one is a function in `chatbot/queries.py` that runs one fixed SQL query, so the numbers always come from the database. Salaries are monthly amounts in EGP. Most answers accept filters for role, city and skill, and `count_postings` also takes a minimum salary.

```
python -m chatbot.ask
python -m chatbot.ask new_postings role=data_engineer days=7
python -m chatbot.ask salary_for_role role=data_analyst city=Cairo
python -m chatbot.ask top_paying group_by=city role=data_engineer
```

The other answers are `top_skills`, `skills_with` (skills that appear together with another skill), `top_companies`, `jobs_by_city`, `jobs_by_role` and `count_postings`. A role, city or skill that does not exist is refused with a message that lists the valid ones. Values are passed to SQL as parameters and never pasted into the query text. A ranking in `top_paying` only counts a group that has at least 3 postings with a listed salary.

## Asking in plain English

```
python -m chatbot.chat "what does a data analyst earn in Cairo?"
python -m chatbot.chat
```

A rule-based router reads the question, fixes small typos, finds the role, city, skill, numbers and time words, and picks one of the nine answers. It is free, runs on your computer and sends nothing anywhere. It can only point at the functions in `chatbot/queries.py`, which check every value again.

Every answer starts with a line such as `Understood as: salary: data analyst, in Cairo`, so a wrong reading is visible. When a question is not about this data (a role, city or skill that is not here, or a subject unrelated to jobs), the router refuses instead of guessing. When a limit applies, a `Note:` line says so: seniority is not tracked, some job titles are grouped under "other", and most answers do not filter by date.

Limits of this router: it understands the wording it was written for, and unusual phrasing can get a refusal or a different reading than you meant. It cannot answer a question that none of the nine answers covers, and it cannot write new queries. How often it is right on questions it was not built around is in `docs/accuracy.md`: about 80 percent on the first run of three question sets.

Each question and the answer it was routed to are logged in `data/chat.log`.

### The web page

```
streamlit run app.py
```

The page uses `data/jobs.duckdb` when it exists and `data/sample.duckdb` otherwise. It has a search box, clickable example questions grouped by topic, a "How to ask" panel, an "Read as" line that shows how the question was understood, follow-up questions after every answer, and a short note that all data is synthetic. It follows the light or dark setting of the visitor's device and works on a phone. Fonts load from Google Fonts. The page only talks to `chatbot/service.py`, escapes everything it shows, and has tests for that in `tests/test_app.py`.

### The service behind it

`chatbot/service.py` is the one door a web page should use. It opens the database read-only, limits how often one visitor can ask, and returns the answer, the numbers, follow-up questions and advice on how to ask. `docs/ui-brief.md` describes the page to build on top of it. `python make_sample_db.py` builds `data/sample.duckdb`, a small synthetic database that is safe to publish.

### Optional: an AI router

```
python -m chatbot.chat --ai "what does a data analyst earn in Cairo?"
```

An AI model picks the answer instead of the rules. It never sees the database and it does not write the reply: the program runs the chosen function and writes the answer from the query result. Only the typed question is sent to the AI service, and the service may charge for it.

To use it, create a file named `.env` in the project folder with the line `LLM_API_KEY=` followed by your key (see `.env.example`). The file is listed in `.gitignore`, and a test fails if a key-like string appears anywhere else in the project. The default model is `claude-haiku-5-5`, which you can change with `LLM_MODEL` in the same file.
