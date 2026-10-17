"""Print the best retrieval score for every test question and where each expected passage ranks.

    python -m rag.calibrate                  # uses rag/index (or the folder in the RAG_INDEX variable)
    python -m rag.calibrate --quiet          # only the summary

The refusal threshold in rag/retrieve.py is chosen from this summary: it must sit above the best
off-topic score and, ideally, below the worst in-scope score. When the two ranges overlap the numbers
are printed instead of being tuned away.
"""
import json
import re
import sys
from pathlib import Path

from rag import retrieve

QUESTIONS = Path(__file__).resolve().parent.parent / "tests" / "rag_questions.json"


def squash(text):
    return re.sub(r"\s+", " ", text)


def expected_rank(item, ranked):
    """1-based position of the first hit that is the expected source and holds the expected text, else None."""
    return next((i + 1 for i, h in enumerate(ranked) if h["source"] == item["source"]
                 and all(n in squash(h["text"]) for n in item["contains"])), None)


def evaluate(questions=None, depth=60):
    """Scores for every question: in-scope items get 'best' and 'rank' (within `depth`), off-topic get 'best'."""
    data = json.loads(QUESTIONS.read_text(encoding="utf-8")) if questions is None else questions
    inside = []
    for item in data["in_scope"]:
        hits = retrieve.search(item["q"], k=depth)
        inside.append({**item, "best": hits[0]["best_score"], "rank": expected_rank(item, hits)})
    outside = [{"q": q, "kind": kind, "best": retrieve.search(q, k=1)[0]["best_score"]}
               for kind in ("off_topic", "database_style") for q in data.get(kind, [])]
    return inside, outside


def summary(inside, outside, threshold=None):
    worst_in = min(r["best"] for r in inside)
    pure = max(r["best"] for r in outside if r["kind"] == "off_topic")
    lines = [f"in-scope questions: {len(inside)}   off-topic: {sum(r['kind'] == 'off_topic' for r in outside)}   "
             f"database-style: {sum(r['kind'] == 'database_style' for r in outside)}",
             f"worst in-scope best score: {worst_in:.3f}   best off-topic score: {pure:.3f}   "
             f"best database-style score: {max(r['best'] for r in outside if r['kind'] == 'database_style'):.3f}"]
    if threshold is not None:
        lines.append(f"at threshold {threshold:.2f}: {sum(r['best'] >= threshold for r in inside)} in-scope pass, "
                     f"{sum(r['best'] < threshold for r in inside)} in-scope refused; "
                     f"{sum(r['best'] >= threshold for r in outside)} off-topic pass, "
                     f"{sum(r['best'] < threshold for r in outside)} off-topic refused")
    ranks = [r["rank"] for r in inside]
    lines.append(f"expected passage in top 4: {sum(1 for r in ranks if r and r <= 4)}/{len(ranks)}   "
                 f"found at all (within 60): {sum(1 for r in ranks if r)}/{len(ranks)}")
    return lines


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:] if argv is None else argv
    if not retrieve.index_available():
        print("No index: put the documents in rag/docs/ and run python -m rag.ingest")
        return 1
    inside, outside = evaluate()
    if "--quiet" not in args:
        for r in sorted(inside, key=lambda r: r["best"]):
            print(f"IN   best={r['best']:.3f} rank={r['rank']}  [{r['kind']}] {r['q']}")
        for r in sorted(outside, key=lambda r: -r["best"]):
            print(f"OUT  best={r['best']:.3f}  [{r['kind']}] {r['q']}")
    for line in summary(inside, outside, retrieve.THRESHOLD):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
