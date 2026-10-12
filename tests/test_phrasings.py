"""135 natural ways to ask the nine answers (casual words, synonyms, typos). See tests/data/phrasings.json."""
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from phrasing_report import evaluate  # noqa: E402

from chatbot.router import RuleRouter, closest_word, edit_distance
from chatbot.service import Service

# Left failing on purpose: a two-letter typo is below the length rule that keeps the repair safe.
KNOWN_FAILS = {"hw many jobs are there"}


@pytest.fixture(scope="module")
def router():
    con = duckdb.connect("data/sample.duckdb", read_only=True)
    yield RuleRouter(con)
    con.close()


def test_natural_phrasings_are_understood(router):
    results = evaluate(router)
    failed = {question for ok, question, *_ in results if not ok}
    assert failed <= KNOWN_FAILS, sorted(failed - KNOWN_FAILS)
    assert sum(ok for ok, *_ in results) / len(results) >= 0.99


def test_top_earing_jobs_is_a_ranking_by_pay(router):
    choice = router("who are the top earing jobs")
    assert choice["function"] == "top_paying" and choice["params"]["group_by"] == "role"


def test_edit_distance():
    assert edit_distance("earing", "earning") == 1 and edit_distance("kitten", "sitting") == 3


@pytest.mark.parametrize("word, expected", [
    ("earing", "earning"), ("usefull", "useful"), ("salry", "salary"), ("pythn", "python"),
    ("skils", "skills"), ("comapnies", "companies"),
    ("cobol", None), ("dubai", None), ("rust", None), ("xyz", None), ("hw", None)])
def test_typo_rule_repairs_close_words_and_leaves_others(word, expected):
    vocabulary = ["earning", "useful", "salary", "python", "skills", "companies", "data", "alexandria", "cairo"]
    assert closest_word(word, vocabulary) == expected


def test_a_refusal_offers_one_or_two_questions_to_try():
    service = Service(db_path="data/sample.duckdb")
    reply = service.ask("whos the boss of data")
    assert not reply["ok"] and 1 <= len(reply["did_you_mean"]) <= 2
    for question in reply["did_you_mean"]:
        assert service.ask(question)["ok"], question
    assert service.ask("what does a data analyst earn")["did_you_mean"] == []
    service.close()
