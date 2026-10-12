"""The golden file that the JavaScript tests use must match what Python answers right now."""
import json
from pathlib import Path

import make_router_golden

GOLDEN = Path(make_router_golden.OUT)


def test_the_golden_file_is_up_to_date():
    fresh = json.loads(make_router_golden.build())
    committed = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert fresh == committed, "run: python make_router_golden.py  (then commit tests/data/router_golden.json)"


def test_the_golden_file_covers_every_role_and_both_kinds_of_outcome():
    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))["cases"]
    assert len(cases) > 250
    assert any(c["ok"] for c in cases) and any(not c["ok"] for c in cases)
    roles = {c["params"].get("role") for c in cases if c["ok"]}
    assert len(roles - {None}) >= 14
