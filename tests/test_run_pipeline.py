from datetime import date, timedelta

import pytest

import run_pipeline as manager
from db.schema import connect, create_tables
from mock_source.generator import generate_jobs

DAY = date(2026, 10, 1)


@pytest.fixture
def con():
    c = connect(":memory:")
    create_tables(c)
    yield c
    c.close()


def count(con, table):
    return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_first_run_collects_only_today(con):
    result = manager.run_pipeline(con, DAY)
    assert result["days_collected"] == [DAY]
    assert count(con, "pipeline_runs") == 1


def test_first_run_cleans_what_it_collected(con):
    result = manager.run_pipeline(con, DAY)
    assert result["cleaned"]["jobs_added"] == result["rows_new"]
    assert count(con, "jobs") == result["rows_new"]


def test_missed_days_are_collected_on_the_next_run(con):
    manager.run_pipeline(con, DAY)
    result = manager.run_pipeline(con, DAY + timedelta(days=3))
    assert result["days_collected"] == [DAY + timedelta(days=i) for i in (1, 2, 3)]
    assert count(con, "pipeline_runs") == 4


def test_catch_up_gives_the_same_data_as_running_every_day(con):
    manager.run_pipeline(con, DAY)
    manager.run_pipeline(con, DAY + timedelta(days=3))

    other = connect(":memory:")
    create_tables(other)
    for i in range(4):
        manager.run_pipeline(other, DAY + timedelta(days=i))

    query = "SELECT job_id, role, city, salary_min, salary_max FROM jobs ORDER BY job_id"
    assert con.execute(query).fetchall() == other.execute(query).fetchall()
    other.close()


def test_running_twice_on_the_same_day_does_nothing_the_second_time(con):
    manager.run_pipeline(con, DAY)
    jobs_before = count(con, "jobs")
    second = manager.run_pipeline(con, DAY)
    assert second["days_collected"] == []
    assert second["cleaned"]["jobs_added"] == 0
    assert count(con, "jobs") == jobs_before
    assert count(con, "pipeline_runs") == 1


def test_since_sets_the_start_when_the_diary_is_empty(con):
    result = manager.run_pipeline(con, DAY, since=DAY - timedelta(days=2))
    assert len(result["days_collected"]) == 3


def test_since_is_ignored_once_the_diary_has_history(con):
    manager.run_pipeline(con, DAY)
    result = manager.run_pipeline(con, DAY + timedelta(days=1), since=DAY - timedelta(days=30))
    assert result["days_collected"] == [DAY + timedelta(days=1)]


def test_a_failed_day_is_retried_by_the_next_run(con):
    bad_day = DAY + timedelta(days=2)

    def flaky(day):
        if day == bad_day:
            raise RuntimeError("job board is down")
        return generate_jobs(day)

    with pytest.raises(RuntimeError):
        manager.run_pipeline(con, DAY + timedelta(days=3), source=flaky, since=DAY)
    # days before the failure are safe in the diary
    assert count(con, "pipeline_runs") == 2

    result = manager.run_pipeline(con, DAY + timedelta(days=3))
    assert result["days_collected"] == [bad_day, DAY + timedelta(days=3)]
    assert count(con, "pipeline_runs") == 4


def test_a_cleaning_failure_is_repaired_by_the_next_run(con, monkeypatch):
    def broken(_con):
        raise RuntimeError("cleaner crashed")

    monkeypatch.setattr(manager, "clean_raw", broken)
    with pytest.raises(RuntimeError):
        manager.run_pipeline(con, DAY)
    assert count(con, "raw_jobs") > 0
    assert count(con, "jobs") == 0

    monkeypatch.undo()
    result = manager.run_pipeline(con, DAY)
    assert result["days_collected"] == []
    assert result["cleaned"]["jobs_added"] > 0
    assert count(con, "jobs") == result["cleaned"]["jobs_added"]


def test_main_writes_one_log_line_and_returns_zero(tmp_path):
    db, log = tmp_path / "jobs.duckdb", tmp_path / "pipeline.log"
    assert manager.main(["2026-10-01"], db_path=db, log_path=log) == 0
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert "ok:" in lines[0] and "collected 1 day(s) (2026-10-01)" in lines[0]

    assert manager.main(["2026-10-01"], db_path=db, log_path=log) == 0
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert "no new days to collect" in lines[1]


def test_main_logs_a_failure_and_returns_one(tmp_path, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(manager, "run_pipeline", broken)
    log = tmp_path / "pipeline.log"
    assert manager.main(["2026-10-01"], db_path=tmp_path / "jobs.duckdb", log_path=log) == 1
    assert "FAILED: RuntimeError: boom" in log.read_text(encoding="utf-8")


def test_log_goes_next_to_the_database_by_default(tmp_path):
    db = tmp_path / "data" / "jobs.duckdb"
    manager.main(["2026-10-01"], db_path=db)
    assert (tmp_path / "data" / "pipeline.log").exists()
