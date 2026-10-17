// Search over the exported report passages. Pure functions (no browser APIs), so Node can test them.
// The vectors are normalised, so cosine similarity is a dot product.

// Lowest best-score at which a question counts as covered by the reports. Calibrated in the browser, on the
// browser's own (quantised) model with tests/rag_questions.json (python -m rag.calibrate_browser): worst in-scope best
// score 0.351, best off-topic score 0.306, so 0.33 is the middle of that gap. Python uses 0.32 on its own scores.
export const THRESHOLD = 0.33;
export const TOP_K = 3;
export const NOT_COVERED = "The documents don't cover that.";

export function dot(a, b) {
  let sum = 0;
  for (let i = 0; i < a.length; i++) sum += a[i] * b[i];
  return sum;
}

/** The k chunks closest to the question vector, best first, each with its cosine score. */
export function topChunks(queryVector, chunks, k = TOP_K) {
  return chunks
    .map((chunk) => ({ chunk, score: dot(queryVector, chunk.embedding) }))
    .sort((a, b) => b.score - a.score || a.chunk.id - b.chunk.id)
    .slice(0, k);
}

/** {covered, hits}: covered is false when even the best passage scores below the threshold. */
export function search(queryVector, chunks, threshold = THRESHOLD, k = TOP_K) {
  const hits = topChunks(queryVector, chunks, k);
  return { covered: hits.length > 0 && hits[0].score >= threshold, hits, best: hits.length ? hits[0].score : 0 };
}

export function pagesText(chunk) {
  return chunk.page === chunk.page_end ? `p. ${chunk.page}` : `pp. ${chunk.page}-${chunk.page_end}`;
}
