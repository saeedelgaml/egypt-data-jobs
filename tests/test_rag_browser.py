"""The Reports page in a real browser (headless Chromium through Playwright). Slow: it downloads the search model
once, so it only runs with --runslow, and it skips when Playwright, the site index or the Python index are missing."""
import json

import pytest

pytest.importorskip("playwright")
from rag import calibrate_browser as cb  # noqa: E402


@pytest.mark.slow
def test_the_page_answers_every_in_scope_question_and_refuses_off_topic_ones():
    if not cb.CHUNKS.exists() or not (cb.SITE / "rag" / "index.json").exists():
        pytest.skip("needs rag/index (the documents) and site/rag/index.json")
    data = json.loads(cb.QUESTIONS.read_text(encoding="utf-8"))
    chunks = json.loads(cb.CHUNKS.read_text(encoding="utf-8"))
    inside = [i for i in data["in_scope"] if i["source"] not in cb.EXCLUDED]
    scores = cb.run([i["q"] for i in inside] + data["off_topic"])
    threshold = cb.site_threshold()
    rows = cb.evaluate(scores, inside, chunks, threshold)
    print({r["q"]: round(r["best"], 3) for r in rows})
    assert all(r["covered"] for r in rows), "an in-scope question was refused"
    assert all(scores[q]["best"] < threshold for q in data["off_topic"]), "an off-topic question was answered"
    assert sum(r["passes"] for r in rows) / len(rows) >= 0.65


@pytest.mark.slow
def test_the_form_shows_three_passages_with_a_link_and_the_not_covered_message():
    if not (cb.SITE / "rag" / "index.json").exists():
        pytest.skip("needs site/rag/index.json")
    from playwright.sync_api import sync_playwright
    server = cb.serve()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{server.server_address[1]}/rag.html")
            assert "Loading" in page.inner_text("#model-status") or page.locator("#model-status").is_hidden()
            page.wait_for_selector("body[data-rag-ready=true]", state="attached", timeout=600_000)
            page.fill("#q", "How many jobs will be created and displaced by 2030?")
            page.click("button[type=submit]")
            page.wait_for_selector(".passage")
            assert page.locator(".passage").count() == 3
            assert "From the reports" in page.inner_text("#answer")
            assert "Search-only demo. The full cited-answer version runs locally." in page.inner_text("#answer")
            assert page.locator(".passage a[href^='https://www.weforum.org']").count() >= 1
            page.fill("#q", "give me a recipe for koshary")
            page.click("button[type=submit]")
            page.wait_for_selector("text=The documents don't cover that.")
            assert page.locator(".passage").count() == 0
            browser.close()
    finally:
        server.shutdown()
