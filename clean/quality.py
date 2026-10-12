"""Data-quality report: a few numbers about the jobs table and warnings when they look wrong.

Run from the project folder:  python -m clean.quality
The daily manager calls quality_report() after cleaning and writes any warning to the log,
so a scraper that starts returning empty or odd data is noticed the same day.
"""
from db.schema import DEFAULT_DB_PATH, connect

# Warn when one of these shares is reached.
MAX_SHARE = {"no_salary": 0.60, "no_city": 0.30, "no_company": 0.40, "no_skills": 0.30, "other_role": 0.30}

PROBABLE_REPOSTS = """
SELECT COUNT(*) FROM (
    SELECT job_id, ROW_NUMBER() OVER (
        PARTITION BY lower(title), company, city, salary_min, salary_max
        ORDER BY posted_date, job_id) AS n
    FROM jobs WHERE company IS NOT NULL AND company <> 'Company not disclosed' AND salary_min IS NOT NULL
) WHERE n > 1
"""


def quality_report(con):
    """Counts, shares of missing values, probable reposts and a list of warnings."""
    total = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    report = {"jobs": total, "probable_reposts": con.execute(PROBABLE_REPOSTS).fetchone()[0], "warnings": []}
    if total == 0:
        report["warnings"].append("the jobs table is empty")
        return report
    counts = {
        "no_salary": "SELECT COUNT(*) FROM jobs WHERE salary_min IS NULL",
        "no_city": "SELECT COUNT(*) FROM jobs WHERE city IS NULL",
        "no_company": "SELECT COUNT(*) FROM jobs WHERE company IS NULL OR company = 'Company not disclosed'",
        "no_skills": "SELECT COUNT(*) FROM jobs WHERE job_id NOT IN (SELECT job_id FROM job_skills)",
        "other_role": "SELECT COUNT(*) FROM jobs WHERE role = 'other'",
    }
    for name, sql in counts.items():
        share = con.execute(sql).fetchone()[0] / total
        report[name] = round(share, 3)
        if share >= MAX_SHARE[name]:
            report["warnings"].append(f"{name.replace('_', ' ')} is {share:.0%} of postings (limit {MAX_SHARE[name]:.0%})")
    return report


def main():
    con = connect(DEFAULT_DB_PATH)
    report = quality_report(con)
    con.close()
    for key, value in report.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
