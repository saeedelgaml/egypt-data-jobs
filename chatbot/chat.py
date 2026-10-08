"""Ask the chatbot a question in plain English.

Run from the project folder, after putting your key in a file named .env:
    python -m chatbot.chat "what does a data analyst earn in Cairo?"
    python -m chatbot.chat                     (type questions one by one, empty line to stop)
"""
import sys

import duckdb
from dotenv import load_dotenv

from chatbot.ai import AnthropicChooser, ChooserError, answer_question
from db.schema import DEFAULT_DB_PATH


def main(argv=None, db_path=DEFAULT_DB_PATH, chooser=None, log_path=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not db_path.exists():
        print(f"No database at {db_path}. Run python run_pipeline.py first.")
        return 1
    if chooser is None:
        load_dotenv()
        try:
            chooser = AnthropicChooser()
        except ChooserError as problem:
            print(problem)
            return 1
    log_path = log_path or (db_path.parent / "chat.log")

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        if args:
            print(answer_question(con, " ".join(args), chooser, log_path)["text"])
        else:
            while True:
                question = input("Question (empty line to stop): ").strip()
                if not question:
                    break
                print(answer_question(con, question, chooser, log_path)["text"] + "\n")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
