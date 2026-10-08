"""Manager: run the whole pipeline in order, catching up on missed days.

Run from the project folder:
    python run_pipeline.py                      (collect up to today, then clean)
    python run_pipeline.py 2026-10-08           (pretend that today is this date)
    python run_pipeline.py --since 2026-10-01   (first run only: start on this day)

The manager reads pipeline_runs to find the last day that was collected, then
collects every day after it up to today. A PC that was off for three days
therefore catches up on the next run. Cleaning runs every time and only touches
postings that are not in jobs yet, so a run that stopped halfway is repaired by
the next one.

Each run adds one line to data/pipeline.log and exits with 0 (ok) or 1 (failed),
so Windows Task Scheduler can show whether the last run worked.
"""
import argparse
import sys
from datetime import datetime, timedelta

from clean.cleaner import clean_raw
from collect.collector import _to_date, collect_range
from db.schema import DEFAULT_DB_PATH, connect, create_tables
from mock_source.generator import generate_jobs


def run_pipeline(con, today, source=generate_jobs, since=None):
    """Collect every missing day up to today, then clean. Returns a summary dict.

    since is only used when pipeline_runs is empty (the very first run). After
    that the diary decides where to start.
    """
    today = _to_date(today)
    last_done = con.execute("SELECT MAX(run_date) FROM pipeline_runs").fetchone()[0]
    if last_done is not None:
        start = _to_date(last_done) + timedelta(days=1)
    elif since is not None:
        start = _to_date(since)
    else:
        start = today

    days = collect_range(con, start, today, source) if start <= today else []
    cleaned = clean_raw(con)
    return {
        "days_collected": [d["run_date"] for d in days],
        "rows_collected": sum(d["rows_collected"] for d in days),
        "rows_new": sum(d["rows_new"] for d in days),
        "cleaned": cleaned,
    }


def describe(result):
    """One readable line about what a run did."""
    days = result["days_collected"]
    if days:
        span = str(days[0]) if len(days) == 1 else f"{days[0]} to {days[-1]}"
        collected = f"collected {len(days)} day(s) ({span}), {result['rows_new']} new postings"
    else:
        collected = "no new days to collect"
    c = result["cleaned"]
    return f"{collected}; cleaned: {c['jobs_added']} jobs, {c['job_skills_added']} job_skills, {c['skills_added']} new skills"


def main(argv=None, db_path=DEFAULT_DB_PATH, log_path=None):
    parser = argparse.ArgumentParser(description="Run the whole pipeline once.")
    parser.add_argument("today", nargs="?", help="pretend today is this date (YYYY-MM-DD)")
    parser.add_argument("--since", help="first run only: start collecting on this date")
    args = parser.parse_args(argv)

    today = _to_date(args.today) if args.today else datetime.now().date()
    log_path = log_path or (db_path.parent / "pipeline.log")

    code = 0
    con = None
    try:
        con = connect(db_path)
        create_tables(con)
        message = "ok: " + describe(run_pipeline(con, today, since=args.since))
    except Exception as exc:  # the log must record every failure
        message = f"FAILED: {type(exc).__name__}: {exc}"
        code = 1
    finally:
        if con is not None:
            con.close()

    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} (today={today}) {message}"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
