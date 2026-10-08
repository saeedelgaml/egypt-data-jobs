"""Turn an answer from chatbot.queries.run() into plain English.

The wording is fixed, so the same data always gives the same sentence. The numbers
always come from the database, never from a language model.
"""


def _label(role):
    return role.replace("_", " ") if role else "all roles"


def _money(value):
    return f"{value:,}"


def _salary_range(low, high):
    if low is None:
        return "salary not listed"
    return f"{_money(low)}-{_money(high)} EGP/month"


def _filters(r):
    """The city, skill and salary filters of an answer, as a phrase with a leading space."""
    text = ""
    if r.get("city"):
        text += f" in {r['city']}"
    if r.get("skill"):
        text += f" that list {r['skill']}"
    if r.get("min_salary") is not None:
        text += f" paying at least {_money(r['min_salary'])} EGP/month"
    return text


def _postings(r):
    """'data engineer postings in Cairo that list SQL', or 'postings' when nothing is chosen."""
    noun = f"{_label(r['role'])} postings" if r.get("role") else "postings"
    return noun + _filters(r)


def _new_postings(r):
    if r["total"] == 0:
        return f"No new {_postings(r)} in the last {r['days']} days."
    head = (f"{r['total']} new {_postings(r)} in the last {r['days']} days "
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
    where = _label(r["role"]) + _filters(r)
    if r["postings"] == 0:
        return f"No {_postings(r)} found."
    if r["with_salary"] == 0:
        return f"No salary data for {where}: none of the {r['postings']} postings list a salary."
    return (f"{where}: typical {_money(r['typical'])} EGP/month (median of the range midpoints), "
            f"lowest listed {_money(r['lowest'])}, highest listed {_money(r['highest'])}. "
            f"Based on {r['with_salary']} of {r['postings']} postings that list a salary.")


def _skills(r):
    where = _label(r["role"]) + _filters(r)
    if not r["skills"]:
        return f"No skills listed for {_postings(r)}."
    lines = [f"Top skills for {where} (share of the {r['postings_with_skills']} postings that list skills):"]
    for s in r["skills"]:
        lines.append(f"- {s['skill']}: {round(s['share'] * 100)}% ({s['postings']} postings)")
    return "\n".join(lines)


def _skills_with(r):
    scope = "postings" if not r["role"] else f"{_label(r['role'])} postings"
    scope += _filters(r)
    if r["postings_with_skill"] == 0:
        return f"No {scope} list {r['skill']}."
    if not r["skills"]:
        return f"The {r['postings_with_skill']} {scope} that list {r['skill']} name no other skills."
    lines = [f"Skills that appear with {r['skill']} in {scope} "
             f"(share of the {r['postings_with_skill']} postings that list {r['skill']}):"]
    for s in r["skills"]:
        lines.append(f"- {s['skill']}: {round(s['share'] * 100)}% ({s['postings']} postings)")
    return "\n".join(lines)


def _companies(r):
    if not r["companies"]:
        return f"No companies found for {_postings(r)}."
    lines = [f"Companies with the most {_postings(r)}:"]
    for c in r["companies"]:
        lines.append(f"- {c['company']}: {c['postings']}")
    return "\n".join(lines)


def _cities(r):
    if not r["cities"]:
        return f"No postings found for {_postings(r)}."
    noun = f"{_label(r['role']).capitalize()} postings" if r["role"] else "Postings"
    lines = [f"{noun}{_filters(r)} by city:"]
    for c in r["cities"]:
        lines.append(f"- {c['city']}: {c['postings']}")
    if r["no_city"]:
        lines.append(f"- city not listed: {r['no_city']}")
    return "\n".join(lines)


def _roles(r):
    if not r["roles"]:
        return "No postings found" + _filters(r) + "."
    lines = ["Postings by role" + _filters(r) + ":"]
    for x in r["roles"]:
        lines.append(f"- {_label(x['role'])}: {x['postings']}")
    return "\n".join(lines)


def _count(r):
    where = _label(r["role"]) + _filters(r)
    return f"{r['total']} postings for {where}."


def _paying(r):
    from chatbot.queries import MIN_GROUP
    word = "Highest" if r["order"] == "highest" else "Lowest"
    scope = _label(r["role"]) + _filters(r)
    if not r["groups"]:
        return (f"Not enough salary data to rank by {r['group_by']} for {scope}: "
                f"each {r['group_by']} needs at least {MIN_GROUP} postings that list a salary.")
    lines = [f"{word} typical monthly salary by {r['group_by']} for {scope} "
             f"(median of the range midpoints, at least {MIN_GROUP} listed salaries each):"]
    for g in r["groups"]:
        name = g["group"].replace("_", " ") if r["group_by"] == "role" else g["group"]
        lines.append(f"- {name}: {_money(g['typical'])} EGP/month ({g['with_salary']} postings with a salary)")
    return "\n".join(lines)


_FORMATTERS = {
    "new_postings": _new_postings,
    "salary_for_role": _salary,
    "top_skills": _skills,
    "skills_with": _skills_with,
    "top_companies": _companies,
    "jobs_by_city": _cities,
    "jobs_by_role": _roles,
    "count_postings": _count,
    "top_paying": _paying,
}


def to_text(answer):
    """Plain-English version of one answer dict from run()."""
    if not answer["ok"]:
        return answer["message"]
    return _FORMATTERS[answer["function"]](answer["result"])
