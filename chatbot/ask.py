"""Try the answers from the command line, with no AI involved.

Run from the project folder:
    python -m chatbot.ask                                  (list the answers)
    python -m chatbot.ask top_skills role=data_engineer limit=3
    python -m chatbot.ask salary_for_role role=data_analyst city=Cairo
"""
import sys

import duckdb

from chatbot.queries import DESCRIPTIONS, run
from chatbot.text import to_text
from db.schema import DEFAULT_DB_PATH


def _parse(pairs):
    params = {}
    for pair in pairs:
        key, _, value = pair.partition("=")
        params[key] = int(value) if value.isdigit() else value
    return params


def main(argv=None, db_path=DEFAULT_DB_PATH):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("Answers I can give:")
        for name, text in DESCRIPTIONS.items():
            print(f"  {name}: {text}")
        return 0
    if not db_path.exists():
        print(f"No database at {db_path}. Run python run_pipeline.py first.")
        return 1
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        print(to_text(run(con, args[0], _parse(args[1:]))))
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
