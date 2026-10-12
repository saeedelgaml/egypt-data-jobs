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
