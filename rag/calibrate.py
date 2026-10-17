"""Print the best retrieval score for every test question (used to choose the refusal threshold).
    python -m rag.calibrate
"""
import json
import re
import sys
from pathlib import Path

from rag.retrieve import index_available, search

QUESTIONS = Path(__file__).resolve().parent.parent / "tests" / "data" / "rag_questions.json"


def squash(text):
    return re.sub(r"\s+", " ", text)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not index_available():
        print("No index: put the documents in rag/docs/ and run python -m rag.ingest")
        return 1
    data = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    inside, outside = [], []
    for item in data["in_scope"]:
        hits = search(item["q"])
        rank = next((i + 1 for i, h in enumerate(hits) if h["source"] == item["source"]
                     and all(n in squash(h["text"]) for n in item["contains"])), None)
        inside.append(hits[0]["best_score"])
        print(f"IN   best={hits[0]['best_score']:.3f} top4_has_expected={rank is not None} rank={rank}  {item['q']}")
    for question in data["off_topic"]:
        best = search(question)[0]["best_score"]
        outside.append(best)
        print(f"OUT  best={best:.3f}  {question}")
    print(f"lowest in-scope best score: {min(inside):.3f}   highest off-topic best score: {max(outside):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
