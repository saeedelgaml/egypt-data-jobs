"""The search-only index published with the website: snippets only, no resume guide, rounded vectors."""
import json
from pathlib import Path

import pytest

from rag import export_site

INDEX_FILE = Path(__file__).resolve().parent.parent / "site" / "rag" / "index.json"


def test_snippet_keeps_only_the_first_words():
    text = " ".join(f"w{i}" for i in range(100))
    assert export_site.snippet(text).split()[:40] == [f"w{i}" for i in range(40)]
    assert len(export_site.snippet(text).split()) == 41  # 40 words and the ellipsis
    assert export_site.snippet("short text") == "short text"


@pytest.mark.skipif(not INDEX_FILE.exists(), reason="site/rag/index.json has not been exported")
def test_the_published_index_has_snippets_not_full_text():
    data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    assert data["model"] == "Xenova/all-MiniLM-L6-v2" and data["dimensions"] == 384 and data["chunks"]
    allowed = {"id", "source", "short", "title", "year", "page", "page_end", "snippet", "embedding", "url"}
    for chunk in data["chunks"]:
        assert set(chunk) <= allowed and "text" not in chunk
        assert len(chunk["snippet"].split()) <= 41
        assert len(chunk["embedding"]) == 384
        assert all(round(x, 3) == x for x in chunk["embedding"])
        assert chunk["source"] != "365ds-resume-guide"
        assert "url" not in chunk or chunk["url"].startswith("http")  # a missing link is omitted, never empty
    assert [c["id"] for c in data["chunks"]] == list(range(len(data["chunks"])))


@pytest.mark.skipif(not export_site.ROOT.joinpath("index", "chunks.json").exists(),
                    reason="rag/index is missing (CI has no documents)")
def test_export_leaves_out_the_resume_guide_and_full_text(tmp_path):
    data = export_site.build()
    assert {c["source"] for c in data["chunks"]} <= {"wef-fojr-2025", "eces-wp241", "ilo-swts-egypt", "wb-egypt-brief4"}
    chunks = json.loads((export_site.ROOT / "index" / "chunks.json").read_text(encoding="utf-8"))
    kept = sum(1 for c in chunks if c["source"] != "365ds-resume-guide")
    assert len(data["chunks"]) == kept
