import duckdb
import pytest

from db.schema import SEED_ROLES, add_skill, connect, create_tables, table_names


@pytest.fixture
def con():
    c = connect(":memory:")
    create_tables(c)
    yield c
    c.close()


def add_job(con, job_id, role, skills):
    con.execute("INSERT INTO jobs (job_id, role) VALUES (?, ?)", [job_id, role])
    for skill in skills:
        add_skill(con, skill)
        con.execute("INSERT INTO job_skills VALUES (?, ?)", [job_id, skill])


def top_skills(con, role):
    return con.execute(
        """
        SELECT js.skill, COUNT(*) AS n
        FROM job_skills js
        JOIN jobs j ON j.job_id = js.job_id
        WHERE j.role = ?
        GROUP BY js.skill
        ORDER BY n DESC, js.skill
        """,
        [role],
    ).fetchall()


def test_all_tables_exist(con):
    assert table_names(con) == [
        "job_skills", "jobs", "pipeline_runs", "raw_jobs", "roles", "skills",
    ]


def test_roles_are_seeded_once(con):
    create_tables(con)
    roles = [r[0] for r in con.execute("SELECT role FROM roles").fetchall()]
    assert sorted(roles) == sorted(SEED_ROLES)


def test_raw_jobs_keeps_duplicates(con):
    row = ("w1", "Data Engineer", "NileTech", "Cairo", "15k-20k", "SQL", "2026-10-01", "2026-10-02")
    for _ in range(2):
        con.execute("INSERT INTO raw_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?)", row)
    assert con.execute("SELECT COUNT(*) FROM raw_jobs").fetchone()[0] == 2


def test_jobs_rejects_duplicate_job_id(con):
    add_job(con, "w1", "data_engineer", [])
    with pytest.raises(duckdb.ConstraintException):
        add_job(con, "w1", "data_engineer", [])


def test_jobs_rejects_unknown_role(con):
    with pytest.raises(duckdb.ConstraintException):
        con.execute("INSERT INTO jobs (job_id, role) VALUES ('w1', 'wizard')")


def test_job_skills_rejects_unknown_skill(con):
    add_job(con, "w1", "data_engineer", [])
    with pytest.raises(duckdb.ConstraintException):
        con.execute("INSERT INTO job_skills VALUES ('w1', 'Not Added Yet')")


def test_add_skill_twice_keeps_one_row(con):
    add_skill(con, "Python")
    add_skill(con, "Python")
    assert con.execute("SELECT COUNT(*) FROM skills").fetchone()[0] == 1


def test_job_skills_rejects_duplicate_pair(con):
    add_job(con, "w1", "data_engineer", ["SQL"])
    with pytest.raises(duckdb.ConstraintException):
        con.execute("INSERT INTO job_skills VALUES ('w1', 'SQL')")


def test_salary_currency_defaults_to_egp(con):
    con.execute("INSERT INTO jobs (job_id) VALUES ('w1')")
    assert con.execute("SELECT salary_currency FROM jobs").fetchone()[0] == "EGP"


def test_new_skill_shows_up_for_its_role(con):
    add_job(con, "w1", "data_engineer", ["Python", "SQL"])
    add_job(con, "w2", "data_engineer", ["Python", "Airflow"])
    add_job(con, "w3", "data_analyst", ["Excel"])
    assert top_skills(con, "data_engineer")[0] == ("Python", 2)
    assert ("dbt", 1) not in top_skills(con, "data_engineer")

    add_job(con, "w4", "data_engineer", ["dbt"])
    assert ("dbt", 1) in top_skills(con, "data_engineer")
    assert ("dbt", 1) not in top_skills(con, "data_analyst")
