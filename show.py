"""Print the first rows of a table in the jobs database.

Usage:  python show.py raw_jobs
        python show.py raw_jobs 20
        python show.py            (lists the tables)
"""
import sys

import duckdb

from db.schema import DEFAULT_DB_PATH, table_names


def main():
    sys.stdout.reconfigure(errors="replace")
    con = duckdb.connect(str(DEFAULT_DB_PATH), read_only=True)
    names = table_names(con)
    if len(sys.argv) < 2 or sys.argv[1] not in names:
        print("Tables:", ", ".join(names))
        print("Usage: python show.py <table> [rows]")
        return
    table = sys.argv[1]
    rows = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    total = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"{table}: {total} rows, showing up to {rows}")
    print(con.sql(f"SELECT * FROM {table} LIMIT {rows}"))
    con.close()


if __name__ == "__main__":
    main()