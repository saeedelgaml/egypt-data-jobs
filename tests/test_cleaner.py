from datetime import date, timedelta

import pytest

from clean.cleaner import clean_raw
from collect.collector import collect_day, collect_range
from db.schema import connect, create_tables
from mock_source.generator import generate_truth

START = date(2026, 10, 1)
DAYS = 30


@pytest.fixture(scope="module")
def cleaned():
    con = connect(":memory:")
    create_tables(con)
    collect_range(con, START, START + timedelta(days=DAYS - 1))
    summary = clean_raw(con)
    yield con, summary
    con.close()


def truth_by_id():
    truth = {}
    for i in range(DAYS):
        truth.update(generate_truth(START + timedelta(days=i)))
    return truth


def test_one_job_per_new_posting(cleaned):
    con, summary = cleaned
    new_total = con.execute("SELECT SUM(rows_new) FROM pipeline_runs").fetchone()[0]
    jobs = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    assert jobs == new_total == summary["jobs_added"]


def test_no_duplicate_jobs(cleaned):
    con, _ = cleaned
    distinct = con.execute("SELECT COUNT(DISTINCT job_id) FROM jobs").fetchone()[0]
    assert distinct == con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]


def test_roles_match_the_answer_key(cleaned):
    con, _ = cleaned
    truth = truth_by_id()
    for job_id, role in con.execute("SELECT job_id, role FROM jobs").fetchall():
        assert role == truth[job_id]["role"], job_id


def test_cities_match_the_answer_key(cleaned):
    con, _ = cleaned
    truth = truth_by_id()
    for job_id, city in con.execute("SELECT job_id, city FROM jobs").fetchall():
        assert city == truth[job_id]["city"], job_id


def test_companies_match_the_answer_key(cleaned):
    con, _ = cleaned
    truth = truth_by_id()
    for job_id, company in con.execute("SELECT job_id, company FROM jobs").fetchall():
        assert company == truth[job_id]["company"], job_id


def test_salaries_match_the_answer_key(cleaned):
    con, _ = cleaned
    truth = truth_by_id()
    rows = con.execute("SELECT job_id, salary_min, salary_max FROM jobs").fetchall()
    visible = 0
    for job_id, low, high in rows:
        t = truth[job_id]
        if t["salary_visible"]:
            assert (low, high) == (t["salary_min"], t["salary_max"]), job_id
            visible += 1
        else:
            assert (low, high) == (None, None), job_id
    assert visible > 100


def test_skills_match_the_answer_key(cleaned):
    con, _ = cleaned
    truth = truth_by_id()
    stored = {}
    for job_id, skill in con.execute("SELECT job_id, skill FROM job_skills").fetchall():
        stored.setdefault(job_id, set()).add(skill)
    for (job_id,) in con.execute("SELECT job_id FROM jobs").fetchall():
        t = truth[job_id]
        expected = set(t["skills"]) if t["skills_visible"] else set()
        assert stored.get(job_id, set()) == expected, job_id


def test_dates_are_filled_in(cleaned):
    con, _ = cleaned
    bad = con.execute(
        "SELECT COUNT(*) FROM jobs WHERE posted_date IS NULL OR first_seen_date IS NULL"
    ).fetchone()[0]
    assert bad == 0
    same = con.execute(
        "SELECT COUNT(*) FROM jobs WHERE first_seen_date < posted_date"
    ).fetchone()[0]
    assert same == 0


def test_every_skill_is_listed_once(cleaned):
    con, _ = cleaned
    skills = [r[0] for r in con.execute("SELECT skill FROM skills").fetchall()]
    assert len(skills) == len({s.lower() for s in skills})
    assert {"Python", "SQL", "Airflow", "dbt"} <= set(skills)


def test_running_the_cleaner_again_adds_nothing(cleaned):
    con, _ = cleaned
    before = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    again = clean_raw(con)
    assert again["jobs_added"] == 0
    assert con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == before


def test_a_new_skill_is_added_automatically():
    con = connect(":memory:")
    create_tables(con)

    def source(day):
        return [{"source_job_id": "n1", "title": "Data Engineer", "company": "Acme Ltd.",
                 "city": "New Cairo", "salary_text": "20k-30k",
                 "skills_text": "python, terraform", "posted_date": day.isoformat()}]

    collect_day(con, date(2026, 10, 1), source=source)
    clean_raw(con)
    skills = {r[0] for r in con.execute("SELECT skill FROM skills").fetchall()}
    assert "Terraform" in skills
    row = con.execute("SELECT role, city, company, salary_min, salary_max FROM jobs").fetchone()
    assert row == ("data_engineer", "Cairo", "Acme", 20000, 30000)
    con.close()
