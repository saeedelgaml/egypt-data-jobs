from datetime import date, timedelta

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
