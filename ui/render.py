"""Turns a reply from chatbot.service into HTML and tables for the page.

Every piece of text that came from a visitor or from the database goes through esc() before it
is placed in markup. Numbers are converted with num() so only digits can reach the markup.
The only unescaped text here is markup written in this file.
"""
from html import escape

ROLE_LABEL = {"data_engineer": "data engineer", "data_analyst": "data analyst",
              "data_scientist": "data scientist", "ml_engineer": "ML engineer",
              "bi_developer": "BI developer", "other": "other roles"}

TITLES = {
    "salary_for_role": "Typical monthly pay",
    "top_paying": "Who pays the most",
    "top_skills": "Skills people ask for",
    "skills_with": "Skills that come together",
    "top_companies": "Who is hiring",
    "jobs_by_city": "Postings by city",
    "jobs_by_role": "Postings by role",
    "count_postings": "Postings that match",
    "new_postings": "Newest postings",
}


def esc(value):
    return escape("" if value is None else str(value), quote=True)


def num(value, default=0):
    try:
        return float(value) if not isinstance(value, bool) else default
    except (TypeError, ValueError):
        return default


def money(value):
    return f"{int(round(num(value))):,}"


def role_label(role):
    return ROLE_LABEL.get(role, str(role).replace("_", " ")) if role else None


def scope(params):
    """'data analyst, in Cairo, listing SQL' from the filters of a reply."""
    bits = []
    if params.get("role"):
        bits.append(role_label(params["role"]))
    if params.get("city"):
        bits.append(f"in {params['city']}")
    if params.get("skill"):
        bits.append(f"listing {params['skill']}")
    if params.get("min_salary") is not None:
        bits.append(f"paying at least {money(params['min_salary'])} EGP")
    return ", ".join(bits) if bits else "all roles and cities"


def head(reply):
    function = reply["function"]
    return (f'<div class="answer-head"><h2>{esc(TITLES.get(function, "Answer"))}</h2>'
            f'<p class="scope">{esc(scope(reply["params"]))}</p></div>')


def read_as(reply):
    if not reply.get("understood"):
        return ""
    return f'<p class="read-as"><span>Read as</span> {esc(reply["understood"])}</p>'


def notes(reply):
    return "".join(f'<p class="note">{esc(n)}</p>' for n in reply.get("notes") or [])


def bars(rows):
    """rows: list of (label, fraction between 0 and 1, value text)."""
    if not rows:
        return ""
    items = []
    for i, (label, fraction, text) in enumerate(rows):
        width = max(2.0, min(100.0, num(fraction) * 100))
        items.append(f'<li style="--w:{width:.1f}%;--i:{i}"><span class="lab">{esc(label)}</span>'
                     f'<span class="bar"><i></i></span><span class="val">{esc(text)}</span></li>')
    return f'<ul class="bars">{"".join(items)}</ul>'


def salary_card(data):
    if not data.get("with_salary"):
        return '<p class="empty">No posting here lists a salary, so there is nothing to average.</p>'
    low, typ, high = num(data["lowest"]), num(data["typical"]), num(data["highest"])
    span = high - low
    pos = 50.0 if span <= 0 else max(0.0, min(100.0, (typ - low) / span * 100))
    return (f'<p class="big"><span class="hl">{money(typ)}</span> <span class="unit">EGP a month</span></p>'
            f'<div class="ruler" style="--p:{pos:.1f}%"><i class="mark"></i></div>'
            f'<p class="ruler-ends"><span>lowest listed {money(low)}</span><span>highest listed {money(high)}</span></p>'
            f'<p class="basis">Median of the range midpoints, from {int(num(data["with_salary"]))} of '
            f'{int(num(data["postings"]))} postings that list a salary.</p>')


def count_card(data):
    return (f'<p class="big"><span class="hl">{int(num(data["total"])):,}</span> '
            f'<span class="unit">postings</span></p>')


def ranking_rows(function, data):
    """(label, fraction, text) rows for the bar list, or None when the answer is not a ranking."""
    if function in ("top_skills", "skills_with"):
        return [(r["skill"], num(r["share"]), f'{round(num(r["share"]) * 100)}% · {int(num(r["postings"]))}')
                for r in data.get("skills", [])]
    if function == "top_companies":
        rows = data.get("companies", [])
        top = max([num(r["postings"]) for r in rows] or [1])
        return [(r["company"], num(r["postings"]) / top, str(int(num(r["postings"])))) for r in rows]
    if function == "jobs_by_city":
        rows = data.get("cities", [])
        top = max([num(r["postings"]) for r in rows] or [1])
        out = [(r["city"], num(r["postings"]) / top, str(int(num(r["postings"])))) for r in rows]
        if data.get("no_city"):
            out.append(("city not listed", num(data["no_city"]) / top, str(int(num(data["no_city"])))))
        return out
    if function == "jobs_by_role":
        rows = data.get("roles", [])
        top = max([num(r["postings"]) for r in rows] or [1])
        return [(role_label(r["role"]), num(r["postings"]) / top, str(int(num(r["postings"])))) for r in rows]
    if function == "top_paying":
        rows = data.get("groups", [])
        top = max([num(r["typical"]) for r in rows] or [1])
        label = (lambda g: role_label(g)) if data.get("group_by") == "role" else (lambda g: g)
        return [(label(r["group"]), num(r["typical"]) / top, f'{money(r["typical"])} EGP') for r in rows]
    return None


def answer_html(reply):
    """All the markup for one successful reply."""
    function, data = reply["function"], reply["data"] or {}
    parts = [read_as(reply), head(reply)]
    if function == "salary_for_role":
        parts.append(salary_card(data))
    elif function == "count_postings":
        parts.append(count_card(data))
    else:
        rows = ranking_rows(function, data)
        if rows is not None:
            parts.append(bars(rows) if rows else '<p class="empty">Nothing matches that yet.</p>')
            if function == "top_paying":
                parts.append('<p class="basis">Typical pay is the median of the range midpoints. Each group '
                             'needs at least 3 postings that list a salary.</p>')
            if function in ("top_skills", "skills_with"):
                parts.append('<p class="basis">The percentage is the share of postings that list the skill. '
                             'The number is how many postings.</p>')
    parts.append(notes(reply))
    return f'<section class="answer">{"".join(parts)}</section>'


def postings_table(reply):
    """Rows for st.dataframe when the reply is a list of postings."""
    if reply["function"] != "new_postings" or not reply["data"]:
        return None
    rows = []
    for p in reply["data"].get("postings", []):
        pay = "not listed" if p.get("salary_min") is None else f'{money(p["salary_min"])}-{money(p["salary_max"])}'
        rows.append({"Title": p.get("title") or "", "Company": p.get("company") or "not listed",
                     "City": p.get("city") or "not listed", "EGP a month": pay,
                     "Posted": str(p.get("posted_date") or "")})
    return rows


def new_postings_summary(reply):
    data = reply["data"] or {}
    total = int(num(data.get("total")))
    shown = len(data.get("postings", []))
    if not total:
        return '<p class="empty">No new postings match in that time.</p>'
    tail = f", showing the newest {shown}" if total > shown else ""
    return (f'<p class="basis">{total} new postings in the last {int(num(data.get("days")))} days{esc(tail)}.</p>')


def chips_html(label, questions):
    """Only for static text written in this project; used for tests of escaping, not for the page buttons."""
    return f'<p class="chip-group">{esc(label)}</p>' + "".join(f"<span>{esc(q)}</span>" for q in questions)


def facts_html(facts):
    first, last = facts.get("first_posted"), facts.get("last_posted")
    ran = facts.get("last_run")
    items = [
        (f'{int(num(facts.get("postings"))):,}', "postings"),
        (f'{esc(first)} to {esc(last)}' if first and last else "no dates yet", "posted between"),
        (esc(ran) if ran else "never", "last pipeline run"),
    ]
    cells = "".join(f'<div><b>{value}</b><span>{esc(label)}</span></div>' for value, label in items)
    return (f'<footer class="facts">{cells}</footer>'
            f'<p class="fine">{esc(facts.get("synthetic_note"))} {esc(facts.get("limits_note"))}</p>')
