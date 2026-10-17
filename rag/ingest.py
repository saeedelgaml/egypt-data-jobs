"""Turn the five documents in rag/docs/ into searchable chunks.

Run from the project folder:  python -m rag.ingest

For every source in rag/sources.json that is present in rag/docs/, the text is extracted (pypdf for
PDFs), cleaned, cut into chunks of about 250-350 words inside one page so the page citation stays
exact, embedded with sentence-transformers all-MiniLM-L6-v2 and saved to rag/index/ as chunks.json
and embeddings.npy. No vector database. Missing documents are skipped with a message.
Everything stays on this computer; the documents themselves are never committed.
"""
import json
import logging
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
INDEX = ROOT / "index"
SOURCES = ROOT / "sources.json"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MAX_SEQ_LENGTH = 512  # see PROFILES: MiniLM defaults to 256 word pieces, which cuts a 300-word chunk short

TARGET_WORDS = 300       # a chunk is closed once it has at least this many words (~250-350)
MAX_WORDS = 350
OVERLAP_WORDS = 40
MIN_PAGE_WORDS = 60      # a page with fewer words is merged into the next page
MAX_NUMERIC_SHARE = 0.5  # drop chunks that are mostly numbers (tables)

logging.getLogger("pypdf").setLevel(logging.ERROR)


def fix_hyphen_breaks(raw):
    """Join words that were split across lines with a hyphen ("unem-\nployment"), keep real hyphens."""
    return re.sub(r"(\w)-\s*\n\s*([a-z])", r"\1\2", raw)


def normalise(raw):
    return re.sub(r"\s+", " ", fix_hyphen_breaks(raw.replace("\r", "\n").replace("­", ""))).strip()


SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9•“\"(\[])")


def sentences(text):
    """Sentences, with any sentence over MAX_WORDS cut into word blocks."""
    out = []
    for sentence in SENTENCE_END.split(text):
        words = sentence.split()
        for i in range(0, len(words), MAX_WORDS):
            out.append(" ".join(words[i:i + MAX_WORDS]))
    return [s for s in out if s]


def overlap(current):
    """The last sentences of a finished chunk (about OVERLAP_WORDS words) that start the next one."""
    carry, total = [], 0
    for previous in reversed(current):
        if total >= OVERLAP_WORDS:
            break
        carry.insert(0, previous)
        total += len(previous.split())
    return carry, total


def chunk_page_text(text):
    """Cut one page of text into chunks of about TARGET_WORDS words with OVERLAP_WORDS of overlap."""
    units = sentences(text)
    chunks, current, count = [], [], 0
    for unit in units:
        n = len(unit.split())
        if current and count + n > MAX_WORDS:
            chunks.append(" ".join(current))
            current, count = overlap(current)
        current.append(unit)
        count += n
        if count >= TARGET_WORDS:
            chunks.append(" ".join(current))
            current, count = overlap(current)
    tail = " ".join(current)
    if tail and (not chunks or tail not in chunks[-1]):
        if chunks and len(tail.split()) < MIN_PAGE_WORDS:
            chunks[-1] = chunks[-1] + " " + tail  # a small tail stays with the chunk before it
        else:
            chunks.append(tail)
    return chunks


NUMBER_TOKEN = re.compile(r"^[~≈$€£(\[]*[\d][\d.,%–\-/)\]kKmMbB]*$")


def strip_number_runs(text, run=6):
    """Remove runs of `run` or more number-only tokens (table rows), so a table next to a paragraph does not
    get the paragraph dropped as 'mostly numbers'. Words in the table (row labels) stay."""
    tokens, out, i = text.split(), [], 0
    while i < len(tokens):
        j = i
        while j < len(tokens) and NUMBER_TOKEN.match(tokens[j]):
            j += 1
        if j - i >= run:
            i = j
        else:
            out.extend(tokens[i:max(j, i + 1)])
            i = max(j, i + 1)
    return " ".join(out)


def numeric_share(text):
    tokens = text.split()
    if not tokens:
        return 1.0
    numeric = sum(1 for t in tokens if re.search(r"\d", t) and not re.search(r"[A-Za-z]{3,}", t))
    return numeric / len(tokens)


def parse_pages(spec, total):
    """'1-111' -> (1, 111); '2-30' -> (2, 30); 'all' -> (1, total). 1-based, as a PDF viewer shows."""
    if spec == "all":
        return 1, total
    first, _, last = spec.partition("-")
    return int(first), min(int(last or first), total)


def read_pages(source):
    """[(page_number, text)] for one source, page numbers as a viewer shows them (1-based)."""
    path = DOCS / source["filename"]
    if path.suffix.lower() == ".txt":
        return [(1, normalise(path.read_text(encoding="utf-8")))]
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    first, last = parse_pages(source["pages"], len(reader.pages))
    return [(n, normalise(reader.pages[n - 1].extract_text() or "")) for n in range(first, last + 1)]


def chunks_for_source(source):
    """Chunks with exact page citations. Short pages are merged into the next page."""
    pages, pending, pending_from = read_pages(source), "", None
    out = []
    for number, text in pages:
        text = strip_number_runs(text)
        if len(text.split()) < MIN_PAGE_WORDS and number != pages[-1][0]:
            pending = (pending + " " + text).strip()
            pending_from = pending_from or number
            continue
        start = pending_from or number
        merged = (pending + " " + text).strip()
        pending, pending_from = "", None
        for piece in chunk_page_text(merged):
            if numeric_share(piece) < MAX_NUMERIC_SHARE and len(piece.split()) >= 20:
                out.append({"source": source["id"], "title": source["title"], "year": source["year"],
                            "page": start, "page_end": number, "text": piece})
    if pending:  # a short last page: keep it with the previous chunk's page
        out.append({"source": source["id"], "title": source["title"], "year": source["year"],
                    "page": pages[-1][0], "page_end": pages[-1][0], "text": pending})
    return out


def build():
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    chunks, counts, missing = [], {}, []
    for source in sources:
        if not (DOCS / source["filename"]).exists():
            missing.append(source["filename"])
            continue
        found = chunks_for_source(source)
        counts[source["id"]] = len(found)
        chunks.extend(found)
    for i, chunk in enumerate(chunks):
        chunk["id"] = i
    return chunks, counts, missing


# Chunking profiles: words per chunk (close at TARGET, never above MAX), overlap, and the embedding model's
# maximum sequence length (None keeps the model's own default of 256 word pieces).
PROFILES = {
    "large": {"target": 300, "max": 350, "overlap": 40, "seq": 512},
    "small": {"target": 170, "max": 200, "overlap": 25, "seq": None},
}
DEFAULT_PROFILE = "large"


def apply_profile(name):
    global TARGET_WORDS, MAX_WORDS, OVERLAP_WORDS, MAX_SEQ_LENGTH
    profile = PROFILES[name]
    TARGET_WORDS, MAX_WORDS, OVERLAP_WORDS, MAX_SEQ_LENGTH = (profile["target"], profile["max"],
                                                              profile["overlap"], profile["seq"])


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:] if argv is None else argv
    profile = args[args.index("--profile") + 1] if "--profile" in args else DEFAULT_PROFILE
    out = Path(args[args.index("--out") + 1]) if "--out" in args else INDEX
    apply_profile(profile)
    chunks, counts, missing = build()
    for name in missing:
        print(f"skipped (not in rag/docs/): {name}")
    if not chunks:
        print("No documents found in rag/docs/, nothing to index.")
        return 1
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_NAME)
    if MAX_SEQ_LENGTH:
        model.max_seq_length = MAX_SEQ_LENGTH
    meta_seq = model.max_seq_length
    vectors = model.encode([c["text"] for c in chunks], batch_size=32, normalize_embeddings=True,
                           show_progress_bar=False).astype(np.float32)
    out.mkdir(parents=True, exist_ok=True)
    (out / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False, indent=1), encoding="utf-8")
    np.save(out / "embeddings.npy", vectors)
    (out / "meta.json").write_text(json.dumps({"model": MODEL_NAME, "max_seq_length": meta_seq, "profile": profile,
                                               "normalized": True, "chunks": len(chunks)}), encoding="utf-8")
    for source_id, n in counts.items():
        print(f"{source_id}: {n} chunks")
    print(f"total: {len(chunks)} chunks, embeddings {vectors.shape}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
