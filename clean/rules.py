"""Cleaning rules: turn messy posting text into tidy values.

Every function takes plain text and returns a plain value, so each rule is easy
to test on its own. The Arabic city names are written as unicode escapes.
"""
import re

ACRONYMS = {"Ai": "AI", "Bi": "BI", "Ml": "ML", "Ii": "II", "Qa": "QA", "Etl": "ETL"}

# Role rules, checked in order. A title that matches none of them is "other".
# "Data Entry Specialist" and "Business Analyst" match nothing on purpose.
ROLE_PATTERNS = [
    ("ml_engineer", r"\b(?:machine\s+learning|ml)\s+engineer\b"),
    ("data_engineer", r"\bdata\s+engineer\b"),
    ("data_scientist", r"\bdata\s+scientist\b"),
    ("data_analyst", r"\bdata\s+analyst\b"),
    ("bi_developer", r"\b(?:power\s*bi|bi|business\s+intelligence)\s+developer\b"),
]

# City rules, checked in order. The first pattern that matches decides.
CITY_PATTERNS = [
    ("Remote", [r"\bremote\b", r"work from home"]),
    ("Alexandria", [r"\balex(?:andria)?\b", "الإسكندرية"]),
    ("Giza", [r"\bgiza\b", r"6th of october", r"sheikh zayed", "الجيزة"]),
    ("Cairo", [r"\bcairo\b", r"nasr city", r"maadi", "القاهرة"]),
]

COMPANY_SUFFIX = re.compile(r"\s*(?:\(egypt\)|llc|ltd\.?|inc\.?)\s*$", re.IGNORECASE)

SKILL_ALIASES = {
    "python": "Python", "python3": "Python",
    "sql": "SQL",
    "spark": "Spark", "apache spark": "Spark", "pyspark": "Spark",
    "airflow": "Airflow", "apache airflow": "Airflow",
    "aws": "AWS", "amazon web services": "AWS",
    "azure": "Azure", "docker": "Docker", "kafka": "Kafka", "dbt": "dbt", "git": "Git",
    "java": "Java", "excel": "Excel", "ms excel": "Excel",
    "power bi": "Power BI", "powerbi": "Power BI", "tableau": "Tableau",
    "pandas": "Pandas", "statistics": "Statistics",
    "scikit-learn": "Scikit-learn", "sklearn": "Scikit-learn",
    "tensorflow": "TensorFlow", "pytorch": "PyTorch",
}

SKILL_SPLIT = re.compile(r"\s*[,;|/]\s*")
SALARY_NUMBER = re.compile(r"(\d+(?:\.\d+)?)\s*([kK])?")


def clean_title(title):
    """Tidy a title for display. Fixes ALL CAPS and all lowercase only."""
    if title is None:
        return None
    text = re.sub(r"\s+", " ", title).strip()
    if text.isupper() or text.islower():
        text = " ".join(ACRONYMS.get(w, w) for w in text.title().split(" "))
    return text


def clean_role(title):
    """Map a messy title to one of the fixed roles."""
    text = (title or "").lower()
    for role, pattern in ROLE_PATTERNS:
        if re.search(pattern, text):
            return role
    return "other"


def clean_city(text):
    """Map a messy city text to Cairo, Giza, Alexandria or Remote. None if unknown."""
    lowered = (text or "").lower()
    for city, patterns in CITY_PATTERNS:
        if any(re.search(p, lowered) for p in patterns):
            return city
    return None


def clean_company(text):
    """Strip legal endings, fix the case. None if the company is hidden."""
    if text is None:
        return None
    name = re.sub(r"\s+", " ", text).strip()
    if not name or name.lower() == "confidential":
        return None
    name = COMPANY_SUFFIX.sub("", name).strip()
    return " ".join(ACRONYMS.get(w, w) for w in name.title().split(" "))


def parse_salary(text):
    """Return (min, max) in EGP per month, or (None, None) if there is no number.

    Understands "20k-30k", "32,000 - 36,000 EGP", "EGP 9000 - 13000" and
    "14,000 to 19,000 EGP monthly". A single number is used as both ends.
    """
    if not text:
        return None, None
    numbers = []
    for value, k in SALARY_NUMBER.findall(text.replace(",", "")):
        numbers.append(int(round(float(value) * (1000 if k else 1))))
    if not numbers:
        return None, None
    if len(numbers) == 1:
        return numbers[0], numbers[0]
    return min(numbers[:2]), max(numbers[:2])


def clean_skills(text):
    """Split a skills text and map each skill to its standard name.

    A skill that is not in the alias list is kept as written, so new skills
    are discovered automatically.
    """
    if not text:
        return []
    found = []
    for token in SKILL_SPLIT.split(text.strip()):
        token = token.strip()
        if not token:
            continue
        skill = SKILL_ALIASES.get(token.lower())
        if skill is None:
            skill = token.title() if token.islower() else token
        found.append(skill)
    return list(dict.fromkeys(found))
