import statistics
from collections import Counter
from datetime import date, timedelta

import pytest

from chatbot import ask
from chatbot.queries import MAX_LIMIT, run
from chatbot.text import to_text
from clean.cleaner import clean_raw
from collect.collector import collect_range
from db.schema import SEED_ROLES, connect, create_tables
from mock_source.generator import generate_jobs, generate_truth

START = date(2026, 10, 1)
DAYS = 30
LAST = START + timedelta(days=DAYS - 1)


@pytest.fixture(scope="module")
def con():
    c = connect(":memory:")
    create_tables(c)
    collect_range(c, START, LAST)
    clean_raw(c)
    yield c
    c.close()


@pytest.fixture(scope="module")
def truth():
    answer_key = {}
    for i in range(DAYS):
        answer_key.update(generate_truth(START + timedelta(days=i)))
    return list(answer_key.items())


@pytest.fixture
def empty():
    c = connect(":memory:")
    create_tables(c)
    yield c
    c.close()


def result(con, name, **params):
    answer = run(con, name, params)
    assert answer["ok"], answer
    return answer["result"]


def ranked(counter, limit):
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]


# ---- the numbers match the generator's answer key -------------------------

def test_count_postings_matches_the_answer_key(con, truth):
    assert result(con, "count_postings")["total"] == len(truth)
    for role in SEED_ROLES:
        expected = sum(1 for _, t in truth if t["role"] == role)
        assert result(con, "count_postings", role=role)["total"] == expected, role


def test_count_postings_by_city_matches_the_answer_key(con, truth):
    for city in ("Cairo", "Giza", "Alexandria", "Remote"):
        expected = sum(1 for _, t in truth if t["role"] == "data_analyst" and t["city"] == city)
        got = result(con, "count_postings", role="data_analyst", city=city)["total"]
        assert got == expected, city


def test_salary_matches_the_answer_key(con, truth):
    for role in ("data_engineer", "data_analyst", "ml_engineer"):
        listed = [t for _, t in truth if t["role"] == role and t["salary_visible"]]
        mids = [(t["salary_min"] + t["salary_max"]) / 2 for t in listed]
        got = result(con, "salary_for_role", role=role)
        assert got["postings"] == sum(1 for _, t in truth if t["role"] == role)
        assert got["with_salary"] == len(listed)
        assert got["typical"] == round(statistics.median(mids))
        assert got["lowest"] == min(t["salary_min"] for t in listed)
        assert got["highest"] == max(t["salary_max"] for t in listed)


def test_salary_in_one_city_matches_the_answer_key(con, truth):
    listed = [t for _, t in truth
              if t["role"] == "data_engineer" and t["city"] == "Cairo" and t["salary_visible"]]
    got = result(con, "salary_for_role", role="data_engineer", city="Cairo")
    assert got["with_salary"] == len(listed)
    mids = [(t["salary_min"] + t["salary_max"]) / 2 for t in listed]
    assert got["typical"] == round(statistics.median(mids))


def test_top_skills_matches_the_answer_key(con, truth):
    with_skills = [t for _, t in truth if t["role"] == "data_engineer"
                   and t["skills_visible"] and t["skills"]]
    counts = Counter(skill for t in with_skills for skill in t["skills"])
    got = result(con, "top_skills", role="data_engineer", limit=6)
    assert got["postings_with_skills"] == len(with_skills)
    assert [(s["skill"], s["postings"]) for s in got["skills"]] == ranked(counts, 6)
    first = got["skills"][0]
    assert first["share"] == round(first["postings"] / len(with_skills), 2)


def test_top_skills_for_all_roles(con, truth):
    with_skills = [t for _, t in truth if t["skills_visible"] and t["skills"]]
    counts = Counter(skill for t in with_skills for skill in t["skills"])
    got = result(con, "top_skills", limit=5)
    assert [(s["skill"], s["postings"]) for s in got["skills"]] == ranked(counts, 5)


def test_top_companies_matches_the_answer_key(con, truth):
    counts = Counter(t["company"] for _, t in truth if t["company"])
    got = result(con, "top_companies", limit=5)
    assert [(c["company"], c["postings"]) for c in got["companies"]] == ranked(counts, 5)


def test_top_companies_for_one_role(con, truth):
    counts = Counter(t["company"] for _, t in truth if t["company"] and t["role"] == "bi_developer")
    got = result(con, "top_companies", role="bi_developer", limit=3)
    assert [(c["company"], c["postings"]) for c in got["companies"]] == ranked(counts, 3)


def test_jobs_by_city_matches_the_answer_key(con, truth):
    counts = Counter(t["city"] for _, t in truth if t["city"])
    got = result(con, "jobs_by_city")
    assert [(c["city"], c["postings"]) for c in got["cities"]] == ranked(counts, 10)
    assert got["no_city"] == sum(1 for _, t in truth if not t["city"])


def test_new_postings_are_the_ones_first_seen_in_the_last_days(con, truth):
    first_seen = {}
    for i in range(DAYS):
        day = START + timedelta(days=i)
        for job in generate_jobs(day):
            first_seen.setdefault(job["source_job_id"], day)
    role_of = dict(truth)
    cutoff = max(first_seen.values()) - timedelta(days=2)
    expected = {j for j, d in first_seen.items() if d > cutoff and role_of[j]["role"] == "data_engineer"}

    got = result(con, "new_postings", role="data_engineer", days=2, limit=MAX_LIMIT)
    assert got["total"] == len(expected)
    assert expected >= {p["job_id"] for p in got["postings"]}
    if got["total"] <= MAX_LIMIT:
        assert {p["job_id"] for p in got["postings"]} == expected
    seen_dates = [p["first_seen_date"] for p in got["postings"]]
    assert seen_dates == sorted(seen_dates, reverse=True)


def test_new_postings_default_is_data_engineer(con):
    got = result(con, "new_postings")
    assert got["role"] == "data_engineer"
    assert got["days"] == 7


# ---- empty and thin data --------------------------------------------------

def test_every_answer_survives_an_empty_database(empty):
    assert result(empty, "new_postings")["total"] == 0
    assert result(empty, "salary_for_role", role="data_engineer")["typical"] is None
    assert result(empty, "top_skills")["skills"] == []
    assert result(empty, "top_companies")["companies"] == []
    assert result(empty, "jobs_by_city")["cities"] == []
    assert result(empty, "count_postings")["total"] == 0
    assert result(empty, "top_paying")["groups"] == []


def test_salary_says_so_when_no_posting_lists_one(empty):
    empty.execute("INSERT INTO jobs (job_id, title, role, posted_date, first_seen_date) "
                  "VALUES ('a', 'Data Engineer', 'data_engineer', '2026-10-01', '2026-10-01')")
    got = result(empty, "salary_for_role", role="data_engineer")
    assert (got["postings"], got["with_salary"], got["typical"]) == (1, 0, None)
    assert "No salary data" in to_text(run(empty, "salary_for_role", {"role": "data_engineer"}))


def test_a_role_with_no_postings_gives_a_clear_message(empty):
    assert "No data engineer postings found" in to_text(
        run(empty, "salary_for_role", {"role": "data_engineer"}))


# ---- bad input never reaches SQL ------------------------------------------

def test_role_names_are_forgiving_about_spaces_and_case(con):
    assert result(con, "count_postings", role="Data Engineer")["role"] == "data_engineer"


def test_unknown_role_is_refused(con):
    answer = run(con, "count_postings", {"role": "chef"})
    assert answer["ok"] is False
    assert "data_engineer" in answer["message"]


def test_unknown_city_is_refused(con):
    answer = run(con, "count_postings", {"city": "Paris"})
    assert answer["ok"] is False
    assert "Cairo" in answer["message"]


def test_city_is_matched_without_caring_about_case(con):
    assert result(con, "count_postings", city="cairo")["city"] == "Cairo"


def test_sql_in_a_value_is_just_a_refused_value(con):
    for value in ("x'; DROP TABLE jobs; --", "data_engineer' OR '1'='1"):
        assert run(con, "count_postings", {"role": value})["ok"] is False
        assert run(con, "count_postings", {"city": value})["ok"] is False
    assert con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] > 0


def test_limit_is_kept_between_1_and_the_maximum(con):
    assert len(result(con, "top_skills", limit=999)["skills"]) <= MAX_LIMIT
    assert len(result(con, "top_skills", limit=0)["skills"]) == 1
    assert run(con, "top_skills", {"limit": "many"})["ok"] is False


def test_unknown_answer_unknown_parameter_and_missing_parameter(con):
    assert run(con, "delete_everything")["ok"] is False
    assert "takes" in run(con, "top_skills", {"colour": "red"})["message"]
    assert "needs: skill" in run(con, "skills_with")["message"]


def test_run_never_raises_even_with_odd_values(con):
    assert run(con, "new_postings", {"role": "chef"})["ok"] is False
    assert run(con, "new_postings", {"days": "x"})["ok"] is False


# ---- the plain-English text -----------------------------------------------

def test_text_for_a_salary_answer_shows_the_basis(con):
    answer = run(con, "salary_for_role", {"role": "data_engineer"})
    got = answer["result"]
    text = to_text(answer)
    assert f"{got['typical']:,}" in text
    assert f"Based on {got['with_salary']} of {got['postings']} postings" in text


def test_text_for_every_answer_is_non_empty(con):
    for name in ("new_postings", "top_skills", "top_companies", "jobs_by_city", "count_postings"):
        assert to_text(run(con, name, {})).strip()
    assert to_text(run(con, "salary_for_role", {"role": "data_analyst"})).strip()


def test_text_passes_a_refusal_through(con):
    assert "I do not know the role" in to_text(run(con, "top_skills", {"role": "chef"}))


def test_text_for_all_roles_reads_naturally(con):
    assert "most postings:" in to_text(run(con, "top_companies", {}))
    assert to_text(run(con, "jobs_by_city", {})).startswith("Postings by city:")


# ---- the command-line helper ----------------------------------------------

def test_ask_lists_the_answers_with_no_arguments(capsys):
    assert ask.main([]) == 0
    assert "top_skills" in capsys.readouterr().out


def test_ask_needs_a_database(tmp_path, capsys):
    assert ask.main(["count_postings"], db_path=tmp_path / "missing.duckdb") == 1
    assert "run_pipeline.py" in capsys.readouterr().out


def test_ask_answers_from_a_database_file(tmp_path, capsys):
    path = tmp_path / "jobs.duckdb"
    c = connect(path)
    create_tables(c)
    collect_range(c, START, START + timedelta(days=2))
    clean_raw(c)
    total = c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    c.close()

    assert ask.main(["count_postings"], db_path=path) == 0
    assert f"{total} postings for all roles." in capsys.readouterr().out
    assert ask.main(["count_postings", "role=chef"], db_path=path) == 0
    assert "I do not know the role" in capsys.readouterr().out


# ---- filters and the two newer answers, checked against the answer key ------

def test_count_with_a_skill_filter_matches_the_answer_key(con, truth):
    expected = sum(1 for _, t in truth if t["role"] == "data_analyst"
                   and t["skills_visible"] and "SQL" in t["skills"])
    assert result(con, "count_postings", role="data_analyst", skill="sql")["total"] == expected


def test_count_with_a_minimum_salary_matches_the_answer_key(con, truth):
    expected = sum(1 for _, t in truth if t["salary_visible"]
                   and (t["salary_min"] + t["salary_max"]) / 2 >= 30000)
    got = result(con, "count_postings", min_salary=30000)
    assert got["total"] == expected and got["min_salary"] == 30000


def test_all_filters_together(con, truth):
    expected = sum(1 for _, t in truth if t["role"] == "data_engineer" and t["city"] == "Cairo"
                   and t["skills_visible"] and "Python" in t["skills"]
                   and t["salary_visible"] and (t["salary_min"] + t["salary_max"]) / 2 >= 25000)
    got = result(con, "count_postings", role="data_engineer", city="Cairo", skill="Python",
                 min_salary=25000)
    assert got["total"] == expected


def test_salary_for_a_skill_without_a_role(con, truth):
    listed = [t for _, t in truth if t["skills_visible"] and "Python" in t["skills"]
              and t["salary_visible"]]
    mids = [(t["salary_min"] + t["salary_max"]) / 2 for t in listed]
    got = result(con, "salary_for_role", skill="Python")
    assert got["role"] is None
    assert got["with_salary"] == len(listed)
    assert got["typical"] == round(statistics.median(mids))


def test_top_companies_and_cities_with_a_skill(con, truth):
    chosen = [t for _, t in truth if t["skills_visible"] and "Airflow" in t["skills"]]
    companies = Counter(t["company"] for t in chosen if t["company"])
    got = result(con, "top_companies", skill="Airflow", limit=3)
    assert [(c["company"], c["postings"]) for c in got["companies"]] == ranked(companies, 3)
    cities = Counter(t["city"] for t in chosen if t["city"])
    got = result(con, "jobs_by_city", skill="Airflow")
    assert [(c["city"], c["postings"]) for c in got["cities"]] == ranked(cities, 10)


def test_top_skills_in_one_city(con, truth):
    chosen = [t for _, t in truth if t["role"] == "data_analyst" and t["city"] == "Giza"
              and t["skills_visible"] and t["skills"]]
    counts = Counter(skill for t in chosen for skill in t["skills"])
    got = result(con, "top_skills", role="data_analyst", city="Giza", limit=4)
    assert got["postings_with_skills"] == len(chosen)
    assert [(s["skill"], s["postings"]) for s in got["skills"]] == ranked(counts, 4)


def test_skills_with_matches_the_answer_key(con, truth):
    chosen = [t for _, t in truth if t["skills_visible"] and "Airflow" in t["skills"]]
    counts = Counter(s for t in chosen for s in t["skills"] if s != "Airflow")
    got = result(con, "skills_with", skill="airflow", limit=5)
    assert got["skill"] == "Airflow"
    assert got["postings_with_skill"] == len(chosen)
    assert [(s["skill"], s["postings"]) for s in got["skills"]] == ranked(counts, 5)
    assert all(s["skill"] != "Airflow" for s in got["skills"])
    assert got["skills"][0]["share"] == round(got["skills"][0]["postings"] / len(chosen), 2)


def test_skills_with_inside_one_role(con, truth):
    chosen = [t for _, t in truth if t["role"] == "data_engineer"
              and t["skills_visible"] and "Spark" in t["skills"]]
    counts = Counter(s for t in chosen for s in t["skills"] if s != "Spark")
    got = result(con, "skills_with", skill="Spark", role="data_engineer", limit=3)
    assert [(s["skill"], s["postings"]) for s in got["skills"]] == ranked(counts, 3)


def _typical_by(truth, key, keep=lambda t: True):
    groups = {}
    for _, t in truth:
        if t["salary_visible"] and keep(t):
            for value in key(t):
                groups.setdefault(value, []).append((t["salary_min"] + t["salary_max"]) / 2)
    return {g: (round(statistics.median(m)), len(m)) for g, m in groups.items() if len(m) >= 3}


@pytest.mark.parametrize("group_by,key", [
    ("role", lambda t: [t["role"]]),
    ("city", lambda t: [t["city"]] if t["city"] else []),
    ("company", lambda t: [t["company"]] if t["company"] else []),
    ("skill", lambda t: t["skills"] if t["skills_visible"] else []),
])
def test_top_paying_matches_the_answer_key(con, truth, group_by, key):
    expected = _typical_by(truth, key)
    order = sorted(expected.items(), key=lambda kv: (-kv[1][0], kv[0]))[:5]
    got = result(con, "top_paying", group_by=group_by)
    assert [(g["group"], g["typical"], g["with_salary"]) for g in got["groups"]] == [
        (name, typical, n) for name, (typical, n) in order]


def test_top_paying_lowest_first_and_with_filters(con, truth):
    expected = _typical_by(truth, lambda t: [t["city"]] if t["city"] else [],
                           keep=lambda t: t["role"] == "data_engineer")
    order = sorted(expected.items(), key=lambda kv: (kv[1][0], kv[0]))[:3]
    got = result(con, "top_paying", group_by="city", role="data_engineer", order="lowest", limit=3)
    assert [(g["group"], g["typical"]) for g in got["groups"]] == [(n, v[0]) for n, v in order]


def test_top_paying_skips_groups_with_too_few_salaries(empty):
    for i in range(2):
        empty.execute("INSERT INTO jobs (job_id, title, role, city, salary_min, salary_max, "
                      "posted_date, first_seen_date) VALUES (?, 'x', 'data_engineer', 'Cairo', "
                      "90000, 100000, '2026-10-01', '2026-10-01')", [f"j{i}"])
    assert result(empty, "top_paying", group_by="city")["groups"] == []
    assert "at least 3" in to_text(run(empty, "top_paying", {"group_by": "city"}))


def test_new_postings_for_all_roles_and_a_skill_filter(con):
    everyone = result(con, "new_postings", role=None, days=2, limit=MAX_LIMIT)
    engineers = result(con, "new_postings", role="data_engineer", days=2, limit=MAX_LIMIT)
    assert everyone["total"] > engineers["total"] > 0
    with_sql = result(con, "new_postings", role=None, skill="SQL", days=2, limit=MAX_LIMIT)
    assert 0 < with_sql["total"] < everyone["total"]


def test_new_filters_refuse_unknown_values(con):
    assert run(con, "count_postings", {"skill": "cobol"})["ok"] is False
    assert "Python" in run(con, "count_postings", {"skill": "cobol"})["message"]
    assert run(con, "count_postings", {"min_salary": "lots"})["ok"] is False
    assert run(con, "count_postings", {"min_salary": -5})["ok"] is False
    assert run(con, "top_paying", {"group_by": "salary; DROP TABLE jobs"})["ok"] is False
    assert run(con, "top_paying", {"order": "sideways"})["ok"] is False
    assert run(con, "skills_with", {"skill": "x'; DROP TABLE jobs; --"})["ok"] is False
    assert con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] > 0


def test_text_for_the_new_answers(con):
    text = to_text(run(con, "top_paying", {"group_by": "city", "role": "data_engineer"}))
    assert text.startswith("Highest typical monthly salary by city for data engineer")
    text = to_text(run(con, "skills_with", {"skill": "Airflow"}))
    assert text.startswith("Skills that appear with Airflow in postings")
    text = to_text(run(con, "count_postings", {"skill": "SQL", "min_salary": 30000}))
    assert "that list SQL paying at least 30,000 EGP/month" in text
    text = to_text(run(con, "salary_for_role", {"skill": "Python"}))
    assert text.startswith("all roles that list Python: typical")


def test_jobs_by_role_matches_the_answer_key(con, truth):
    counts = Counter(t["role"] for _, t in truth if t["role"])
    got = result(con, "jobs_by_role")
    assert [(r["role"], r["postings"]) for r in got["roles"]] == ranked(counts, 10)


def test_jobs_by_role_in_one_city_adds_up_to_that_city(con, truth):
    got = result(con, "jobs_by_role", city="Cairo")
    assert sum(r["postings"] for r in got["roles"]) <= result(con, "count_postings", city="Cairo")["total"]
    assert to_text(run(con, "jobs_by_role", {"city": "Cairo"})).startswith("Postings by role in Cairo:")


def test_jobs_by_role_survives_an_empty_database(empty):
    assert result(empty, "jobs_by_role")["roles"] == []
    assert "No postings found" in to_text(run(empty, "jobs_by_role", {}))
