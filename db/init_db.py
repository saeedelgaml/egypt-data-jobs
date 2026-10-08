"""Create the database and print what is in it.

Run from the project folder:  python -m db.init_db
"""
from db.schema import DEFAULT_DB_PATH, connect, create_tables, table_names


def main():
    con = connect()
    create_tables(con)
    print("Database file:", DEFAULT_DB_PATH)
    for name in table_names(con):
        count = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        print(f"  {name}: {count} rows")
    con.close()


if __name__ == "__main__":
    main()
