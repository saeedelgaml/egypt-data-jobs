"""Synthetic job board. Every posting here is invented.

generate_jobs(date) returns the messy postings a job board would show on that
date. generate_truth(date) returns the correct clean answer for each posting,
so later tests can check the cleaning step and the chatbot against known facts.
The same date always gives the same output.
"""
import random
import sys
from datetime import date, datetime, timedelta

# Share of postings per role.
ROLE_WEIGHTS = {
    "data_engineer": 0.30,
    "data_analyst": 0.30,
    "data_scientist": 0.15,
    "ml_engineer": 0.10,
    "bi_developer": 0.10,
    "other": 0.05,
}

# Ways a board might write each role.
ROLE_TITLES = {
    "data_engineer": ["Data Engineer"],
    "data_analyst": ["Data Analyst"],
    "data_scientist": ["Data Scientist"],
    "ml_engineer": ["Machine Learning Engineer", "ML Engineer"],
    "bi_developer": ["BI Developer", "Power BI Developer", "Business Intelligence Developer"],
    "other": ["Backend Developer", "Software Engineer", "QA Engineer", "Project Coordinator"],
}

SENIORITY_WEIGHTS = {"junior": 0.30, "mid": 0.45, "senior": 0.25}

SENIORITY_FORMATS = {
    "junior": ["Junior {r}", "Jr. {r}", "{r} (Junior)"],
    "mid": ["{r}", "{r}", "{r} II", "{r} (Hybrid)"],
    "senior": ["Senior {r}", "Sr. {r}", "Sr {r}", "{r} (Senior)", "Lead {r}"],
}

# Invented monthly salary bands in EGP: (low, high) per role and seniority.
# These are made-up numbers, not market facts.
SALARY_BANDS = {
    "data_engineer": {"junior": (12000, 20000), "mid": (20000, 35000), "senior": (35000, 60000)},
    "data_analyst": {"junior": (8000, 15000), "mid": (15000, 25000), "senior": (25000, 40000)},
    "data_scientist": {"junior": (12000, 20000), "mid": (20000, 35000), "senior": (35000, 55000)},
    "ml_engineer": {"junior": (15000, 25000), "mid": (25000, 40000), "senior": (40000, 65000)},
    "bi_developer": {"junior": (9000, 16000), "mid": (16000, 28000), "senior": (28000, 45000)},
    "other": {"junior": (8000, 15000), "mid": (15000, 25000), "senior": (25000, 40000)},
}

CITY_WEIGHTS = {"Cairo": 0.55, "Giza": 0.20, "Alexandria": 0.12, "Remote": 0.13}

# The messy spellings. The \u escapes are the Arabic names for Cairo, Giza
# and Alexandria.
CITY_VARIANTS = {
    "Cairo": ["Cairo", "cairo", "New Cairo", "Nasr City, Cairo", "Maadi, Cairo",
              "Cairo, Egypt", "\u0627\u0644\u0642\u0627\u0647\u0631\u0629"],
    "Giza": ["Giza", "6th of October", "Sheikh Zayed, Giza", "Giza, Egypt",
             "\u0627\u0644\u062c\u064a\u0632\u0629"],
    "Alexandria": ["Alexandria", "Alex", "Alexandria, Egypt",
                   "\u0627\u0644\u0625\u0633\u0643\u0646\u062f\u0631\u064a\u0629"],
    "Remote": ["Remote", "remote", "Remote (Egypt)", "Work from home"],
}

# Invented companies. Any match with a real company is a coincidence.
COMPANIES = [
    "Sphinx Data Labs", "Delta Byte Systems", "Papyrus Analytics", "Luxor Cloud Works",
    "Pharos Digital", "Karnak Software", "Siwa Systems", "Aswan Insight",
    "Red Sea Compute", "Mokattam Tech", "Zamalek Data Co", "Fayoum Analytics",
    "Nubia Networks", "Heliopolis Labs", "Rosetta AI Works", "Tahrir Metrics",
    "Abu Simbel Cloud", "Dahab Digital", "Memphis Logic", "Alamein Systems",
]
COMPANY_SUFFIXES = ["", "", "", " LLC", " Ltd.", " (Egypt)"]

# Chance that each skill appears in a posting for the role. These are the
# known answers the chatbot will be tested against.
ROLE_SKILL_PROBS = {
    "data_engineer": {"Python": 0.90, "SQL": 0.90, "Airflow": 0.50, "Spark": 0.50, "AWS": 0.40,
                      "Git": 0.30, "Docker": 0.30, "Kafka": 0.20, "Azure": 0.20, "dbt": 0.15},
    "data_analyst": {"SQL": 0.85, "Excel": 0.80, "Power BI": 0.55, "Python": 0.40,
                     "Tableau": 0.30, "Statistics": 0.30},
    "data_scientist": {"Python": 0.95, "SQL": 0.60, "Pandas": 0.60, "Scikit-learn": 0.60,
                       "Statistics": 0.50, "TensorFlow": 0.25, "PyTorch": 0.25},
    "ml_engineer": {"Python": 0.95, "PyTorch": 0.50, "Docker": 0.50, "TensorFlow": 0.40,
                    "AWS": 0.40, "Scikit-learn": 0.40, "SQL": 0.30, "Git": 0.30},
    "bi_developer": {"Power BI": 0.85, "SQL": 0.80, "Excel": 0.50, "Tableau": 0.30, "Azure": 0.20},
    "other": {"Python": 0.40, "Java": 0.40, "Git": 0.40, "SQL": 0.30, "Excel": 0.20},
}

# Other ways a board might write a skill.
SKILL_ALIASES = {
    "Python": ["Python", "python", "Python3"],
    "SQL": ["SQL", "Sql"],
    "Spark": ["Spark", "Apache Spark", "PySpark"],
    "Airflow": ["Airflow", "Apache Airflow"],
    "AWS": ["AWS", "Amazon Web Services"],
    "Power BI": ["Power BI", "PowerBI", "power bi"],
    "Scikit-learn": ["Scikit-learn", "sklearn"],
    "Excel": ["Excel", "MS Excel"],
}
SKILL_SEPARATORS = [", ", "; ", " | ", " / ", ","]

SALARY_CONFIDENTIAL = 0.15
SALARY_MISSING = 0.10
SKILLS_MISSING = 0.05

RAW_FIELDS = ["source_job_id", "title", "company", "city", "salary_text",
              "skills_text", "posted_date"]


def _pick(rng, weights):
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def _format_salary(rng, low, high):
    options = [
        f"{low:,} - {high:,} EGP",
        f"{low // 1000}k-{high // 1000}k",
        f"EGP {low} - {high}",
        f"{low}-{high}",
        f"{low // 1000}K - {high // 1000}K EGP/month",
        f"{low:,} to {high:,} EGP monthly",
    ]
    return rng.choice(options)


def _build_posting(day, index, rng):
    role = _pick(rng, ROLE_WEIGHTS)
    seniority = _pick(rng, SENIORITY_WEIGHTS)

    title = rng.choice(SENIORITY_FORMATS[seniority]).format(r=rng.choice(ROLE_TITLES[role]))
    title = rng.choices([title, title.lower(), title.upper()], weights=[0.7, 0.2, 0.1])[0]

    city = _pick(rng, CITY_WEIGHTS)
    city_text = rng.choice(CITY_VARIANTS[city])

    if rng.random() < 0.08:
        company, company_text = None, "Confidential"
    else:
        company = rng.choice(COMPANIES)
        company_text = company + rng.choice(COMPANY_SUFFIXES)
        if rng.random() < 0.10:
            company_text = company_text.lower()

    band_low, band_high = SALARY_BANDS[role][seniority]
    low = int(round(rng.uniform(band_low, band_high * 0.8), -3))
    high = low + 1000 * rng.randint(3, 10)
    roll = rng.random()
    if roll < SALARY_CONFIDENTIAL:
        salary_text, salary_visible = "Confidential", False
    elif roll < SALARY_CONFIDENTIAL + SALARY_MISSING:
        salary_text, salary_visible = None, False
    else:
        salary_text, salary_visible = _format_salary(rng, low, high), True

    skills = [s for s, p in ROLE_SKILL_PROBS[role].items() if rng.random() < p]
    if not skills:
        skills = [next(iter(ROLE_SKILL_PROBS[role]))]
    if rng.random() < SKILLS_MISSING:
        skills_text, skills_visible = None, False
    else:
        names = [rng.choice(SKILL_ALIASES.get(s, [s])) for s in skills]
        rng.shuffle(names)
        skills_text, skills_visible = rng.choice(SKILL_SEPARATORS).join(names), True

    job_id = f"mock-{day:%Y%m%d}-{index:02d}"
    raw = {
        "source_job_id": job_id,
        "title": title,
        "company": company_text,
        "city": city_text,
        "salary_text": salary_text,
        "skills_text": skills_text,
        "posted_date": day.isoformat(),
    }
    truth = {
        "role": role,
        "seniority": seniority,
        "company": company,
        "city": city,
        "salary_min": low,
        "salary_max": high,
        "salary_visible": salary_visible,
        "skills": skills,
        "skills_visible": skills_visible,
        "posted_date": day.isoformat(),
    }
    return raw, truth


def _to_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _posted_on(day):
    """The postings first published on this day (10 to 12 of them)."""
    rng = random.Random(f"mock-board-{day.isoformat()}")
    return [_build_posting(day, i, rng) for i in range(rng.randint(10, 12))]


def _live_on(day):
    """New postings plus repeats of older ones that are still on the board."""
    live = list(_posted_on(day))
    live += [p for i, p in enumerate(_posted_on(day - timedelta(days=1))) if i % 2 == 0]
    live += [p for i, p in enumerate(_posted_on(day - timedelta(days=2))) if i % 3 == 0]
    return live


def generate_jobs(day):
    """Return the messy postings visible on a date, as a list of dicts.

    Roughly half of yesterday's postings and a third of the ones from two
    days ago show up again, with the same source_job_id.
    """
    return [dict(raw) for raw, _ in _live_on(_to_date(day))]


def generate_truth(day):
    """Return the clean facts for the same postings, keyed by source_job_id."""
    return {raw["source_job_id"]: dict(truth) for raw, truth in _live_on(_to_date(day))}


def main():
    sys.stdout.reconfigure(errors="replace")
    day = _to_date(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    jobs = generate_jobs(day)
    print(f"{len(jobs)} postings on {day}. First 8:")
    for job in jobs[:8]:
        print(f"  {job['source_job_id']} | {job['title']} | {job['company']} | "
              f"{job['city']} | {job['salary_text']} | {job['skills_text']}")


if __name__ == "__main__":
    main()
