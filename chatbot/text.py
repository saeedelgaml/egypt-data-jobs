"""Turn an answer from chatbot.queries.run() into plain English.

The wording is fixed, so the same data always gives the same sentence. The AI
layer (a later phase) can rephrase these answers, but the numbers always come
from here and from the database.
"""


def _label(role):
    return role.replace("_", " ") if role else "all roles"


def _money(value):
    return f"{value:,}"


def _salary_range(low, high):
    if low is None:
        return "salary not listed"
    return f"{_money(low)}-{_money(high)} EGP/month"


def _new_postings(r):
    if r["total"] == 0:
        return f"No new {_label(r['role'])} postings in the last {r['days']} days."
    head = (f"{r['total']} new {_label(r['role'])} postings in the last {r['days']} days "
            f"(up to {r['latest_date']})")
    if r["total"] > len(r["postings"]):
        head += f", showing {len(r['postings'])}"
    lines = [head + ":"]
    for p in r["postings"]:
        company = p["company"] or "company not listed"
        city = p["city"] or "city not listed"
        lines.append(f"- {p['title']} at {company}, {city}, "
                     f"{_salary_range(p['salary_min'], p['salary_max'])} (posted {p['posted_date']})")
    return "\n".join(lines)


def _salary(r):
    where = _label(r["role"]) + (f" in {r['city']}" if r["city"] else "")
    if r["postings"] == 0:
        return f"No {where} postings found."
    if r["with_salary"] == 0:
        return f"No salary data for {where}: none of the {r['postings']} postings list a salary."
    return (f"{where}: typical {_money(r['typical'])} EGP/month (median of the range midpoints), "
            f"lowest listed {_money(r['lowest'])}, highest listed {_money(r['highest'])}. "
            f"Based on {r['with_salary']} of {r['postings']} postings that list a salary.")


def _skills(r):
    scope = _label(r["role"])
    if not r["skills"]:
        return f"No skills listed for {scope} postings."
    lines = [f"Top skills for {scope} (share of the {r['postings_with_skills']} postings that list skills):"]
    for s in r["skills"]:
        lines.append(f"- {s['skill']}: {round(s['share'] * 100)}% ({s['postings']} postings)")
    return "\n".join(lines)


def _companies(r):
    if not r["companies"]:
        return f"No companies found for {_label(r['role'])}."
    scope = f"{_label(r['role'])} postings" if r["role"] else "postings"
    lines = [f"Companies with the most {scope}:"]
    for c in r["companies"]:
        lines.append(f"- {c['company']}: {c['postings']}")
    return "\n".join(lines)


def _cities(r):
    if not r["cities"]:
        return f"No postings found for {_label(r['role'])}."
    scope = f"{_label(r['role']).capitalize()} postings" if r["role"] else "Postings"
    lines = [f"{scope} by city:"]
    for c in r["cities"]:
        lines.append(f"- {c['city']}: {c['postings']}")
    if r["no_city"]:
        lines.append(f"- city not listed: {r['no_city']}")
    return "\n".join(lines)


def _count(r):
    where = _label(r["role"]) + (f" in {r['city']}" if r["city"] else "")
    return f"{r['total']} postings for {where}."


_FORMATTERS = {
    "new_postings": _new_postings,
    "salary_for_role": _salary,
    "top_skills": _skills,
    "top_companies": _companies,
    "jobs_by_city": _cities,
    "count_postings": _count,
}


def to_text(answer):
    """Plain-English version of one answer dict from run()."""
    if not answer["ok"]:
        return answer["message"]
    return _FORMATTERS[answer["function"]](answer["result"])
