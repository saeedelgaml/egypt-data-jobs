"""The 'newest postings' guess only answers jobs questions; everything else can reach the reports."""
import duckdb
import pytest

from chatbot.ai import answer_question
from chatbot.rag_route import RagRoute
from chatbot.router import RuleRouter

HIT = {"source": "eces-wp241", "title": "ECES Working Paper 241", "year": "data Q4 2021 - Q4 2024", "page": 19,
       "page_end": 19, "score": 0.6, "best_score": 0.6,
       "text": "Entry level roles stipulated a minimum requirement of approximately 2 years of prior experience."}


@pytest.fixture(scope="module")
def con():
    con = duckdb.connect("data/sample.duckdb", read_only=True)
    yield con
    con.close()


def covered(reply="Entry roles ask for approximately 2 years of experience [1]."):
    return RagRoute(ask_model=lambda system, user: reply, search=lambda q: [HIT], threshold=0.3)


def nothing(question):
    return None


@pytest.mark.parametrize("question", ["Do fresh graduates need experience?", "How long should a data science resume be?"])
def test_non_job_questions_with_a_role_or_the_word_fresh_reach_the_reports(con, question):
    router = RuleRouter(con)
    assert router(question)["function"] is None, "the router must not guess 'newest postings' here"
    result = answer_question(con, question, router, rag=covered())
    assert result["function"] == "rag" and result["text"].startswith("From the reports")


def test_the_weather_in_cairo_is_refused_with_no_postings(con):
    router = RuleRouter(con)
    assert router("What's the weather in Cairo tomorrow?")["function"] is None
    result = answer_question(con, "What's the weather in Cairo tomorrow?", router, rag=nothing, fallback=nothing)
    assert result["ok"] is False and "postings" not in result["text"].split("I can answer")[0]
    assert result["function"] is None


@pytest.mark.parametrize("question, role, city", [("data engineer cairo", "data_engineer", "Cairo"),
                                                  ("ai engineers in giza", "ai_engineer", "Giza"),
                                                  ("remote data analyst jobs", "data_analyst", "Remote")])
def test_bare_role_and_city_phrases_and_jobs_questions_still_return_postings(con, question, role, city):
    choice = RuleRouter(con)(question)
    assert choice["function"] == "new_postings" and choice["params"]["role"] == role and choice["params"]["city"] == city
    reply = answer_question(con, question, RuleRouter(con), rag=nothing)
    assert reply["ok"] and "new" in reply["text"].lower()


def test_a_long_question_with_an_unknown_word_is_not_a_bare_phrase(con):
    assert RuleRouter(con)("weather cairo")["function"] is None
    assert RuleRouter(con)("cairo data engineer salary tips please now")["function"] is not None  # salary intent


def test_when_the_reports_cover_a_guess_they_win_and_otherwise_the_guess_stands(con):
    router = RuleRouter(con)
    question = "data scientist jobs resume tips"
    assert router(question).get("last_resort") is True
    win = answer_question(con, question, router, rag=covered("Keep it to one page [1]."))
    assert win["function"] == "rag"
    stays = answer_question(con, question, router, rag=nothing)
    assert stays["function"] == "new_postings"
