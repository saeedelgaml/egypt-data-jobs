"""Run the natural phrasings through the router and list what fails.  python tests/phrasing_report.py"""
import json
import sys
from collections import Counter
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from chatbot.router import RuleRouter  # noqa: E402


def evaluate(router):
    rows = json.loads((ROOT / "tests" / "data" / "phrasings.json").read_text(encoding="utf-8"))
    results = []
    for question, function, params in rows:
        choice = router(question)
        given = choice.get("params") or {}
        ok = choice["function"] == function and all(given.get(k) == v for k, v in params.items())
        results.append((ok, question, function, params, choice))
    return results


if __name__ == "__main__":
    con = duckdb.connect(str(ROOT / "data" / "sample.duckdb"), read_only=True)
    results = evaluate(RuleRouter(con))
    passed = sum(r[0] for r in results)
    print(f"pass rate: {passed}/{len(results)} = {passed / len(results):.0%}")
    by_function = Counter(r[2] for r in results if not r[0])
    print("failures by expected function:", dict(by_function))
    for ok, question, function, params, choice in results:
        if not ok:
            print(f"- {question!r}: want {function} {params}; got {choice['function']} {choice.get('params')} "
                  f"hint={choice.get('hint')!r}")
