"""The answers the chatbot can give.

Each answer is one function that runs one fixed SQL query on the tidy tables
(jobs, job_skills) and returns plain Python data. Most answers accept the same
optional filters: a role, a city and a skill. Values that come from a customer
are checked against known values and passed to SQL as parameters, never pasted
into the SQL text. The chatbot cannot run any query that is not in this file.

Use run() to call an answer by name. It never raises: a bad name or a bad
value comes back as {"ok": False, "message": ...}.
"""
import inspect

from db.schema import SEED_ROLES

MAX_LIMIT = 20
MAX_DAYS = 90
MAX_SALARY = 1_000_000
MIN_GROUP = 3  # a group needs this many listed salaries before it can be ranked


class BadQuestion(ValueError):
    """The question has a value the answer functions do not accept."""


def _check_role(role):
    if role is None:
        return None
    cleaned = str(role).strip().lower().replace(" ", "_").replace("-", "_")
    if cleaned not in SEED_ROLES:
        raise BadQuestion(f"I do not know the role {role!r}. Roles: " + ", ".join(SEED_ROLES))
    return cleaned


def _check_city(con, city):
    if city is None:
        return None
    known = [r[0] for r in con.execute(
        "SELECT DISTINCT city FROM jobs WHERE city IS NOT NULL ORDER BY city").fetchall()]
    for name in known:
        if name.lower() == str(city).strip().lower():
            return name
    raise BadQuestion(f"I have no postings in {city!r}. Cities: " + (", ".join(known) or "none yet"))


def _check_skill(con, skill, required=False):
    if skill is None:
        if required:
            raise BadQuestion("This answer needs a skill, such as Python or SQL.")
        return None
    known = [r[0] for r in con.execute("SELECT skill FROM skills ORDER BY skill").fetchall()]
    for name in known:
        if name.lower() == str(skill).strip().lower():
            return name
    raise BadQuestion(f"I have no postings that list {skill!r}. Skills: " + (", ".join(known) or "none yet"))


def _check_int(value, name, low, high):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise BadQuestion(f"{name} must be a whole number.") from None
    return max(low, min(high, number))


def _check_amount(value):
    if value is None:
        return None
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise BadQuestion("min_salary must be a number.") from None
    if not 0 <= amount <= MAX_SALARY:
        raise BadQuestion(f"min_salary must be between 0 and {MAX_SALARY:,}.")
    return int(amount) if amount == int(amount) else amount


def _scope(role=None, city=None, skill=None, min_salary=None):
    """Build WHERE conditions on the jobs table (alias j) from fixed fragments.
    Only values go in as parameters."""
    parts, params = [], []
    if role is not None:
        parts.append("j.role = ?")
        params.append(role)
    if city is not None:
        parts.append("j.city = ?")
        params.append(city)
    if skill is not None:
        parts.append("EXISTS (SELECT 1 FROM job_skills s WHERE s.job_id = j.job_id AND s.skill = ?)")
        params.append(skill)
    if min_salary is not None:
        parts.append("j.salary_min IS NOT NULL AND (j.salary_min + j.salary_max) / 2.0 >= ?")
        params.append(min_salary)
    return parts, params


def _where(parts):
    return (" WHERE " + " AND ".join(parts)) if parts else ""


def new_postings(con, role="data_engineer", city=None, skill=None, days=7, limit=10):
    """Postings first seen in the last `days` days of data, newest first.
    role=None means every role."""
    role = _check_role(role)
    city = _check_city(con, city)
    skill = _check_skill(con, skill)
    days = _check_int(days, "days", 1, MAX_DAYS)
    limit = _check_int(limit, "limit", 1, MAX_LIMIT)
    latest = con.execute("SELECT MAX(first_seen_date) FROM jobs").fetchone()[0]
    columns = ["job_id", "title", "company", "city", "salary_min", "salary_max",
               "posted_date", "first_seen_date"]
    rows = []
    if latest is not None:
        parts, params = _scope(role, city, skill)
        parts.append("j.first_seen_date > ? - CAST(? AS INTEGER)")
        rows = con.execute(
            "SELECT j.job_id, j.title, j.company, j.city, j.salary_min, j.salary_max, "
            "j.posted_date, j.first_seen_date FROM jobs j" + _where(parts) +
            " ORDER BY j.first_seen_date DESC, j.posted_date DESC, j.job_id",
            params + [latest, days]).fetchall()
    return {
        "role": role, "city": city, "skill": skill, "days": days,
        "latest_date": latest,
        "total": len(rows),
        "postings": [dict(zip(columns, r)) for r in rows[:limit]],
    }


def salary_for_role(con, role=None, city=None, skill=None):
    """Monthly salary in EGP, from the postings that list one."""
    role = _check_role(role)
    city = _check_city(con, city)
    skill = _check_skill(con, skill)
    parts, params = _scope(role, city, skill)
    postings, with_salary, typical, lowest, highest = con.execute(
        "SELECT COUNT(*), COUNT(j.salary_min), median((j.salary_min + j.salary_max) / 2.0), "
        "MIN(j.salary_min), MAX(j.salary_max) FROM jobs j" + _where(parts), params).fetchone()
    return {
        "role": role, "city": city, "skill": skill,
        "postings": postings,
        "with_salary": with_salary,
        "typical": None if typical is None else round(typical),
        "lowest": lowest,
        "highest": highest,
    }


def top_skills(con, role=None, city=None, limit=5):
    """Skills ranked by how many postings list them. Share = postings with the
    skill divided by postings that list at least one skill."""
    role = _check_role(role)
    city = _check_city(con, city)
    limit = _check_int(limit, "limit", 1, MAX_LIMIT)
    parts, params = _scope(role, city)
    join = " FROM job_skills js JOIN jobs j ON j.job_id = js.job_id" + _where(parts)
    base = con.execute("SELECT COUNT(DISTINCT js.job_id)" + join, params).fetchone()[0]
    rows = con.execute(
        "SELECT js.skill, COUNT(*) AS n" + join +
        " GROUP BY js.skill ORDER BY n DESC, js.skill LIMIT ?", params + [limit]).fetchall()
    return {
        "role": role, "city": city,
        "postings_with_skills": base,
        "skills": [{"skill": s, "postings": n, "share": round(n / base, 2)} for s, n in rows],
    }


def skills_with(con, skill, role=None, city=None, limit=5):
    """Other skills that appear in the postings which list `skill`. Share = postings
    with the other skill divided by postings that list `skill`."""
    skill = _check_skill(con, skill, required=True)
    role = _check_role(role)
    city = _check_city(con, city)
    limit = _check_int(limit, "limit", 1, MAX_LIMIT)
    parts, params = _scope(role, city, skill)
    base = con.execute("SELECT COUNT(*) FROM jobs j" + _where(parts), params).fetchone()[0]
    rows = con.execute(
        "SELECT js.skill, COUNT(*) AS n FROM jobs j JOIN job_skills js ON js.job_id = j.job_id" +
        _where(parts + ["js.skill <> ?"]) + " GROUP BY js.skill ORDER BY n DESC, js.skill LIMIT ?",
        params + [skill, limit]).fetchall()
    return {
        "skill": skill, "role": role, "city": city,
        "postings_with_skill": base,
        "skills": [{"skill": s, "postings": n, "share": round(n / base, 2)} for s, n in rows],
    }


def top_companies(con, role=None, city=None, skill=None, limit=5):
    """Companies with the most postings. Postings with no company are skipped."""
    role = _check_role(role)
    city = _check_city(con, city)
    skill = _check_skill(con, skill)
    limit = _check_int(limit, "limit", 1, MAX_LIMIT)
    parts, params = _scope(role, city, skill)
    rows = con.execute(
        "SELECT j.company, COUNT(*) AS n FROM jobs j" + _where(parts + ["j.company IS NOT NULL"]) +
        " GROUP BY j.company ORDER BY n DESC, j.company LIMIT ?", params + [limit]).fetchall()
    return {"role": role, "city": city, "skill": skill,
            "companies": [{"company": c, "postings": n} for c, n in rows]}


def jobs_by_city(con, role=None, skill=None):
    """Number of postings per city, with the count that has no city."""
    role = _check_role(role)
    skill = _check_skill(con, skill)
    parts, params = _scope(role, None, skill)
    rows = con.execute(
        "SELECT j.city, COUNT(*) AS n FROM jobs j" + _where(parts + ["j.city IS NOT NULL"]) +
        " GROUP BY j.city ORDER BY n DESC, j.city", params).fetchall()
    no_city = con.execute(
        "SELECT COUNT(*) FROM jobs j" + _where(parts + ["j.city IS NULL"]), params).fetchone()[0]
    return {"role": role, "skill": skill,
            "cities": [{"city": c, "postings": n} for c, n in rows], "no_city": no_city}


def jobs_by_role(con, city=None, skill=None):
    """Number of postings per role, optionally in one city or listing one skill."""
    city = _check_city(con, city)
    skill = _check_skill(con, skill)
    parts, params = _scope(None, city, skill)
    rows = con.execute(
        "SELECT j.role, COUNT(*) AS n FROM jobs j" + _where(parts + ["j.role IS NOT NULL"]) +
        " GROUP BY j.role ORDER BY n DESC, j.role", params).fetchall()
    return {"city": city, "skill": skill, "roles": [{"role": r, "postings": n} for r, n in rows]}


def count_postings(con, role=None, city=None, skill=None, min_salary=None):
    """How many postings match the filters. min_salary keeps only postings whose
    listed range has a midpoint of at least that many EGP per month."""
    role = _check_role(role)
    city = _check_city(con, city)
    skill = _check_skill(con, skill)
    min_salary = _check_amount(min_salary)
    parts, params = _scope(role, city, skill, min_salary)
    total = con.execute("SELECT COUNT(*) FROM jobs j" + _where(parts), params).fetchone()[0]
    return {"role": role, "city": city, "skill": skill, "min_salary": min_salary, "total": total}


# group_by -> (column, extra join, condition that skips empty groups)
_GROUPS = {
    "role": ("j.role", "", "j.role IS NOT NULL"),
    "city": ("j.city", "", "j.city IS NOT NULL"),
    "company": ("j.company", "", "j.company IS NOT NULL"),
    "skill": ("js.skill", " JOIN job_skills js ON js.job_id = j.job_id", "js.skill IS NOT NULL"),
}


def top_paying(con, group_by="role", role=None, city=None, skill=None, order="highest", limit=5):
    """Rank roles, cities, companies or skills by typical monthly salary (median of
    the range midpoints). A group needs at least MIN_GROUP listed salaries."""
    if group_by not in _GROUPS:
        raise BadQuestion(f"I can rank by: {', '.join(_GROUPS)}.")
    if order not in ("highest", "lowest"):
        raise BadQuestion("order must be highest or lowest.")
    role = _check_role(role)
    city = _check_city(con, city)
    skill = _check_skill(con, skill)
    limit = _check_int(limit, "limit", 1, MAX_LIMIT)
    column, join, not_empty = _GROUPS[group_by]
    parts, params = _scope(role, city, skill)
    direction = "DESC" if order == "highest" else "ASC"
    rows = con.execute(
        f"SELECT {column} AS grp, median((j.salary_min + j.salary_max) / 2.0) AS typical, "
        f"COUNT(j.salary_min) AS n FROM jobs j{join}" +
        _where(parts + [not_empty, "j.salary_min IS NOT NULL"]) +
        f" GROUP BY {column} HAVING COUNT(j.salary_min) >= {MIN_GROUP} "
        f"ORDER BY typical {direction}, grp LIMIT ?", params + [limit]).fetchall()
    return {"group_by": group_by, "order": order, "role": role, "city": city, "skill": skill,
            "groups": [{"group": g, "typical": round(t), "with_salary": n} for g, t, n in rows]}


FUNCTIONS = {
    "new_postings": new_postings,
    "salary_for_role": salary_for_role,
    "top_skills": top_skills,
    "skills_with": skills_with,
    "top_companies": top_companies,
    "jobs_by_city": jobs_by_city,
    "jobs_by_role": jobs_by_role,
    "count_postings": count_postings,
    "top_paying": top_paying,
}

DESCRIPTIONS = {
    "new_postings": "List the newest postings from the last few days, optionally for one role, city or skill.",
    "salary_for_role": "Typical, lowest and highest monthly salary in EGP, optionally for one role, city or skill.",
    "top_skills": "The skills that appear in the most postings, optionally for one role or city.",
    "skills_with": "The other skills that most often appear in postings that list a given skill.",
    "top_companies": "The companies with the most postings, optionally for one role, city or skill.",
    "jobs_by_city": "How many postings there are in each city, optionally for one role or skill.",
    "jobs_by_role": "How many postings there are for each role, optionally in one city or for one skill.",
    "count_postings": "How many postings match an optional role, city, skill and minimum monthly salary.",
    "top_paying": "Rank roles, cities, companies or skills by typical monthly salary, highest or lowest first.",
}


def run(con, name, params=None):
    """Call one answer by name. Never raises: problems come back as ok=False."""
    params = dict(params or {})
    func = FUNCTIONS.get(name)
    if func is None:
        return {"ok": False,
                "message": f"I have no answer called {name!r}. I can answer: " + ", ".join(FUNCTIONS)}
    signature = inspect.signature(func).parameters
    allowed = [p for p in signature if p != "con"]
    unknown = sorted(set(params) - set(allowed))
    if unknown:
        return {"ok": False,
                "message": f"{name} does not take {', '.join(unknown)}. It takes: " + ", ".join(allowed)}
    missing = [p for p in allowed if signature[p].default is inspect.Parameter.empty
               and p not in params]
    if missing:
        return {"ok": False, "message": f"{name} needs: " + ", ".join(missing)}
    try:
        result = func(con, **params)
    except BadQuestion as problem:
        return {"ok": False, "message": str(problem)}
    return {"ok": True, "function": name, "params": params, "result": result}
