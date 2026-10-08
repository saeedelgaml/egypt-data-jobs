"""Tests for the web page (app.py) and its renderer (ui/render.py)."""
import re
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import make_sample_db
from chatbot.service import EXAMPLES
from db.schema import connect
from ui import render

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app.py")


@pytest.fixture(scope="module")
def db_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("app") / "sample.duckdb"
    make_sample_db.build(path, days=10)
    return path


@pytest.fixture
def app(db_path, monkeypatch):
    monkeypatch.setenv("JOBS_DB", str(db_path))
    st.cache_resource.clear()
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception
    yield at
    st.cache_resource.clear()


def submit(at, question):
    at.text_input(key="box").set_value(question)
    next(b for b in at.button if b.label == "Ask").click()
    at.run()
    assert not at.exception
    return at


def page_text(at):
    return "\n".join(m.value for m in at.markdown)


def test_the_page_loads_with_a_hero_the_chips_and_the_synthetic_notice(app):
    text = page_text(app)
    assert "Ask anything about data jobs in Egypt" in text
    assert "synthetic" in text
    labels = [b.label for b in app.button]
    for group in EXAMPLES.values():
        for question in group:
            assert question in labels


@pytest.mark.parametrize("question", [g[0] for g in EXAMPLES.values()])
def test_clicking_an_example_shows_an_answer(app, question):
    next(b for b in app.button if b.label == question).click()
    app.run()
    assert not app.exception
    text = page_text(app)
    assert "Read as" in text and 'class="answer"' in text
    assert any(b.label for b in app.button if b.label.endswith("?"))      # follow-up chips are offered


def test_a_question_with_no_answer_teaches_what_to_ask(app):
    submit(app, "what does a chef earn")
    text = page_text(app)
    assert "That one I can't answer" in text and "What works" in text
    assert "Name a role." in text
    assert any(b.label in {g[0] for g in EXAMPLES.values()} for b in app.button)


def test_an_empty_submit_asks_for_a_question(app):
    submit(app, "   ")
    assert any("Type a question" in i.value for i in app.info)


def test_a_visitor_who_asks_too_much_is_slowed_down(app):
    for _ in range(11):                       # the limit is 10 a minute
        submit(app, "how many postings are there")
    assert any("lot of questions" in w.value for w in app.warning)
    assert next(b for b in app.button if b.label == "Ask").disabled


def test_each_visitor_gets_a_private_random_session_id(db_path, monkeypatch):
    monkeypatch.setenv("JOBS_DB", str(db_path))
    st.cache_resource.clear()
    a, b = AppTest.from_file(APP).run(), AppTest.from_file(APP).run()
    assert re.fullmatch(r"[0-9a-f]{32}", a.session_state["sid"]) and a.session_state["sid"] != b.session_state["sid"]


def test_html_in_the_database_or_the_question_never_reaches_the_page_as_markup(tmp_path, monkeypatch):
    path = tmp_path / "evil.duckdb"
    make_sample_db.build(path, days=5)
    con = connect(path)
    con.execute("UPDATE jobs SET company = '<img src=x onerror=alert(1)>Evil&Co' WHERE company IN "
                "(SELECT company FROM jobs GROUP BY company ORDER BY COUNT(*) DESC LIMIT 1)")
    con.execute("UPDATE jobs SET title = '<script>alert(2)</script>' WHERE rowid % 2 = 0")
    con.close()
    monkeypatch.setenv("JOBS_DB", str(path))
    st.cache_resource.clear()
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    for question in ["top 5 companies hiring", "new data engineer jobs", "<img src=x onerror=alert(3)> salary"]:
        submit(at, question)
        everything = page_text(at)
        assert "<img" not in everything and "<script" not in everything.replace("<style>", "")
    submit(at, "top 5 companies hiring")
    assert "&lt;img src=x onerror=alert(1)&gt;Evil&amp;Co" in page_text(at)
    st.cache_resource.clear()


def test_the_renderer_escapes_every_dynamic_value():
    evil = '<b onclick="x">&"\''
    reply = {"ok": True, "function": "top_companies", "params": {"role": None, "city": evil, "skill": evil},
             "understood": evil, "notes": [evil], "text": evil,
             "data": {"companies": [{"company": evil, "postings": 3}]}}
    html = render.answer_html(reply)
    assert "<b " not in html and html.count("&lt;b onclick") >= 4
    facts = render.facts_html({"postings": evil, "first_posted": evil, "last_posted": evil, "last_run": evil,
                               "synthetic_note": evil, "limits_note": evil})
    assert "<b onclick" not in facts


def test_numbers_cannot_carry_markup_into_a_style_attribute():
    html = render.bars([("a", '"><script>', "x")])
    assert "<script" not in html and "--w:2.0%" in html
    assert render.num("12px;background:red") == 0 and render.num(True) == 0 and render.money(None) == "0"


def test_the_page_never_touches_the_database_or_secrets():
    for name in ("app.py", "ui/render.py"):
        source = (ROOT / name).read_text(encoding="utf-8")
        for banned in ("import duckdb", "chatbot.queries", "chatbot.router", "anthropic", "os.environ",
                       "dotenv", "requests", "urllib", "subprocess", "eval(", "exec("):
            assert banned not in source, (name, banned)


def test_unsafe_html_goes_through_one_door_and_only_for_our_own_markup():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    uses = [line.strip() for line in source.splitlines() if "unsafe_allow_html" in line]
    allowed = ('st.markdown(markup, unsafe_allow_html=True)',
               'st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)',
               'unsafe_allow_html=True)')
    assert all(any(u.endswith(a) or u == a for a in allowed) for u in uses), uses
    assert "<style>{CSS}" in source and (ROOT / "ui" / "style.css").exists()


def test_the_stylesheet_works_without_motion_and_keeps_keyboard_focus_visible():
    css = (ROOT / "ui" / "style.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in css and "focus-visible" in css
