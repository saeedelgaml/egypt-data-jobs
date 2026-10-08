import pytest

from clean.rules import (
    clean_city,
    clean_company,
    clean_role,
    clean_skills,
    clean_title,
    parse_salary,
)


@pytest.mark.parametrize("title, role", [
    ("Data Engineer", "data_engineer"),
    ("sr. data engineer", "data_engineer"),
    ("DATA ENGINEER (JUNIOR)", "data_engineer"),
    ("Lead Data Analyst", "data_analyst"),
    ("Jr. Data Scientist", "data_scientist"),
    ("Machine Learning Engineer", "ml_engineer"),
    ("LEAD ML ENGINEER", "ml_engineer"),
    ("Power BI Developer", "bi_developer"),
    ("Business Intelligence Developer (Hybrid)", "bi_developer"),
    ("bi developer", "bi_developer"),
    ("Data Entry Specialist", "other"),
    ("Business Analyst", "other"),
    ("Database Administrator", "other"),
    ("Analytics Manager", "other"),
    ("Backend Developer", "other"),
    ("", "other"),
])
def test_clean_role(title, role):
    assert clean_role(title) == role


@pytest.mark.parametrize("text, city", [
    ("Cairo", "Cairo"), ("cairo", "Cairo"), ("New Cairo", "Cairo"),
    ("Nasr City, Cairo", "Cairo"), ("Maadi, Cairo", "Cairo"), ("Cairo, Egypt", "Cairo"),
    ("القاهرة", "Cairo"),
    ("Giza", "Giza"), ("6th of October", "Giza"), ("Sheikh Zayed, Giza", "Giza"),
    ("الجيزة", "Giza"),
    ("Alexandria", "Alexandria"), ("Alex", "Alexandria"),
    ("الإسكندرية", "Alexandria"),
    ("Remote", "Remote"), ("Remote (Egypt)", "Remote"), ("Work from home", "Remote"),
    ("Tokyo", None), (None, None),
])
def test_clean_city(text, city):
    assert clean_city(text) == city


@pytest.mark.parametrize("text, expected", [
    ("20k-30k", (20000, 30000)),
    ("20K - 30K EGP/month", (20000, 30000)),
    ("32,000 - 36,000 EGP", (32000, 36000)),
    ("EGP 9000 - 13000", (9000, 13000)),
    ("9000-13000", (9000, 13000)),
    ("14,000 to 19,000 EGP monthly", (14000, 19000)),
    ("36,000 - 32,000 EGP", (32000, 36000)),
    ("25k", (25000, 25000)),
    ("Confidential", (None, None)),
    ("", (None, None)),
    (None, (None, None)),
])
def test_parse_salary(text, expected):
    assert parse_salary(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("Delta Byte Systems", "Delta Byte Systems"),
    ("Delta Byte Systems Ltd.", "Delta Byte Systems"),
    ("Karnak Software LLC", "Karnak Software"),
    ("Papyrus Analytics (Egypt)", "Papyrus Analytics"),
    ("red sea compute", "Red Sea Compute"),
    ("rosetta ai works ltd.", "Rosetta AI Works"),
    ("Confidential", None),
    (None, None),
])
def test_clean_company(text, expected):
    assert clean_company(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("Python, SQL, Airflow", ["Python", "SQL", "Airflow"]),
    ("python3;sql;Apache Airflow", ["Python", "SQL", "Airflow"]),
    ("Spark | PySpark | Apache Spark", ["Spark"]),
    ("Amazon Web Services / MS Excel", ["AWS", "Excel"]),
    ("PowerBI,sklearn,Sql", ["Power BI", "Scikit-learn", "SQL"]),
    ("Python, terraform", ["Python", "Terraform"]),
    ("", []),
    (None, []),
])
def test_clean_skills(text, expected):
    assert clean_skills(text) == expected


@pytest.mark.parametrize("title, expected", [
    ("DATA ANALYST II", "Data Analyst II"),
    ("sr. data analyst", "Sr. Data Analyst"),
    ("LEAD ML ENGINEER", "Lead ML Engineer"),
    ("bi developer", "BI Developer"),
    ("Senior Data Engineer", "Senior Data Engineer"),
    ("  Data   Engineer ", "Data Engineer"),
])
def test_clean_title(title, expected):
    assert clean_title(title) == expected
