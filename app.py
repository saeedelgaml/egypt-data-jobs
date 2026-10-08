"""The web page. Run with:  streamlit run app.py

The page talks only to chatbot.service. It never opens the database, never writes SQL and
never sends data anywhere. Everything from a visitor or from the database is escaped in
ui/render.py before it is placed in HTML (see docs/ui-brief.md for the rules).
"""
import random
import time
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st

from chatbot.service import EXAMPLES, HOW_TO_ASK, Service
from ui import render

st.set_page_config(page_title="Egypt data jobs", page_icon="\U0001F4CC", layout="wide")

CSS = (Path(__file__).parent / "ui" / "style.css").read_text(encoding="utf-8")


@st.cache_resource
def get_service():
    return Service()


def show_html(markup):
    """Markup built by ui.render, where every dynamic value is already escaped."""
    st.markdown(markup, unsafe_allow_html=True)


def ask_from_chip(question):
    st.session_state["box"] = question
    st.session_state["run"] = True


def ask_from_form():
    st.session_state["run"] = True


def start():
    if "sid" not in st.session_state:
        st.session_state["sid"] = uuid.uuid4().hex
        st.session_state["placeholder"] = random.choice([q for g in EXAMPLES.values() for q in g])
        st.session_state["box"] = ""
        st.session_state["reply"] = None
        st.session_state["asked"] = ""
        st.session_state["blocked_until"] = 0.0


def run_if_asked(service):
    if not st.session_state.pop("run", False):
        return
    question = st.session_state.get("box", "")
    reply = service.ask(question, session=st.session_state["sid"])
    st.session_state["reply"] = reply
    st.session_state["asked"] = question
    if reply["limited"]:
        st.session_state["blocked_until"] = time.time() + reply["retry_after"]


def hero():
    st.markdown("# Ask anything about data jobs in Egypt")
    st.markdown('<p class="lede">Pay, skills, who is hiring and where. Write it the way you would ask a friend.</p>',
                unsafe_allow_html=True)


def search_box():
    wait = int(st.session_state["blocked_until"] - time.time())
    with st.form("ask", clear_on_submit=False, border=False):
        left, right = st.columns([5, 1], vertical_alignment="bottom")
        left.text_input("Your question", key="box", max_chars=300, label_visibility="collapsed",
                        placeholder=st.session_state["placeholder"], disabled=wait > 0)
        right.form_submit_button("Ask", on_click=ask_from_form, use_container_width=True, disabled=wait > 0)
    if wait > 0:
        st.caption(f"Too many questions at once. You can ask again in about {wait} seconds.")


def chips(questions, key, label=None):
    if label:
        st.markdown(f'<p class="chip-label">{render.esc(label)}</p>', unsafe_allow_html=True)
    with st.container(key=f"chips_{key}", horizontal=True):
        for i, question in enumerate(questions):
            st.button(question, key=f"{key}_{i}", on_click=ask_from_chip, args=(question,))


def example_chips():
    for group, questions in EXAMPLES.items():
        chips(questions, f"ex_{group}", group)


def how_to_ask(open_first):
    with st.expander("How to ask", expanded=open_first):
        for tip in HOW_TO_ASK:
            st.markdown(f'**{tip["title"]}.** {tip["tip"]}')
            st.button(tip["example"], key=f"tip_{tip['title']}", on_click=ask_from_chip, args=(tip["example"],))


def show_reply(reply, service):
    if reply["ok"]:
        show_html(render.answer_html(reply))
        rows = render.postings_table(reply)
        if rows is not None:
            show_html(render.new_postings_summary(reply))
            if rows:
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        if reply["follow_ups"]:
            chips(reply["follow_ups"], "next", "Ask next")
        with st.expander("Answer as plain text"):
            st.text(reply["text"])
        return
    if reply["limited"]:
        st.warning(reply["text"])
        return
    if not st.session_state.get("asked", "").strip():
        st.info(reply["text"])
        chips([q for group in reply["examples"].values() for q in group[:1]], "try", "Try one of these")
        return
    st.markdown("### That one I can't answer")
    st.text(reply["hint"] or reply["text"].split("\n\n")[0])
    typed = st.session_state.get("asked", "")
    near = service.suggest(typed) if typed else []
    if near:
        chips(near, "near", "Did you mean")
    if reply["tips"]:
        st.markdown("#### What works")
        for tip in reply["tips"]:
            st.markdown(f'**{tip["title"]}.** {tip["tip"]}')
    chips([q for group in reply["examples"].values() for q in group[:1]], "try", "Try one of these")


def main():
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
    start()
    service = get_service()
    run_if_asked(service)
    reply = st.session_state["reply"]

    main_col, side_col = st.columns([7, 3], gap="large")
    with main_col:
        hero()
        search_box()
        if reply is None:
            example_chips()
        else:
            show_reply(reply, service)
    with side_col:
        how_to_ask(open_first=reply is None)
        if reply is not None:
            with st.expander("More examples"):
                example_chips()
    show_html(render.facts_html(service.facts()))


main()
