"""Ask the chatbot a question in plain English. Free: no key, no AI service.

Run from the project folder:
    python -m chatbot.chat "what does a data analyst earn in Cairo?"
    python -m chatbot.chat                     (type questions one by one, empty line to stop)

Optional smart mode, which sends only the question text to an AI service and needs a key
in a file named .env (see .env.example). It may cost money:
    python -m chatbot.chat --ai "what does a data analyst earn in Cairo?"

Local AI fallback (free, needs Ollama running with qwen2.5-coder:3b; skipped when Ollama is down):
a question that no fixed answer fits may get one checked, read-only SQL query written by the local
model. Turn it off with --no-local-ai.
"""
import sys

import duckdb

from chatbot.ai import answer_question
from db.schema import DEFAULT_DB_PATH


def main(argv=None, db_path=DEFAULT_DB_PATH, chooser=None, log_path=None, fallback="default"):
    args = list(sys.argv[1:] if argv is None else argv)
    use_ai = "--ai" in args
    no_local = "--no-local-ai" in args
    args = [a for a in args if a not in ("--ai", "--no-local-ai")]
    if not db_path.exists():
        print(f"No database at {db_path}. Run python run_pipeline.py first.")
        return 1
    log_path = log_path or (db_path.parent / "chat.log")

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        if fallback == "default":
            fallback = None
            if not no_local:
                from chatbot.local_ai import LocalAI
                fallback = LocalAI(con)
        if chooser is None:
            if use_ai:
                from dotenv import load_dotenv
                from chatbot.ai import AnthropicChooser, ChooserError
                load_dotenv()
                try:
                    chooser = AnthropicChooser()
                except ChooserError as problem:
                    print(problem)
                    return 1
            else:
                from chatbot.router import RuleRouter
                chooser = RuleRouter(con)
        if args:
            print(answer_question(con, " ".join(args), chooser, log_path, fallback)["text"])
        else:
            while True:
                try:
                    question = input("Question (empty line to stop): ").strip()
                except EOFError:
                    break
                if not question:
                    break
                print(answer_question(con, question, chooser, log_path, fallback)["text"] + "\n")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
