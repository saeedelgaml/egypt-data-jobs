"""Run the website's search in a real browser (headless Chromium via Playwright) on the test questions.

    python -m rag.calibrate_browser            # prints every score, the summary and which questions pass

The browser embeds each question with its own (quantised) copy of all-MiniLM-L6-v2, so its scores can differ a
little from the Python index; the website threshold (site/js/ragsearch.js) is calibrated here, separately.
Needs: pip install playwright && python -m playwright install chromium, network access for the model
download (once), and the exported site/rag/index.json plus the Python index (only to find the expected pages).
"""
import functools
import http.server
import json
import re
import socketserver
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
QUESTIONS = ROOT / "tests" / "rag_questions.json"
CHUNKS = ROOT / "rag" / "index" / "chunks.json"
EXCLUDED = {"365ds-resume-guide"}  # not in the website index on purpose


def squash(text):
    return re.sub(r"\s+", " ", text)


def expected_pages(item, chunks):
    """(source, first page, last page) of every chunk that holds the expected text."""
    return [(c["source"], c["page"], c["page_end"]) for c in chunks
            if c["source"] == item["source"] and all(n in squash(c["text"]) for n in item["contains"])]


def is_expected(hit_chunk, pages):
    return any(hit_chunk["source"] == s and hit_chunk["page"] <= last and hit_chunk["page_end"] >= first
               for s, first, last in pages)


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve():
    handler = functools.partial(_Quiet, directory=str(SITE))
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def run(questions, timeout_ms=600_000, headless=True):
    """{question: {'best': float, 'hits': [{'source','page','page_end','score'}]}} from the page's own search."""
    from playwright.sync_api import sync_playwright
    server = serve()
    results = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{server.server_address[1]}/rag.html")
            page.wait_for_selector("body[data-rag-ready=true]", state="attached", timeout=timeout_ms)
            for q in questions:
                r = page.evaluate("q => window.ragSearch(q)", q)
                results[q] = {"best": r["best"], "hits": [{"source": h["chunk"]["source"], "page": h["chunk"]["page"],
                                                          "page_end": h["chunk"]["page_end"], "score": h["score"]}
                                                         for h in r["hits"]]}
            browser.close()
        if errors:
            raise RuntimeError("page errors: " + "; ".join(errors))
    finally:
        server.shutdown()
    return results


def site_threshold():
    text = (SITE / "js" / "ragsearch.js").read_text(encoding="utf-8")
    return float(re.search(r"export const THRESHOLD = ([0-9.]+);", text).group(1))


def evaluate(scores, inside, chunks, threshold):
    """For every in-scope question: does the page cover it, and is the expected passage among its top 3?"""
    rows = []
    for item in inside:
        r = scores[item["q"]]
        pages = expected_pages(item, chunks)
        found = any(is_expected(h, pages) for h in r["hits"])
        rows.append({**item, "best": r["best"], "covered": r["best"] >= threshold, "found": found,
                     "passes": r["best"] >= threshold and found})
    return rows


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    data = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    chunks = json.loads(CHUNKS.read_text(encoding="utf-8"))
    inside = [i for i in data["in_scope"] if i["source"] not in EXCLUDED]
    skipped = [i for i in data["in_scope"] if i["source"] in EXCLUDED]
    pure, database = data["off_topic"], data.get("database_style", [])
    scores = run([i["q"] for i in data["in_scope"]] + pure + database)
    threshold = site_threshold()
    rows = evaluate(scores, inside, chunks, threshold)
    for r in sorted(rows, key=lambda r: r["best"]):
        print(f"IN   best={r['best']:.3f} covered={r['covered']} expected_in_top3={r['found']} "
              f"{'PASS' if r['passes'] else 'FAIL'}  [{r['kind']}] {r['q']}")
    for q in sorted(pure + database, key=lambda q: -scores[q]["best"]):
        kind = "off_topic" if q in pure else "database_style"
        print(f"OUT  best={scores[q]['best']:.3f} covered={scores[q]['best'] >= threshold}  [{kind}] {q}")
    for i in skipped:
        print(f"N/A  best={scores[i['q']]['best']:.3f} covered={scores[i['q']]['best'] >= threshold}  "
              f"[resume guide, not in the website index] {i['q']}")
    worst_in = min(r["best"] for r in rows)
    best_pure = max(scores[q]["best"] for q in pure)
    best_db = max(scores[q]["best"] for q in database)
    print(f"in-scope questions in the website index: {len(rows)}   off-topic: {len(pure)}   database-style: {len(database)}")
    print(f"worst in-scope best score: {worst_in:.3f}   best off-topic score: {best_pure:.3f}   "
          f"best database-style score: {best_db:.3f}")
    print(f"threshold in site/js/ragsearch.js: {threshold:.2f}: "
          f"{sum(r['covered'] for r in rows)}/{len(rows)} in-scope covered, "
          f"{sum(scores[q]['best'] >= threshold for q in pure)}/{len(pure)} off-topic covered, "
          f"{sum(scores[q]['best'] >= threshold for q in database)}/{len(database)} database-style covered")
    print(f"questions passing in the browser (covered and expected passage in the top 3): "
          f"{sum(r['passes'] for r in rows)}/{len(rows)}; originals {sum(r['passes'] for r in rows if r['kind'] == 'original')}/"
          f"{sum(r['kind'] == 'original' for r in rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
