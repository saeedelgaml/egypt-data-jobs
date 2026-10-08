from pathlib import Path

root = Path(".")
if not (root / "pytest.ini").exists():
    raise SystemExit("Run this from inside the egypt-data-jobs folder.")

collector = r'''"""Collector: fetch one day of postings from a source and store them as received.

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
'''

test_collector = r'''from datetime import date, timedelta

import pytest

from collect.collector import collect_day, collect_range
from db.schema import connect, create_tables
from mock_source.generator import generate_jobs

DAY = date(2026, 10, 8)


@pytest.fixture
def con():
    c = connect(":memory:")
    create_tables(c)
    yield c
    c.close()


def count(con, table):
    return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_collect_day_stores_every_posting_as_received(con):
    summary = collect_day(con, DAY)
    expected = generate_jobs(DAY)
    assert summary["rows_collected"] == len(expected)
    assert count(con, "raw_jobs") == len(expected)
    stored = {r[0] for r in con.execute("SELECT source_job_id FROM raw_jobs").fetchall()}
    assert stored == {j["source_job_id"] for j in expected}


def test_raw_text_is_not_cleaned(con):
    collect_day(con, DAY)
    cities = {r[0] for r in con.execute("SELECT city FROM raw_jobs").fetchall()}
    assert cities == {j["city"] for j in generate_jobs(DAY)}


def test_collected_on_is_the_collection_day(con):
    collect_day(con, DAY)
    days = {r[0] for r in con.execute("SELECT collected_on FROM raw_jobs").fetchall()}
    assert days == {DAY}


def test_first_day_has_no_duplicates(con):
    summary = collect_day(con, DAY)
    assert summary["rows_new"] == summary["rows_collected"]
    assert summary["rows_duplicate"] == 0
    assert summary["status"] == "collected"


def test_second_day_counts_repeats_as_duplicates(con):
    collect_day(con, DAY)
    second = collect_day(con, DAY + timedelta(days=1))
    seen = {j["source_job_id"] for j in generate_jobs(DAY)}
    expected = sum(1 for j in generate_jobs(DAY + timedelta(days=1))
                   if j["source_job_id"] in seen)
    assert expected > 0
    assert second["rows_duplicate"] == expected
    assert second["rows_new"] + second["rows_duplicate"] == second["rows_collected"]


def test_pipeline_runs_gets_one_line_per_day(con):
    collect_range(con, DAY, DAY + timedelta(days=2))
    assert count(con, "pipeline_runs") == 3


def test_running_the_same_day_twice_does_not_double_rows(con):
    collect_day(con, DAY)
    first = count(con, "raw_jobs")
    collect_day(con, DAY)
    assert count(con, "raw_jobs") == first
    assert count(con, "pipeline_runs") == 1


def test_accepts_a_date_string(con):
    collect_day(con, "2026-10-08")
    assert count(con, "raw_jobs") == len(generate_jobs(DAY))


def test_a_custom_source_can_replace_the_fake_board(con):
    def tiny_source(day):
        return [{"source_job_id": "x1", "title": "Data Engineer", "company": "Acme",
                 "city": "Cairo", "salary_text": None, "skills_text": "SQL",
                 "posted_date": day.isoformat()}]

    summary = collect_day(con, DAY, source=tiny_source)
    assert summary["rows_collected"] == 1
    assert count(con, "raw_jobs") == 1


def test_an_empty_day_is_logged_as_empty(con):
    summary = collect_day(con, DAY, source=lambda day: [])
    assert summary["status"] == "empty"
    assert count(con, "raw_jobs") == 0
    assert con.execute("SELECT status FROM pipeline_runs").fetchone()[0] == "empty"
'''

files = {
    "collect/collector.py": collector,
    "tests/test_collector.py": test_collector,
}

for name, text in files.items():
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

readme = root / "README.md"
text = readme.read_text(encoding="utf-8")
old = "Phases 1 to 3 are done: the repository layout, the DuckDB tables, and the generator for fake job postings. Collection, cleaning, automation and the chatbot come in later phases."
new = "Phases 1 to 4 are done: the repository layout, the DuckDB tables, the generator for fake job postings, and the collector that stores each day's postings. Cleaning, automation and the chatbot come in later phases."
if old in text:
    readme.write_text(text.replace(old, new), encoding="utf-8")

print("Phase 4 files written:")
for name in files:
    print("  ", name)