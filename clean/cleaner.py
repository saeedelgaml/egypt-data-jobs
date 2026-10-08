"""Cleaner: turn the messy raw_jobs table into the tidy jobs and job_skills tables.

Run from the project folder:  python -m clean.cleaner
Running it again is safe: postings that are already in jobs are skipped.
"""
from clean.rules import (
    clean_city,
    clean_company,
    clean_role,
    clean_skills,
    clean_title,
    parse_salary,
)
from db.schema import DEFAULT_DB_PATH, add_skill, connect, create_tables

NEW_RAW_ROWS = """
SELECT source_job_id, title, company, city, salary_text, skills_text,
       posted_date, collected_on
FROM raw_jobs
WHERE source_job_id NOT IN (SELECT job_id FROM jobs)
QUALIFY ROW_NUMBER() OVER (PARTITION BY source_job_id ORDER BY collected_on) = 1
ORDER BY posted_date, source_job_id
"""


def clean_raw(con):
    """Clean every posting in raw_jobs that is not yet in jobs.

    Each posting is stored once, even if it was collected on several days.
    Returns a summary with counts, including how much data was missing.
    """
    rows = con.execute(NEW_RAW_ROWS).fetchall()
    skills_before = con.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
    summary = {
        "jobs_added": 0,
        "job_skills_added": 0,
        "skills_added": 0,
        "missing_salary": 0,
        "missing_city": 0,
        "missing_company": 0,
        "missing_skills": 0,
    }

    con.begin()
    try:
        for (job_id, title, company, city, salary_text, skills_text,
             posted_date, collected_on) in rows:
            low, high = parse_salary(salary_text)
            city_clean = clean_city(city)
            company_clean = clean_company(company)
            skills = clean_skills(skills_text)

            con.execute(
                "INSERT INTO jobs (job_id, title, role, company, city, salary_min, "
                "salary_max, posted_date, first_seen_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [job_id, clean_title(title), clean_role(title), company_clean, city_clean,
                 low, high, posted_date, collected_on],
            )
            for skill in skills:
                add_skill(con, skill)
                con.execute("INSERT INTO job_skills VALUES (?, ?)", [job_id, skill])

            summary["jobs_added"] += 1
            summary["job_skills_added"] += len(skills)
            summary["missing_salary"] += low is None
            summary["missing_city"] += city_clean is None
            summary["missing_company"] += company_clean is None
            summary["missing_skills"] += not skills
        con.commit()
    except Exception:
        con.rollback()
        raise

    summary["skills_added"] = con.execute("SELECT COUNT(*) FROM skills").fetchone()[0] - skills_before
    return summary


def main():
    con = connect()
    create_tables(con)
    s = clean_raw(con)
    print(f"jobs added: {s['jobs_added']}, job_skills added: {s['job_skills_added']}, "
          f"new skills: {s['skills_added']}")
    print(f"missing in the new jobs: salary {s['missing_salary']}, city {s['missing_city']}, "
          f"company {s['missing_company']}, skills {s['missing_skills']}")
    total = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    print(f"jobs now holds {total} rows in {DEFAULT_DB_PATH}")
    con.close()


if __name__ == "__main__":
    main()
