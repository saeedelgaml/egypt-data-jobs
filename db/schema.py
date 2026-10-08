"""Table definitions for the jobs database (DuckDB)."""
from pathlib import Path

import duckdb

DEFAULT_DB_PATH = Path("data") / "jobs.duckdb"

# The fixed list of roles. Each role is stored once. Cleaning maps messy
# titles such as "sr data engineer" onto one of these names.
SEED_ROLES = [
    "data_engineer",
    "data_analyst",
    "data_scientist",
    "ml_engineer",
    "bi_developer",
    "other",
]

# raw_jobs keeps postings exactly as collected: messy text, duplicates allowed.
RAW_JOBS = """
CREATE TABLE IF NOT EXISTS raw_jobs (
    source_job_id VARCHAR,
    title         VARCHAR,
    company       VARCHAR,
    city          VARCHAR,
    salary_text   VARCHAR,
    skills_text   VARCHAR,
    posted_date   DATE,
    collected_on  DATE
)
"""

# roles lists each role exactly once.
ROLES = """
CREATE TABLE IF NOT EXISTS roles (
    role VARCHAR PRIMARY KEY
)
"""

# skills lists each skill exactly once. A new skill is added here the first
# time any job mentions it (see add_skill).
SKILLS = """
CREATE TABLE IF NOT EXISTS skills (
    skill VARCHAR PRIMARY KEY
)
"""

# jobs holds one cleaned row per posting. job_id is the key, so a posting
# that shows up again on a later day cannot be stored twice. The role must
# exist in the roles table.
JOBS = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id          VARCHAR PRIMARY KEY,
    title           VARCHAR,
    role            VARCHAR REFERENCES roles (role),
    company         VARCHAR,
    city            VARCHAR,
    salary_min      INTEGER,
    salary_max      INTEGER,
    salary_currency VARCHAR DEFAULT 'EGP',
    posted_date     DATE,
    first_seen_date DATE
)
"""

# job_skills links a job to each of its skills, one row per pair.
JOB_SKILLS = """
CREATE TABLE IF NOT EXISTS job_skills (
    job_id VARCHAR REFERENCES jobs (job_id),
    skill  VARCHAR REFERENCES skills (skill),
    PRIMARY KEY (job_id, skill)
)
"""

# pipeline_runs logs every daily run, so a bad day is easy to spot.
PIPELINE_RUNS = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_date       DATE,
    rows_collected INTEGER,
    rows_new       INTEGER,
    rows_duplicate INTEGER,
    status         VARCHAR,
    run_at         TIMESTAMP DEFAULT current_timestamp
)
"""

# Order matters: a table must exist before another table points at it.
ALL_TABLES = [RAW_JOBS, ROLES, SKILLS, JOBS, JOB_SKILLS, PIPELINE_RUNS]


def connect(path=DEFAULT_DB_PATH):
    """Open the database file, creating the data folder if needed."""
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


def create_tables(con):
    """Create every table and the fixed roles. Safe to run more than once."""
    for sql in ALL_TABLES:
        con.execute(sql)
    for role in SEED_ROLES:
        con.execute("INSERT OR IGNORE INTO roles VALUES (?)", [role])


def add_skill(con, skill):
    """Add a skill to the skills table if it is new. Does nothing otherwise."""
    con.execute("INSERT OR IGNORE INTO skills VALUES (?)", [skill])


def table_names(con):
    """Return the sorted names of the tables in the database."""
    return sorted(row[0] for row in con.execute("SHOW TABLES").fetchall())
