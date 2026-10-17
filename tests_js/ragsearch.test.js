// The search-only Reports page: scoring, ordering and the threshold decision (no browser or model needed).
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dot, NOT_COVERED, pagesText, search, THRESHOLD, topChunks } from "../site/js/ragsearch.js";

const chunks = [
  { id: 0, embedding: [1, 0], page: 3, page_end: 3 },
  { id: 1, embedding: [0.6, 0.8], page: 4, page_end: 5 },
  { id: 2, embedding: [0, 1], page: 9, page_end: 9 },
  { id: 3, embedding: [0.6, 0.8], page: 10, page_end: 10 },
];

test("cosine of normalised vectors is a dot product", () => {
  assert.equal(dot([1, 0], [0.6, 0.8]), 0.6);
});

test("the top three come back best first, ties by id", () => {
  const hits = topChunks([0.6, 0.8], chunks);
  assert.deepEqual(hits.map((h) => h.chunk.id), [1, 3, 2]);
  assert.ok(hits[0].score >= hits[1].score && hits[1].score >= hits[2].score);
});

test("below the threshold the question is not covered", () => {
  const near = search([1, 0], chunks, 0.9);
  assert.equal(near.covered, true);
  assert.equal(near.hits.length, 3);
  const far = search([0, -1], chunks, 0.2);
  assert.equal(far.covered, false);
  assert.equal(NOT_COVERED, "The documents don't cover that.");
});

test("the threshold is the calibrated one and an empty index never covers", () => {
  assert.equal(THRESHOLD, 0.33);
  assert.equal(search([1, 0], []).covered, false);
});

test("page labels", () => {
  assert.equal(pagesText(chunks[0]), "p. 3");
  assert.equal(pagesText(chunks[1]), "pp. 4-5");
});

test("the page pins the library version, forbids eval and only shows snippets", () => {
  const page = readFileSync(new URL("../site/rag.html", import.meta.url), "utf8");
  const code = readFileSync(new URL("../site/js/rag.js", import.meta.url), "utf8");
  assert.match(code, /@xenova\/transformers@2\.17\.2\//);
  assert.match(code, /Xenova\/all-MiniLM-L6-v2/);
  assert.match(code, /pooling: "mean", normalize: true/);
  assert.doesNotMatch(page, /(?<!wasm-)unsafe-eval/); // only WebAssembly may compile, never strings
  assert.match(page, /Search-only demo\. The full cited-answer version runs locally\./);
});
