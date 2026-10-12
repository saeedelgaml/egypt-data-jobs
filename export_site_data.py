"""Export the cleaned data to one compact JSON file for the static website.

Run from the project folder after the daily pipeline:
    python export_site_data.py                      (uses data/jobs.duckdb, else data/sample.duckdb)
    python export_site_data.py --db data/sample.duckdb --out site/data/jobs.json

The file holds the job rows, the skill list and the router settings. GitHub Pages serves it as
a plain file and the page answers questions in the browser, so no server, database or key is
needed. Only read-only SELECTs are run here, and nothing in the file is secret.
"""
import argparse
import json
import sys
from pathlib import Path

import duckdb

import config
from chatbot import router as router_module
from chatbot.ai import HELP
from chatbot.service import LIMITS_NOTE, SYNTHETIC_NOTE, default_db_path

DEFAULT_OUT = Path(__file__).parent / "site" / "data" / "jobs.json"
SOURCE = "mock_source/generator.py"
JOB_COLUMNS = ["job_id", "title", "role", "company", "city", "salary_min", "salary_max",
               "posted_date", "first_seen_date", "skills"]


def build_payload(con):
    """The whole payload as plain Python data (dates as ISO text)."""
    skills_of = {}
    for job_id, skill in con.execute("SELECT job_id, skill FROM job_skills ORDER BY job_id, skill").fetchall():
        skills_of.setdefault(job_id, []).append(skill)
    rows = [
        [job_id, title, role, company, city, low, high, str(posted), str(seen), skills_of.get(job_id, [])]
        for job_id, title, role, company, city, low, high, posted, seen in con.execute(
            "SELECT job_id, title, role, company, city, salary_min, salary_max, posted_date, first_seen_date "
            "FROM jobs ORDER BY job_id").fetchall()
    ]
    skills = [r[0] for r in con.execute("SELECT skill FROM skills ORDER BY skill").fetchall()]
    last_run = con.execute(
        "SELECT run_date, status FROM pipeline_runs WHERE status <> 'failed' "
        "ORDER BY run_date DESC, run_at DESC LIMIT 1").fetchone()
    first_posted, last_posted, last_seen = con.execute(
        "SELECT MIN(posted_date), MAX(posted_date), MAX(first_seen_date) FROM jobs").fetchone()
    updated = last_run[0] if last_run else last_seen
    meta = {
        "data_last_updated": str(updated) if updated else None,
        "last_posted": str(last_posted) if last_posted else None,
        "first_posted": str(first_posted) if first_posted else None,
        "postings": len(rows),
        "with_salary": sum(1 for r in rows if r[5] is not None),
        "synthetic": True,
        "source": SOURCE,
        "synthetic_note": SYNTHETIC_NOTE,
        "limits_note": LIMITS_NOTE,
    }
    roles = [{"key": key, "label": spec["label"], "plural": spec["plural"]} for key, spec in config.ROLES.items()]
    return {
        "meta": meta,
        "config": {
            "max_limit": config.MAX_LIMIT, "max_days": config.MAX_DAYS, "max_salary": config.MAX_SALARY,
            "min_group": config.MIN_GROUP, "company_not_disclosed": config.COMPANY_NOT_DISCLOSED, "max_question_chars": config.MAX_QUESTION_CHARS,
            "cities": config.CITIES, "roles": roles, "plural": config.PLURAL,
            "examples": config.EXAMPLES, "generic": config.GENERIC_QUESTIONS, "how_to_ask": config.HOW_TO_ASK, "help": HELP,
            "router": router_module.export_config(),
        },
        "skills": skills,
        "columns": JOB_COLUMNS,
        "jobs": rows,
    }


def export(db_path, out_path):
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        payload = build_payload(con)
    finally:
        con.close()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return payload["meta"], out_path.stat().st_size


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export the cleaned data for the static website.")
    parser.add_argument("--db", default=None, help="database file (default: data/jobs.duckdb, else the sample)")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="where to write the JSON file")
    args = parser.parse_args(argv)
    meta, size = export(args.db or default_db_path(), args.out)
    print(f"Wrote {args.out}: {meta['postings']} postings, data last updated {meta['data_last_updated']}, "
          f"{size // 1024} KB.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
