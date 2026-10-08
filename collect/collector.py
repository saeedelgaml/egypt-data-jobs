"""Collector: fetch one day of postings from a source and store them as received.

Run from the project folder:
    python -m collect.collector                       (today)
    python -m collect.collector 2026-10-08            (one day)
    python -m collect.collector 2026-10-01 2026-10-08 (a range of days)
"""
import sys
from datetime import date, datetime, timedelta

from db.schema import DEFAULT_DB_PATH, connect, create_tables
from mock_source.generator import generate_jobs

RAW_COLUMNS = ["source_job_id", "title", "company", "city", "salary_text",
               "skills_text", "posted_date"]


def _to_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def collect_day(con, day, source=generate_jobs):
    """Store one day of postings in raw_jobs and log the day in pipeline_runs.

    source is any function that takes a date and returns a list of posting
    dicts. It defaults to the fake job board, and a real source can replace it
    later. Running the same day twice replaces that day's rows, so nothing
    is stored twice.
    """
    day = _to_date(day)
    jobs = source(day)

    seen_before = {
        row[0]
        for row in con.execute(
            "SELECT DISTINCT source_job_id FROM raw_jobs WHERE collected_on < ?", [day]
        ).fetchall()
    }
    duplicates = sum(1 for job in jobs if job["source_job_id"] in seen_before)
    summary = {
        "run_date": day,
        "rows_collected": len(jobs),
        "rows_new": len(jobs) - duplicates,
        "rows_duplicate": duplicates,
        "status": "collected" if jobs else "empty",
    }

    rows = [[job[col] for col in RAW_COLUMNS] + [day] for job in jobs]
    con.begin()
    try:
        con.execute("DELETE FROM raw_jobs WHERE collected_on = ?", [day])
        con.execute("DELETE FROM pipeline_runs WHERE run_date = ?", [day])
        if rows:
            con.executemany("INSERT INTO raw_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
        con.execute(
            "INSERT INTO pipeline_runs (run_date, rows_collected, rows_new, rows_duplicate, status) "
            "VALUES (?, ?, ?, ?, ?)",
            [day, summary["rows_collected"], summary["rows_new"],
             summary["rows_duplicate"], summary["status"]],
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    return summary


def collect_range(con, start, end, source=generate_jobs):
    """Collect every day from start to end, both included, oldest first."""
    start, end = _to_date(start), _to_date(end)
    summaries = []
    day = start
    while day <= end:
        summaries.append(collect_day(con, day, source))
        day += timedelta(days=1)
    return summaries


def main():
    args = sys.argv[1:]
    if len(args) == 0:
        start = end = date.today()
    elif len(args) == 1:
        start = end = _to_date(args[0])
    else:
        start, end = _to_date(args[0]), _to_date(args[1])

    con = connect()
    create_tables(con)
    for s in collect_range(con, start, end):
        print(f"{s['run_date']}: collected {s['rows_collected']}, new {s['rows_new']}, "
              f"duplicates {s['rows_duplicate']}, status {s['status']}")
    total = con.execute("SELECT COUNT(*) FROM raw_jobs").fetchone()[0]
    print(f"raw_jobs now holds {total} rows in {DEFAULT_DB_PATH}")
    con.close()


if __name__ == "__main__":
    main()
