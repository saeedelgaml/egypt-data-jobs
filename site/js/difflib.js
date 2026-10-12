// A port of the part of Python's difflib that the router uses to fix typos:
// get_close_matches(word, possibilities, n=1, cutoff). Same matching rules, same tie-breaking,
// so a typo is repaired the same way in the browser as in Python.

function matchedCharacters(a, b) {
  const b2j = new Map();
  for (let j = 0; j < b.length; j++) {
    if (!b2j.has(b[j])) b2j.set(b[j], []);
    b2j.get(b[j]).push(j);
  }

  function longestMatch(alo, ahi, blo, bhi) {
    let besti = alo, bestj = blo, bestsize = 0;
    let j2len = new Map();
    for (let i = alo; i < ahi; i++) {
      const next = new Map();
      for (const j of b2j.get(a[i]) || []) {
        if (j < blo) continue;
        if (j >= bhi) break;
        const k = (j2len.get(j - 1) || 0) + 1;
        next.set(j, k);
        if (k > bestsize) { besti = i - k + 1; bestj = j - k + 1; bestsize = k; }
      }
      j2len = next;
    }
    return [besti, bestj, bestsize];
  }

  let matches = 0;
  const queue = [[0, a.length, 0, b.length]];
  while (queue.length) {
    const [alo, ahi, blo, bhi] = queue.pop();
    const [i, j, k] = longestMatch(alo, ahi, blo, bhi);
    if (k) {
      matches += k;
      if (alo < i && blo < j) queue.push([alo, i, blo, j]);
      if (i + k < ahi && j + k < bhi) queue.push([i + k, ahi, j + k, bhi]);
    }
  }
  return matches;
}

export function ratio(a, b) {
  const total = a.length + b.length;
  return total ? (2.0 * matchedCharacters(a, b)) / total : 1.0;
}

/** Number of single-letter inserts, deletes and changes that turn a into b. */
export function editDistance(a, b) {
  let previous = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const row = [i];
    for (let j = 1; j <= b.length; j++) {
      row.push(Math.min(previous[j] + 1, row[j - 1] + 1, previous[j - 1] + (a[i - 1] !== b[j - 1] ? 1 : 0)));
    }
    previous = row;
  }
  return previous[b.length];
}

/** The known word a misspelt word most likely means (same rule as chatbot/router.py closest_word). */
export function closestWord(word, vocabulary, cutoff) {
  const allowedEdits = word.length <= 5 ? 1 : 2;
  let best = null;
  for (const candidate of vocabulary) {
    if (Math.abs(candidate.length - word.length) > allowedEdits || editDistance(word, candidate) > allowedEdits) continue;
    const score = ratio(candidate, word);
    if (score >= cutoff && (best === null || score > best.score || (score === best.score && candidate > best.word))) {
      best = { score, word: candidate };
    }
  }
  return best ? best.word : null;
}

/** The best match at or above the cutoff, or null. Ties go to the larger string, as in Python. */
export function closeMatch(word, possibilities, cutoff = 0.6) {
  let best = null;
  for (const candidate of possibilities) {
    const score = ratio(candidate, word);
    if (score < cutoff) continue;
    if (best === null || score > best.score || (score === best.score && candidate > best.word)) {
      best = { score, word: candidate };
    }
  }
  return best ? best.word : null;
}
