"""Salary parsing limits, the data-quality report and failed runs in pipeline_runs."""
from datetime import date

import duckdb
import pytest

import run_pipeline as manager
from clean.cleaner import clean_raw
from clean.quality import quality_report
from clean.rules import parse_salary
from db.schema import connect, create_tables


@pytest.mark.parametrize("text, expected", [
    ("20k-30k", (20000, 30000)),
    ("EGP 240,000 - 360,000 per year", (20000, 30000)),
    ("300k annual", (25000, 25000)),
    ("1500-2500 USD", (None, None)),
    ("$3000 - $4000 a month", (None, None)),
    ("EUR 2,000", (None, None)),
    ("150 - 250 EGP per hour", (None, None)),
    ("5", (None, None)),                       # too small to be a monthly salary
    ("20000000 - 30000000", (None, None)),     # too large to be a monthly salary
    ("Sarah's team pays 20k-30k", (20000, 30000)),
])
def test_parse_salary_rejects_what_it_cannot_trust(text, expected):
    assert parse_salary(text) == expected


def _con_with(rows):
    con = connect(":memory:")
    create_tables(con)
    con.executemany("INSERT INTO raw_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    clean_raw(con)
    return con


def _raw(i, title="Data Engineer", company="Sphinx Data Labs", city="Cairo", salary="20k-30k",
         skills="Python, SQL"):
    return (f"id-{i}", title, company, city, salary, skills, date(2026, 10, 1), date(2026, 10, 1))


def test_cleaner_counts_salary_text_it_could_not_read():
    con = connect(":memory:")
    create_tables(con)
    con.executemany("INSERT INTO raw_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [_raw(1), _raw(2, salary="Confidential"), _raw(3, salary="2000 USD")])
    summary = clean_raw(con)
    assert summary["missing_salary"] == 2 and summary["salary_unreadable"] == 1


def test_quality_report_is_quiet_for_healthy_data_and_loud_for_bad_data():
    healthy = _con_with([_raw(i, company=f"Co {i}") for i in range(10)])
    report = quality_report(healthy)
    assert report["jobs"] == 10 and report["warnings"] == []
    bad = _con_with([_raw(i, company=None, city="Mars", salary=None, skills=None, title="Chef") for i in range(10)])
    text = " ".join(quality_report(bad)["warnings"])
    for word in ("no salary", "no city", "no company", "no skills", "other role"):
        assert word in text
    assert quality_report(_empty())["warnings"] == ["the jobs table is empty"]


def _empty():
    con = connect(":memory:")
    create_tables(con)
    return con


def test_probable_reposts_are_counted_but_not_deleted():
    rows = [_raw(1), _raw(2), _raw(3, company="Other Co")]  # 1 and 2 only differ by id
    con = _con_with(rows)
    assert quality_report(con)["probable_reposts"] == 1
    assert con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 3


def test_a_failed_run_is_logged_in_pipeline_runs_and_does_not_skip_the_day(tmp_path, monkeypatch):
    db, log = tmp_path / "jobs.duckdb", tmp_path / "pipeline.log"

    def boom(*args, **kwargs):
        raise RuntimeError("source is down")

    monkeypatch.setattr(manager, "run_pipeline", boom)
    assert manager.main(["2026-10-05"], db_path=db, log_path=log) == 1
    assert "FAILED: RuntimeError: source is down" in log.read_text(encoding="utf-8")
    con = duckdb.connect(str(db))
    assert con.execute("SELECT run_date, status FROM pipeline_runs").fetchall() == [(date(2026, 10, 5), "failed")]
    con.close()

    monkeypatch.undo()
    assert manager.main(["2026-10-05"], db_path=db, log_path=log) == 0
    con = duckdb.connect(str(db))
    statuses = con.execute("SELECT DISTINCT status FROM pipeline_runs").fetchall()
    assert ("failed",) not in statuses and con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] > 0
    con.close()
