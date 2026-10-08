"""The six answers the chatbot can give.

Each answer is one function that runs one fixed SQL query on the tidy tables
(jobs, job_skills) and returns plain Python data. Values that come from a
customer, such as a role or a city, are checked against known values and passed
to SQL as parameters, never pasted into the SQL text. The chatbot cannot run
any query that is not in this file.

Use run() to call an answer by name. It never raises: a bad name or a bad
value comes back as {"ok": False, "message": ...}.
"""
import inspect

from db.schema import SEED_ROLES

MAX_LIMIT = 20
MAX_DAYS = 90


class BadQuestion(ValueError):
    """The question has a value the answer functions do not accept."""


def _check_role(role, required=False):
    if role is None:
        if required:
            raise BadQuestion("This answer needs a role. Roles: " + ", ".join(SEED_ROLES))
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


def _check_int(value, name, low, high):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise BadQuestion(f"{name} must be a whole number.") from None
    return max(low, min(high, number))


def _where(role=None, city=None):
    """Build a WHERE clause from fixed fragments. Only values go in as parameters."""
    parts, params = [], []
    if role is not None:
        parts.append("role = ?")
        params.append(role)
    if city is not None:
        parts.append("city = ?")
        params.append(city)
    return (" WHERE " + " AND ".join(parts)) if parts else "", params


def new_postings(con, role="data_engineer", days=7, limit=10):
    """Postings first seen in the last `days` days of data, newest first."""
    role = _check_role(role, required=True)
    days = _check_int(days, "days", 1, MAX_DAYS)
    limit = _check_int(limit, "limit", 1, MAX_LIMIT)
    latest = con.execute("SELECT MAX(first_seen_date) FROM jobs").fetchone()[0]
    rows = con.execute(
        "SELECT job_id, title, company, city, salary_min, salary_max, posted_date, first_seen_date "
        "FROM jobs WHERE role = ? AND first_seen_date > ? - CAST(? AS INTEGER) "
        "ORDER BY first_seen_date DESC, posted_date DESC, job_id",
        [role, latest, days],
    ).fetchall() if latest is not None else []
    columns = ["job_id", "title", "company", "city", "salary_min", "salary_max",
               "posted_date", "first_seen_date"]
    return {
        "role": role,
        "days": days,
        "latest_date": latest,
        "total": len(rows),
        "postings": [dict(zip(columns, r)) for r in rows[:limit]],
    }


def salary_for_role(con, role, city=None):
    """Monthly salary in EGP for a role, from the postings that list one."""
    role = _check_role(role, required=True)
    city = _check_city(con, city)
    where, params = _where(role, city)
    postings, with_salary, typical, lowest, highest = con.execute(
        "SELECT COUNT(*), COUNT(salary_min), median((salary_min + salary_max) / 2.0), "
        "MIN(salary_min), MAX(salary_max) FROM jobs" + where, params).fetchone()
    return {
        "role": role,
        "city": city,
        "postings": postings,
        "with_salary": with_salary,
        "typical": None if typical is None else round(typical),
        "lowest": lowest,
        "highest": highest,
    }


def top_skills(con, role=None, limit=5):
    """Skills ranked by how many postings list them. Share = postings with the
    skill divided by postings that list at least one skill."""
    role = _check_role(role)
    limit = _check_int(limit, "limit", 1, MAX_LIMIT)
    where, params = _where(role)
    scoped = "SELECT job_id FROM jobs" + where
    base = con.execute(
        f"SELECT COUNT(DISTINCT job_id) FROM job_skills WHERE job_id IN ({scoped})", params
    ).fetchone()[0]
    rows = con.execute(
        f"SELECT skill, COUNT(*) AS n FROM job_skills WHERE job_id IN ({scoped}) "
        "GROUP BY skill ORDER BY n DESC, skill LIMIT ?", params + [limit]).fetchall()
    return {
        "role": role,
        "postings_with_skills": base,
        "skills": [{"skill": s, "postings": n, "share": round(n / base, 2)} for s, n in rows],
    }


def top_companies(con, role=None, limit=5):
    """Companies with the most postings. Postings with no company are skipped."""
    role = _check_role(role)
    limit = _check_int(limit, "limit", 1, MAX_LIMIT)
    where, params = _where(role)
    extra = (" AND " if where else " WHERE ") + "company IS NOT NULL"
    rows = con.execute(
        "SELECT company, COUNT(*) AS n FROM jobs" + where + extra +
        " GROUP BY company ORDER BY n DESC, company LIMIT ?", params + [limit]).fetchall()
    return {"role": role, "companies": [{"company": c, "postings": n} for c, n in rows]}


def jobs_by_city(con, role=None):
    """Number of postings per city, with the count that has no city."""
    role = _check_role(role)
    where, params = _where(role)
    extra = (" AND " if where else " WHERE ") + "city IS NOT NULL"
    rows = con.execute(
        "SELECT city, COUNT(*) AS n FROM jobs" + where + extra +
        " GROUP BY city ORDER BY n DESC, city", params).fetchall()
    no_city = con.execute(
        "SELECT COUNT(*) FROM jobs" + where + (" AND " if where else " WHERE ") + "city IS NULL",
        params).fetchone()[0]
    return {"role": role, "cities": [{"city": c, "postings": n} for c, n in rows],
            "no_city": no_city}


def count_postings(con, role=None, city=None):
    """How many postings match an optional role and city."""
    role = _check_role(role)
    city = _check_city(con, city)
    where, params = _where(role, city)
    total = con.execute("SELECT COUNT(*) FROM jobs" + where, params).fetchone()[0]
    return {"role": role, "city": city, "total": total}


FUNCTIONS = {
    "new_postings": new_postings,
    "salary_for_role": salary_for_role,
    "top_skills": top_skills,
    "top_companies": top_companies,
    "jobs_by_city": jobs_by_city,
    "count_postings": count_postings,
}

DESCRIPTIONS = {
    "new_postings": "List the newest postings for a role (default data_engineer) from the last few days.",
    "salary_for_role": "Typical, lowest and highest monthly salary in EGP for a role, optionally in one city.",
    "top_skills": "The skills that appear in the most postings, optionally for one role.",
    "top_companies": "The companies with the most postings, optionally for one role.",
    "jobs_by_city": "How many postings there are in each city, optionally for one role.",
    "count_postings": "How many postings there are, optionally for one role and city.",
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
