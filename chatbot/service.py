"""The one door the web page uses.

A page (Streamlit or anything else) should call only this module. It opens the database
read-only, uses the free router, limits how often one visitor can ask, and returns plain
dicts that a page can draw: the answer text, the raw numbers, follow-up questions that are
guaranteed to work, and advice on how to ask.

Nothing here writes to the database or sends data anywhere.
"""
import os
import threading
import time
from collections import deque
from datetime import date

import duckdb

from chatbot.ai import MAX_QUESTION_CHARS, answer_question
from chatbot.router import RuleRouter
from db.schema import DEFAULT_DB_PATH

SAMPLE_DB_PATH = DEFAULT_DB_PATH.parent / "sample.duckdb"


def default_db_path():
    """The database the page should open: the real local one if it exists, else the committed sample.
    The JOBS_DB environment variable (set by whoever runs the page, never by a visitor) overrides both."""
    chosen = os.environ.get("JOBS_DB")
    if chosen:
        return chosen
    return DEFAULT_DB_PATH if DEFAULT_DB_PATH.exists() else SAMPLE_DB_PATH


SYNTHETIC_NOTE = ("All postings are synthetic: a program generated them for this portfolio project. "
                  "They do not describe the real Egyptian job market.")

PLURAL = {"data_engineer": "data engineers", "data_analyst": "data analysts",
          "data_scientist": "data scientists", "ml_engineer": "ml engineers",
          "bi_developer": "bi developers"}

# Click-to-ask questions, grouped for the page. Tests check that every one is answered.
EXAMPLES = {
    "Pay": [
        "What does a data analyst earn in Cairo?",
        "Which city pays data engineers the most?",
        "Lowest paying role",
        "How many jobs pay over 30k?",
    ],
    "Skills": [
        "What skills do ml engineers need?",
        "What skills go with Airflow?",
        "Top 5 skills in Giza",
    ],
    "Hiring": [
        "Who is hiring data scientists?",
        "Top 5 companies hiring data engineers",
        "Which city has the most postings?",
    ],
    "New": [
        "New data engineer jobs in the last 7 days",
        "Remote data analyst jobs",
        "Which role has the most openings?",
    ],
}

# Advice on how to ask. Each tip has an example that a test checks.
HOW_TO_ASK = [
    {"title": "Name a role", "tip": "Say data engineer, data analyst, data scientist, ML engineer or BI developer.",
     "example": "What does a data engineer earn?"},
    {"title": "Add a city", "tip": "Cairo, Giza, Alexandria or Remote.",
     "example": "Data scientist jobs in Alexandria"},
    {"title": "Add a skill", "tip": "Python, SQL, Airflow, Power BI, Spark, Docker and more.",
     "example": "How many postings list Spark?"},
    {"title": "Use numbers", "tip": "Try top 5, over 30k, or the last 7 days.",
     "example": "Top 3 skills for data analysts"},
    {"title": "Ask for a ranking", "tip": "Start with which and end with the most or the lowest.",
     "example": "Which skill pays the most?"},
    {"title": "One thing at a time", "tip": "One city and one skill per question works best.",
     "example": "Companies hiring in Giza"},
]

LIMITS_NOTE = ("Not available: trends over time, seniority, other countries or cities, advice about "
               "what to choose, and any change to the data.")


class RateLimiter:
    """Allow a visitor a few questions per minute and per hour, and everyone a daily total.
    Kept in memory, keyed by an opaque session id. It stores times only, never questions."""

    def __init__(self, per_minute=10, per_hour=120, per_day_total=4000, max_sessions=5000, clock=time.time):
        self.per_minute, self.per_hour, self.per_day_total = per_minute, per_hour, per_day_total
        self.max_sessions, self.clock = max_sessions, clock
        self._seen = {}
        self._day = deque()
        self._lock = threading.Lock()

    def check(self, session):
        """Returns 0 when the visitor may ask now, else the seconds to wait."""
        now = self.clock()
        with self._lock:
            while self._day and now - self._day[0] > 86400:
                self._day.popleft()
            if len(self._day) >= self.per_day_total:
                return 3600
            key = str(session)[:100]
            times = self._seen.setdefault(key, deque())
            while times and now - times[0] > 3600:
                times.popleft()
            last_minute = [t for t in times if now - t <= 60]
            if len(last_minute) >= self.per_minute:
                return max(1, int(60 - (now - last_minute[0])) + 1)
            if len(times) >= self.per_hour:
                return max(1, int(3600 - (now - times[0])) + 1)
            times.append(now)
            self._day.append(now)
            if len(self._seen) > self.max_sessions:
                for old in [k for k, v in self._seen.items() if not v or now - v[-1] > 3600]:
                    del self._seen[old]
            return 0


def _a(noun):
    return ("an " if noun.startswith(("ml", "a", "e", "i", "o", "u")) else "a ") + noun


def follow_ups(function, params):
    """Up to three next questions that make sense after this answer."""
    role = params.get("role")
    plural = PLURAL.get(role)
    skill, city = params.get("skill"), params.get("city")
    out = []
    if function == "salary_for_role":
        if plural:
            out += [f"Which city pays {plural} the most?", f"What skills do {plural} need?",
                    f"Who is hiring {plural}?"]
        else:
            out += ["Which role pays the most?", "Which city pays the most?", "What skills are most in demand?"]
    elif function == "top_skills":
        if plural:
            out += [f"What is the salary for {plural}?", f"Who is hiring {plural}?"]
        out += ["What skills go with Python?"]
    elif function == "skills_with":
        out += [f"How many postings list {skill}?", "Which skill pays the most?", "Which role has the most openings?"]
    elif function == "top_companies":
        out += [f"What is the salary for {plural}?" if plural else "Which role pays the most?",
                "Which city has the most postings?", "What skills are most in demand?"]
    elif function == "jobs_by_city":
        out += ["Which city pays the most?", "Which role has the most openings?", "Who is hiring the most?"]
    elif function == "jobs_by_role":
        out += ["Which role pays the most?", "What skills are most in demand?", "Which city has the most postings?"]
    elif function == "count_postings":
        out += ["Which city has the most postings?", "Which role has the most openings?",
                "Show the newest postings"]
    elif function == "top_paying":
        out += ["What skills are most in demand?", "Who is hiring the most?", "Which city has the most postings?"]
    elif function == "new_postings":
        out += [f"What is the salary for {plural}?" if plural else "Which role pays the most?",
                f"What skills do {plural} need?" if plural else "What skills are most in demand?",
                "Who is hiring the most?"]
    if city and function in ("salary_for_role", "top_skills") and plural:
        out.insert(0, f"Show new {role.replace('_', ' ')} jobs in {city}")
    seen, unique = set(), []
    for q in out:
        if q.lower() not in seen:
            seen.add(q.lower())
            unique.append(q)
    return unique[:3]


class Service:
    """Open once, call ask() for each question. Safe to share between page reruns."""

    def __init__(self, db_path=None, limiter=None, log_path=None):
        self.con = duckdb.connect(str(db_path or default_db_path()), read_only=True)
        self.router = RuleRouter(self.con)
        self.limiter = limiter or RateLimiter()
        self.log_path = log_path
        self._lock = threading.Lock()

    def close(self):
        self.con.close()

    def ask(self, question, session="local"):
        if not isinstance(question, str) or not question.strip():
            return self._reply(False, "Type a question, or click one of the examples.", tips=True)
        if len(question) > MAX_QUESTION_CHARS:
            return self._reply(False, f"Please keep the question under {MAX_QUESTION_CHARS} characters.",
                               tips=True)
        wait = self.limiter.check(session)
        if wait:
            return self._reply(False, f"That is a lot of questions. Please wait {wait} seconds and try again.",
                               limited=True, retry_after=wait)
        try:
            with self._lock:
                cursor = self.con.cursor()
                try:
                    result = answer_question(cursor, question, self.router, self.log_path)
                finally:
                    cursor.close()
        except Exception as problem:  # never show internals to a visitor
            return self._reply(False, f"Something went wrong ({type(problem).__name__}). Please try again.")
        if not result["ok"]:
            return self._reply(False, result["text"], tips=True, hint=result.get("hint"))
        return self._reply(True, result["text"], function=result["function"], params=result["params"],
                           data=result["data"], understood=result["understood"], notes=result["notes"],
                           follow_ups=follow_ups(result["function"], result["params"]))

    @staticmethod
    def _reply(ok, text, tips=False, **extra):
        reply = {"ok": ok, "text": text, "function": None, "params": {}, "data": None, "understood": None,
                 "notes": [], "follow_ups": [], "limited": False, "retry_after": 0, "hint": None,
                 "tips": HOW_TO_ASK if tips else [], "examples": EXAMPLES if tips else {}}
        reply.update(extra)
        return reply

    def facts(self):
        """Numbers for a small panel on the page."""
        one = lambda sql: self.con.cursor().execute(sql).fetchone()
        total, with_salary, first, last = one(
            "SELECT COUNT(*), COUNT(salary_min), MIN(posted_date), MAX(posted_date) FROM jobs")
        run = one("SELECT run_date, status FROM pipeline_runs ORDER BY run_date DESC, run_at DESC LIMIT 1")
        skills = [r[0] for r in self.con.cursor().execute("SELECT skill FROM skills ORDER BY skill").fetchall()]
        return {"postings": total, "with_salary": with_salary, "first_posted": first, "last_posted": last,
                "last_run": run[0] if run else None, "last_run_status": run[1] if run else None,
                "roles": list(PLURAL.values()) + ["other"], "cities": ["Cairo", "Giza", "Alexandria", "Remote"],
                "skills": skills, "synthetic_note": SYNTHETIC_NOTE, "limits_note": LIMITS_NOTE,
                "as_of": date.today().isoformat()}

    def suggest(self, typed, limit=6):
        """Questions to offer while the visitor types. Every suggestion is a known-good question."""
        words = [w for w in str(typed or "").lower()[:100].split() if w]
        if not words:
            return []
        pool = [q for group in EXAMPLES.values() for q in group] + [t["example"] for t in HOW_TO_ASK]
        facts_skills = [r[0] for r in self.con.cursor().execute("SELECT skill FROM skills").fetchall()]
        pool += [f"What skills go with {s}?" for s in facts_skills]
        pool += [f"How many postings list {s}?" for s in facts_skills]
        pool += [f"What does {_a(r[:-1])} earn?" for r in PLURAL.values()]
        pool += [f"Who is hiring {r}?" for r in PLURAL.values()]
        pool += [f"What skills do {r} need?" for r in PLURAL.values()]
        pool += [f"{r.capitalize()} jobs in {c}" for r in PLURAL.values() for c in ("Cairo", "Giza", "Alexandria", "Remote")]
        scored = []
        for q in dict.fromkeys(pool):
            low = q.lower()
            if all(w in low for w in words):
                scored.append((0 if low.startswith(words[0]) else 1, len(q), q))
        return [q for _, _, q in sorted(scored)[:limit]]
