"""The static website: honest about the data, no keys, and fed by export_site_data.py."""
import json
import re
from datetime import date
from pathlib import Path

import export_site_data
import make_sample_db

SITE = Path(__file__).resolve().parent.parent / "site"
PAGE = (SITE / "index.html").read_text(encoding="utf-8")


def test_the_page_says_the_data_is_synthetic_and_the_pipeline_is_ready_for_real_data():
    assert "All data is synthetic" in PAGE
    assert "mock_source/generator.py" in PAGE
    assert "accept a real job source later" in PAGE
    assert "Data last updated" in PAGE


def test_the_page_can_only_talk_to_itself_and_chartjs():
    csp = re.search(r'Content-Security-Policy" content="([^"]+)"', PAGE).group(1)
    assert "connect-src 'self'" in csp and "default-src 'none'" in csp
    assert "https://cdnjs.cloudflare.com" in csp
    scripts = re.findall(r'<script[^>]+src="([^"]+)"', PAGE)
    assert [s for s in scripts if s.startswith("http")] == [
        "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"]
    assert 'integrity="sha384-' in PAGE


def test_no_key_or_ai_code_is_published_with_the_site():
    forbidden = re.compile(r"LLM_API_KEY|anthropic|api[_-]?key|sk-[A-Za-z0-9_-]{20,}|Bearer ", re.IGNORECASE)
    for path in SITE.rglob("*"):
        if path.is_file():
            assert not forbidden.search(path.read_text(encoding="utf-8")), path


def test_the_published_data_file_is_complete():
    data = json.loads((SITE / "data" / "jobs.json").read_text(encoding="utf-8"))
    assert data["meta"]["synthetic"] is True and data["meta"]["source"] == "mock_source/generator.py"
    assert date.fromisoformat(data["meta"]["data_last_updated"])
    assert data["meta"]["postings"] == len(data["jobs"]) > 100
    assert all(len(row) == len(data["columns"]) for row in data["jobs"])
    assert len(data["config"]["roles"]) >= 15 and "router" in data["config"]


def test_export_writes_a_file_the_page_can_read(tmp_path):
    db, out = tmp_path / "small.duckdb", tmp_path / "out" / "jobs.json"
    assert make_sample_db.build(db, days=4) > 20
    meta, size = export_site_data.export(db, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert meta["postings"] == len(data["jobs"]) and size == out.stat().st_size
    assert meta["data_last_updated"] == "2026-10-04"
    assert set(data) == {"meta", "config", "skills", "columns", "jobs"}
    assert data["config"]["router"]["patterns"]["SALARY"]
