"""Tests for chatbot.service, the one door the web page uses."""
from datetime import date, timedelta

import pytest

from chatbot import service as service_module
from chatbot.service import EXAMPLES, HOW_TO_ASK, PLURAL, RateLimiter, Service, follow_ups
from clean.cleaner import clean_raw
from collect.collector import collect_range
from db.schema import connect, create_tables

START = date(2026, 10, 1)


@pytest.fixture(scope="module")
def db_file(tmp_path_factory):
    path = tmp_path_factory.mktemp("svc") / "jobs.duckdb"
    c = connect(path)
    create_tables(c)
    collect_range(c, START, START + timedelta(days=29))
    clean_raw(c)
    c.close()
    return path


@pytest.fixture(scope="module")
def svc(db_file):
    s = Service(db_file, limiter=RateLimiter(per_minute=10_000, per_hour=100_000, per_day_total=1_000_000))
    yield s
    s.close()


def all_examples():
    return [q for group in EXAMPLES.values() for q in group] + [t["example"] for t in HOW_TO_ASK]


@pytest.mark.parametrize("question", all_examples())
def test_every_example_and_tip_gets_a_real_answer(svc, question):
    reply = svc.ask(question)
    assert reply["ok"], (question, reply["text"])
    assert reply["understood"] and reply["data"] is not None


def test_every_follow_up_after_every_answer_works(svc):
    checked = 0
    for question in all_examples() + ["salary data scientist", "top skills in cairo", "who hires ml engineers",
                                      "what skills go with sql for bi developers", "postings by city"]:
        reply = svc.ask(question)
        assert reply["follow_ups"], question
        assert len(reply["follow_ups"]) <= 3
        for follow in reply["follow_ups"]:
            assert svc.ask(follow)["ok"], (question, follow)
            checked += 1
    assert checked > 40


def test_follow_ups_cover_every_function_and_never_repeat():
    for function in ("new_postings", "salary_for_role", "top_skills", "skills_with", "top_companies",
                     "jobs_by_city", "jobs_by_role", "count_postings", "top_paying"):
        for params in ({}, {"role": "ml_engineer"}, {"role": "data_analyst", "city": "Giza", "skill": "SQL"}):
            out = follow_ups(function, params)
            assert out and len({q.lower() for q in out}) == len(out)


def test_refusals_come_with_advice_and_working_examples(svc):
    reply = svc.ask("what does a chef earn")
    assert not reply["ok"] and "chef" in reply["text"]
    assert reply["tips"] == HOW_TO_ASK and reply["examples"] == EXAMPLES
    assert reply["hint"]


def test_empty_long_and_odd_questions_are_handled(svc):
    for bad in ["", "   ", None, 42, "x" * 5000, "'; DROP TABLE jobs; --", "\x00\x01", "‮" * 50]:
        reply = svc.ask(bad)
        assert isinstance(reply["text"], str) and reply["text"]
    assert svc.ask("x" * 5000)["ok"] is False
    assert svc.con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] > 0


def test_the_database_is_read_only(svc):
    for sql in ("CREATE TABLE hacked (i INTEGER)", "INSERT INTO roles VALUES ('x')",
                "UPDATE jobs SET company = 'x'", "DROP TABLE pipeline_runs"):
        with pytest.raises(Exception):
            svc.con.execute(sql)


def test_an_internal_error_never_reaches_the_visitor(svc, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("secret path /srv/db")
    monkeypatch.setattr(service_module, "answer_question", boom)
    reply = svc.ask("how many postings are there")
    assert not reply["ok"] and "secret" not in reply["text"] and "RuntimeError" in reply["text"]


def test_facts_describe_the_data_and_say_it_is_synthetic(svc):
    facts = svc.facts()
    assert facts["postings"] > 0 and facts["with_salary"] <= facts["postings"]
    assert facts["last_run"] == START + timedelta(days=29) and facts["last_run_status"]
    assert "synthetic" in facts["synthetic_note"]
    assert "Python" in facts["skills"] and "Cairo" in facts["cities"]
    assert len(facts["roles"]) == len(PLURAL) + 1


def test_suggestions_match_what_was_typed_and_all_work(svc):
    assert svc.suggest("") == [] and svc.suggest(None) == []
    got = svc.suggest("airflow")
    assert got and all("airflow" in q.lower() for q in got) and len(got) <= 6
    for typed in ["sal", "data eng", "cairo", "skills", "who", "top"]:
        for q in svc.suggest(typed, limit=8):
            assert svc.ask(q)["ok"], q
    assert svc.suggest("zzzzqqq") == []
    assert len(svc.suggest("a" * 5000)) <= 6


def test_rate_limit_per_minute_per_hour_and_per_visitor():
    now = [1000.0]
    limiter = RateLimiter(per_minute=3, per_hour=5, per_day_total=100, clock=lambda: now[0])
    assert [limiter.check("a") for _ in range(3)] == [0, 0, 0]
    assert limiter.check("a") > 0                      # fourth in a minute
    assert limiter.check("b") == 0                     # another visitor is unaffected
    now[0] += 61
    assert limiter.check("a") == 0 and limiter.check("a") == 0   # 5 in the hour now
    now[0] += 61
    assert limiter.check("a") > 0                      # hourly cap
    now[0] += 3600
    assert limiter.check("a") == 0


def test_rate_limit_daily_total_and_memory_bound():
    now = [0.0]
    limiter = RateLimiter(per_minute=100, per_hour=100, per_day_total=5, max_sessions=3, clock=lambda: now[0])
    for i in range(5):
        assert limiter.check(f"s{i}") == 0
    assert limiter.check("new") > 0                    # everyone is stopped for the day
    now[0] += 86401
    assert limiter.check("new") == 0
    many = RateLimiter(per_minute=100, per_hour=100, per_day_total=10**6, max_sessions=50, clock=lambda: now[0])
    for i in range(500):
        now[0] += 4000
        many.check(f"v{i}")
    assert len(many._seen) < 100


def test_the_service_blocks_a_visitor_who_asks_too_much(db_file):
    s = Service(db_file, limiter=RateLimiter(per_minute=2, per_hour=50, per_day_total=1000))
    try:
        assert s.ask("how many postings are there", session="x")["ok"]
        assert s.ask("how many postings are there", session="x")["ok"]
        blocked = s.ask("how many postings are there", session="x")
        assert blocked["limited"] and blocked["retry_after"] > 0 and not blocked["ok"]
        assert s.ask("how many postings are there", session="y")["ok"]
    finally:
        s.close()


def test_the_page_can_log_without_the_session_id(db_file, tmp_path):
    log = tmp_path / "web.log"
    s = Service(db_file, log_path=log)
    try:
        s.ask("salary data analyst", session="secret-session-123")
    finally:
        s.close()
    text = log.read_text(encoding="utf-8")
    assert "salary data analyst" in text and "secret-session-123" not in text


def test_default_database_prefers_the_real_one_then_the_sample(tmp_path, monkeypatch):
    monkeypatch.delenv("JOBS_DB", raising=False)
    monkeypatch.setattr(service_module, "DEFAULT_DB_PATH", tmp_path / "jobs.duckdb")
    monkeypatch.setattr(service_module, "SAMPLE_DB_PATH", tmp_path / "sample.duckdb")
    assert service_module.default_db_path() == tmp_path / "sample.duckdb"
    (tmp_path / "jobs.duckdb").write_bytes(b"")
    assert service_module.default_db_path() == tmp_path / "jobs.duckdb"
    monkeypatch.setenv("JOBS_DB", "/somewhere/else.duckdb")
    assert service_module.default_db_path() == "/somewhere/else.duckdb"


def test_the_sample_database_is_built_from_synthetic_data_and_works(tmp_path):
    import make_sample_db
    path = tmp_path / "sample.duckdb"
    assert make_sample_db.build(path, days=5) > 20
    s = Service(path)
    try:
        assert s.ask("what skills go with Airflow?")["ok"]
    finally:
        s.close()
