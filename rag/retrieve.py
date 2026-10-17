"""Find the document passages that best match a question. Local only; no LLM is involved.

    python -m rag.retrieve "How many jobs will be created and displaced by 2030?"

The question is embedded with the same model as the chunks (all-MiniLM-L6-v2) and compared by cosine
similarity (the vectors are normalised, so a dot product). THRESHOLD is the lowest best-score at which
the chatbot treats a question as 'covered by the reports'.

Ranking is hybrid: the embedding ranking and a plain keyword (BM25) ranking are merged with reciprocal
rank fusion (equal weights, k=60). Embeddings alone ranked two of the seven test passages 8th and 12th,
because a long chunk full of figures embeds vaguely and "degree" or "experience" are exactly the words
the passage uses. Each hit's 'score' is still its cosine similarity, and 'best_score' (the highest cosine
over ALL chunks) is what the refusal threshold looks at, so keyword matches alone can never pass it.
"""
import json
import math
import os
import re
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

import numpy as np

INDEX = Path(os.environ.get("RAG_INDEX") or Path(__file__).resolve().parent / "index")
TOP_K = 4
# Chosen from python -m rag.calibrate on tests/rag_questions.json (45 in-scope questions and paraphrases, 12 off-topic,
# 10 database-style). Worst in-scope best score 0.341, best off-topic score 0.300, so 0.32 sits in the middle of that
# gap and never refuses an in-scope paraphrase. Database-style questions (0.37-0.52) cannot be separated from in-scope
# ones by score; they are caught earlier by the fixed answers and the keyword block, or later when the model replies
# "not covered" and the chatbot falls through to the SQL fallback.
THRESHOLD = 0.32


def index_available():
    return (INDEX / "chunks.json").exists() and (INDEX / "embeddings.npy").exists()


STOPWORDS = set("a an the of to in on for and or is are was were be do does did what how why which who when it its "
                "this that with as at by from about can will".split())
RRF_K = 60


def _tokens(text):
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS]


class _Bm25:
    def __init__(self, texts, k1=1.5, b=0.75):
        self.docs = [Counter(_tokens(t)) for t in texts]
        self.lengths = np.array([sum(d.values()) for d in self.docs], dtype=float)
        self.avg = self.lengths.mean()
        self.k1, self.b = k1, b
        df = Counter(w for d in self.docs for w in d)
        n = len(self.docs)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}

    def scores(self, question):
        out = np.zeros(len(self.docs))
        for word in set(_tokens(question)):
            if word not in self.idf:
                continue
            for i, doc in enumerate(self.docs):
                f = doc.get(word, 0)
                if f:
                    out[i] += self.idf[word] * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * self.lengths[i] / self.avg))
        return out


def _ranks(scores):
    order = np.argsort(-scores, kind="stable")
    ranks = np.empty(len(scores), dtype=int)
    ranks[order] = np.arange(1, len(scores) + 1)
    return ranks


@lru_cache(maxsize=1)
def _load():
    chunks = json.loads((INDEX / "chunks.json").read_text(encoding="utf-8"))
    vectors = np.load(INDEX / "embeddings.npy")
    meta = json.loads((INDEX / "meta.json").read_text(encoding="utf-8"))
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(meta["model"])
    model.max_seq_length = meta["max_seq_length"]
    return chunks, vectors, model, _Bm25([c["text"] for c in chunks])


def search(question, k=TOP_K):
    """The k best chunks, best first. Each hit has 'score' (its cosine similarity) and 'best_score'
    (the highest cosine over all chunks, used for the refusal threshold)."""
    chunks, vectors, model, keywords = _load()
    query = model.encode([question], normalize_embeddings=True, show_progress_bar=False)[0]
    dense = vectors @ query
    fused = 1 / (RRF_K + _ranks(dense))
    if keywords.scores(question).any():
        fused = fused + 1 / (RRF_K + _ranks(keywords.scores(question)))
    order = np.argsort(-fused, kind="stable")[:k]
    best = float(dense.max())
    return [{**chunks[i], "score": float(dense[i]), "best_score": best} for i in order]


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    question = " ".join(sys.argv[1:] if argv is None else argv)
    if not index_available():
        print("No index. Put the documents in rag/docs/ and run: python -m rag.ingest")
        return 1
    for hit in search(question):
        print(f"{hit['score']:.3f} (best {hit['best_score']:.3f})  {hit['source']} p.{hit['page']}  {hit['text'][:110]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
