"""Export a search-only index for the public website: site/rag/index.json.

    python -m rag.export_site

For every chunk the file holds its source, title, year, link, PDF page, a snippet of the first ~40 words
and the embedding rounded to 3 decimals. The full chunk text is never exported, and the resume guide
(365ds-resume-guide) is left out. The browser embeds a question with the same model (all-MiniLM-L6-v2) and
compares it with these vectors; it can show where the reports talk about something, but it cannot write answers.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
SITE_OUT = ROOT.parent / "site" / "rag" / "index.json"
EXCLUDED_SOURCES = {"365ds-resume-guide"}
SNIPPET_WORDS = 40
DECIMALS = 3


def snippet(text, words=SNIPPET_WORDS):
    parts = text.split()
    return " ".join(parts[:words]) + (" ..." if len(parts) > words else "")


def build(index_dir=None):
    index = Path(index_dir) if index_dir else ROOT / "index"
    chunks = json.loads((index / "chunks.json").read_text(encoding="utf-8"))
    vectors = np.load(index / "embeddings.npy")
    meta = json.loads((index / "meta.json").read_text(encoding="utf-8"))
    sources = {s["id"]: s for s in json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))}
    out = []
    for chunk, vector in zip(chunks, vectors):
        if chunk["source"] in EXCLUDED_SOURCES:
            continue
        source = sources[chunk["source"]]
        item = {"id": len(out), "source": chunk["source"], "short": source["short"], "title": chunk["title"],
                "year": chunk["year"], "page": chunk["page"], "page_end": chunk["page_end"],
                "snippet": snippet(chunk["text"]),
                "embedding": [round(float(x), DECIMALS) for x in vector]}
        if source["url"]:
            item["url"] = source["url"]
        out.append(item)
    return {"model": "Xenova/all-MiniLM-L6-v2", "python_model": meta["model"], "max_seq_length": meta["max_seq_length"],
            "dimensions": int(vectors.shape[1]), "normalized": True, "chunks": out}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    data = build()
    SITE_OUT.parent.mkdir(parents=True, exist_ok=True)
    SITE_OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    sources = sorted({c["source"] for c in data["chunks"]})
    print(f"Wrote {SITE_OUT}: {len(data['chunks'])} chunks from {len(sources)} sources, "
          f"{SITE_OUT.stat().st_size / 1024:.0f} KB ({SITE_OUT.stat().st_size / 1024 / 1024:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
