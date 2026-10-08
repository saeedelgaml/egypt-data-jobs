# Egypt data jobs

A pipeline that collects data-job postings, cleans them, stores them in DuckDB, and answers questions about them through a chatbot. The chatbot can list new data engineer postings, show salaries for a role, and name the top skills.

All data in this repository is synthetic. A small program generates fake job postings with messy city names, salary formats and duplicates, so the cleaning steps have real work to do. No real job board text is stored here, and none of the numbers describe the real Egyptian job market. Company names are invented, and any match with a real company is a coincidence.

## Status

Phases 1 to 8 are done: the repository layout, the DuckDB tables, the generator for fake job postings, the collector that stores each day's postings, the cleaner that turns them into tidy tables, the manager script that runs both once a day, the six fixed answers the chatbot can give, and an AI layer that reads a typed question and picks one of those answers. The web page comes in a later phase.

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

The chatbot can give six answers. Each one is a function in `chatbot/queries.py` that runs one fixed SQL query, so the numbers always come from the database. Salaries are monthly amounts in EGP.

```
python -m chatbot.ask
python -m chatbot.ask new_postings role=data_engineer days=7
python -m chatbot.ask salary_for_role role=data_analyst city=Cairo
python -m chatbot.ask top_skills role=data_engineer limit=5
```

The other three answers are `top_companies`, `jobs_by_city` and `count_postings`. A role or city that does not exist is refused with a message that lists the valid ones. Values are passed to SQL as parameters and never pasted into the query text.

## Asking in plain English

```
python -m chatbot.chat "what does a data analyst earn in Cairo?"
```

An AI model reads the question and picks one of the six answers above, with its parameters. It never sees the database and it does not write the reply. The program runs the chosen function, which checks every value again, and writes the answer from the query result. A question that matches no answer gets a short help message. The model cannot run any query that is not in `chatbot/queries.py`.

Only the typed question is sent to the AI service. No rows and no job text leave the computer. Each question and the answer it was routed to are logged in `data/chat.log`.

To use it, create a file named `.env` in the project folder with the line `LLM_API_KEY=` followed by your key (see `.env.example`). The file is listed in `.gitignore`, and a test fails if a key-like string appears anywhere else in the project. The default model is `claude-haiku-5-5`, which you can change with `LLM_MODEL` in the same file.
