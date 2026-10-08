import re
from datetime import date, timedelta

from mock_source.generator import (
    CITY_VARIANTS,
    RAW_FIELDS,
    ROLE_SKILL_PROBS,
    ROLE_WEIGHTS,
    generate_jobs,
    generate_truth,
)

START = date(2026, 1, 1)


def days(n):
    return [START + timedelta(days=i) for i in range(n)]


def new_postings(n):
    """(raw, truth) for postings on the day they were first posted."""
    out = []
    for d in days(n):
        truth = generate_truth(d)
        for job in generate_jobs(d):
            if job["posted_date"] == d.isoformat():
                out.append((job, truth[job["source_job_id"]]))
    return out


def test_about_twenty_jobs_a_day():
    counts = [len(generate_jobs(d)) for d in days(30)]
    assert all(15 <= c <= 28 for c in counts)


def test_same_date_gives_same_output():
    assert generate_jobs(date(2026, 3, 5)) == generate_jobs(date(2026, 3, 5))


def test_accepts_a_date_string():
    assert generate_jobs("2026-03-05") == generate_jobs(date(2026, 3, 5))


def test_rows_have_the_raw_fields_only():
    for job in generate_jobs(START):
        assert list(job) == RAW_FIELDS


def test_ids_are_unique_within_a_day():
    ids = [j["source_job_id"] for j in generate_jobs(START)]
    assert len(ids) == len(set(ids))


def test_earlier_postings_come_back_on_later_days():
    today = {j["source_job_id"] for j in generate_jobs(START + timedelta(days=1))}
    yesterday = {j["source_job_id"] for j in generate_jobs(START)}
    assert today & yesterday


def test_data_is_messy():
    jobs = [j for d in days(30) for j in generate_jobs(d)]
    cairo_spellings = {j["city"] for j in jobs if j["city"] in CITY_VARIANTS["Cairo"]}
    assert len(cairo_spellings) >= 5
    assert len({j["title"] for j in jobs}) > 20
    assert any(j["salary_text"] == "Confidential" for j in jobs)
    assert any(j["salary_text"] is None for j in jobs)
    assert any(j["company"] == "Confidential" for j in jobs)


def test_city_text_matches_the_true_city():
    for d in days(10):
        truth = generate_truth(d)
        for job in generate_jobs(d):
            assert job["city"] in CITY_VARIANTS[truth[job["source_job_id"]]["city"]]


def test_salary_text_matches_the_true_salary():
    checked = 0
    for raw, truth in new_postings(20):
        if not truth["salary_visible"]:
            continue
        numbers = [int(n) for n in re.findall(r"\d+", raw["salary_text"].replace(",", ""))]
        assert numbers in (
            [truth["salary_min"], truth["salary_max"]],
            [truth["salary_min"] // 1000, truth["salary_max"] // 1000],
        )
        checked += 1
    assert checked > 50


def test_salary_min_is_below_max_and_seniors_earn_more():
    postings = new_postings(60)
    assert all(t["salary_min"] < t["salary_max"] for _, t in postings)

    def average_min(level):
        values = [t["salary_min"] for _, t in postings
                  if t["role"] == "data_engineer" and t["seniority"] == level]
        return sum(values) / len(values)

    assert average_min("senior") > average_min("junior")


def test_role_shares_are_close_to_the_targets():
    postings = new_postings(200)
    for role, target in ROLE_WEIGHTS.items():
        share = sum(1 for _, t in postings if t["role"] == role) / len(postings)
        assert abs(share - target) < 0.05, role


def test_skill_shares_are_close_to_the_targets():
    postings = [t for _, t in new_postings(200)
                if t["role"] == "data_engineer" and t["skills_visible"]]
    assert len(postings) > 300
    for skill, target in ROLE_SKILL_PROBS["data_engineer"].items():
        share = sum(1 for t in postings if skill in t["skills"]) / len(postings)
        assert abs(share - target) < 0.08, skill
