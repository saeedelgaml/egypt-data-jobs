"""Every role in config.py can be generated, cleaned, asked about and answered."""
from datetime import date, timedelta

import duckdb
import pytest

from chatbot.queries import run
from chatbot.router import RuleRouter
from clean.rules import clean_role, clean_skills, clean_title
from config import (PATTERN_ORDER, PLURAL, ROLE_LABEL, ROLE_PHRASES, ROLES, SALARY_BANDS,
                    SEED_ROLES, SENIORITY_BY_ROLE, SKILL_VARIANTS)
from mock_source.generator import SENIORITY_FORMATS, generate_truth

DATA_ROLES = [r for r in SEED_ROLES if r != "other"]

# Titles the user asked for, written the way a job board might.
EXPECTED_ROLES = {
    "Data Analyst": "data_analyst", "BI Developer": "bi_developer", "Business Analyst (Data)": "business_analyst",
    "Data Engineer": "data_engineer", "Analytics Engineer": "analytics_engineer",
    "Data Scientist": "data_scientist", "ML Engineer": "ml_engineer", "AI Engineer": "ai_engineer",
    "MLOps Engineer": "mlops_engineer", "NLP Engineer": "nlp_engineer",
    "Computer Vision Engineer": "computer_vision_engineer", "Data Architect": "data_architect",
    "Big Data Engineer": "big_data_engineer", "GenAI Engineer": "genai_engineer", "LLM Engineer": "genai_engineer",
}


@pytest.fixture(scope="module")
def router():
    con = duckdb.connect("data/sample.duckdb", read_only=True)
    yield RuleRouter(con), con
    con.close()


def test_the_requested_roles_exist():
    assert set(EXPECTED_ROLES.values()) <= set(SEED_ROLES)
    assert len(DATA_ROLES) >= 14


def test_config_is_consistent():
    assert abs(sum(r["weight"] for r in ROLES.values()) - 1) < 1e-9
    assert sorted(PATTERN_ORDER) == sorted(DATA_ROLES)
    assert set(PLURAL) == set(DATA_ROLES)
    for key, role in ROLES.items():
        assert set(role["seniority"]) <= set(role["salary"]), key
        assert all(low < high for low, high in role["salary"].values()), key
        assert set(role["skills"]) <= set(SKILL_VARIANTS), f"{key} uses a skill the cleaner does not know"
    seen = {}
    for key, phrases in ROLE_PHRASES.items():
        for phrase in phrases:
            assert seen.setdefault(phrase, key) == key, f"{phrase!r} belongs to two roles"


def test_seniors_earn_more_than_juniors_in_every_band():
    for role, bands in SALARY_BANDS.items():
        levels = [bands[k] for k in ("junior", "mid", "senior") if k in bands]
        assert levels == sorted(levels), role


@pytest.mark.parametrize("title, role", sorted(EXPECTED_ROLES.items()))
def test_clean_role_knows_each_requested_title(title, role):
    assert clean_role(title) == role
    assert clean_role(title.lower()) == role
    assert clean_role(title.upper()) == role
    assert clean_role(f"Senior {title}") == role


def test_every_title_the_generator_writes_maps_back_to_its_role():
    for role, spec in ROLES.items():
        for title in spec["titles"]:
            for level in spec["seniority"]:
                for form in SENIORITY_FORMATS[level]:
                    text = form.format(r=title)
                    assert clean_role(text) == role, text
                    assert clean_role(text.lower()) == role, text
                    assert clean_role(clean_title(text.upper())) == role, text


def test_the_generator_makes_every_role_with_its_own_skills():
    start, seen = date(2026, 1, 1), {}
    for i in range(120):
        for truth in generate_truth(start + timedelta(days=i)).values():
            seen.setdefault(truth["role"], []).append(truth)
    assert set(seen) == set(SEED_ROLES)
    for role, postings in seen.items():
        assert {p["seniority"] for p in postings} <= set(ROLES[role]["seniority"])
        assert all(set(p["skills"]) <= set(ROLES[role]["skills"]) for p in postings)
    architects = seen["data_architect"]
    assert not any(p["seniority"] == "junior" for p in architects)


def test_acronyms_in_new_titles_are_fixed():
    assert clean_title("nlp engineer") == "NLP Engineer"
    assert clean_title("MLOPS ENGINEER") == "MLOps Engineer"
    assert clean_title("genai engineer") == "GenAI Engineer"
    assert clean_title("llm engineer") == "LLM Engineer"


def test_a_slash_inside_a_skill_name_does_not_split_it():
    assert clean_skills("Docker, CI/CD, Kubernetes") == ["Docker", "CI/CD", "Kubernetes"]
    assert clean_skills("Docker / Kubernetes") == ["Docker", "Kubernetes"]
    assert clean_skills("cicd; k8s; HuggingFace") == ["CI/CD", "Kubernetes", "Hugging Face"]


@pytest.mark.parametrize("role", DATA_ROLES)
def test_every_role_can_be_asked_about(router, role):
    route, con = router
    for question in (f"what does a {ROLE_LABEL[role]} earn", f"who is hiring {PLURAL[role]}",
                     f"what skills do {PLURAL[role]} need"):
        choice = route(question)
        assert choice["function"] is not None, question
        assert choice["params"].get("role") == role, question
        answer = run(con, choice["function"], choice["params"])
        assert answer["ok"], question


ALIASES = [
    ("what does an AI eng earn", "ai_engineer"), ("ai engineer salary", "ai_engineer"),
    ("ML eng salary", "ml_engineer"), ("what do llm jobs pay", "genai_engineer"),
    ("LLM engineer salary", "genai_engineer"), ("genai jobs in cairo", "genai_engineer"),
    ("generative ai engineer salary", "genai_engineer"), ("mlops salary", "mlops_engineer"),
    ("ml ops engineers pay", "mlops_engineer"), ("nlp jobs in giza", "nlp_engineer"),
    ("natural language processing engineer salary", "nlp_engineer"),
    ("cv engineer salary", "computer_vision_engineer"), ("computer vision jobs", "computer_vision_engineer"),
    ("data architect salary", "data_architect"), ("big data engineer salary", "big_data_engineer"),
    ("big data jobs in alexandria", "big_data_engineer"), ("analytics engineer salary", "analytics_engineer"),
    ("business analyst salary", "business_analyst"), ("bi dev salary", "bi_developer"),
    ("data eng salary", "data_engineer"), ("de salary", "data_engineer"),
]


@pytest.mark.parametrize("question, role", ALIASES)
def test_role_aliases_are_understood(router, question, role):
    choice = router[0](question)
    assert choice["params"].get("role") == role, question


def test_new_skills_are_known_to_the_router(router):
    route, _ = router
    assert route("how many postings list kubernetes")["params"]["skill"] == "Kubernetes"
    assert route("what skills go with langchain")["params"]["skill"] == "LangChain"
    assert route("how many postings list ci/cd")["params"]["skill"] == "CI/CD"
    assert route("how many postings list k8s")["params"]["skill"] == "Kubernetes"


def test_a_skill_that_is_not_in_the_data_is_still_refused(router):
    assert router[0]("how many jobs need cobol")["function"] is None


# ---- field names ("ai engineering"), "most useful skills" and typos ----------------------------
from config import FIELD_NAMES  # noqa: E402


@pytest.mark.parametrize("role, field", [(r, f) for r, names in FIELD_NAMES.items() for f in names])
@pytest.mark.parametrize("template", ["what are the most useful skills for {}", "most important skills for {}",
                                       "best skills needed for {}", "which skills are in demand for {}"])
def test_field_names_are_the_matching_role_and_ask_for_top_skills(router, role, field, template):
    choice = router[0](template.format(field))
    assert choice["function"] == "top_skills" and choice["params"].get("role") == role, (field, choice)


def test_every_role_has_a_field_name():
    assert set(FIELD_NAMES) == set(DATA_ROLES)


@pytest.mark.parametrize("question", [
    "what are the most usefull skills for ai engineering", "most importnat skills for ai engineering",
    "what are the most usefull skils for ai enginering", "most valueable skills for data engineering"])
def test_common_typos_do_not_stop_the_answer(router, question):
    choice = router[0](question)
    assert choice["function"] == "top_skills" and choice["params"]["role"] in ROLES, question


def test_no_word_of_a_role_name_is_a_skill_or_unknown(router):
    route, _ = router
    for words in ("ai", "nlp", "ml", "vision", "architect", "intelligence", "science"):
        hint = route(f"top skills for {words}").get("hint") or ""
        assert "do not recognize" not in hint, words
    assert route("most useful skills for ai engineering")["params"] == {"role": "ai_engineer"}
