"""Find which excerpt really supports each sentence of a written answer, and the sentence that proves it.

A small model often cites the wrong excerpt ([1] when the fact is in [3]). So the model's own [n] is only a
tie-breaker: the code looks for the excerpt that contains the sentence's numbers (or, for a sentence with no
numbers, shares the most key words), cites that one, and quotes the supporting sentence as evidence.
"""
import re

CITATION = re.compile(r"\s*\[(\d+(?:\s*[,;]\s*\d+)*)\]")
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
STOPWORDS = set("a an the of to in on for and or is are was were be been do does did what how why which who when it its "
                "this that with as at by from about can will than then there their they them have has had not no".split())
EVIDENCE_WORDS = 60


def squash(text):
    return re.sub(r"\s+", " ", text).strip()


def numbers_in(text):
    """The numbers of a text as plain strings ('92', '89.6', '2030'); commas and % signs are dropped."""
    return {n.replace(",", "") for n in NUMBER.findall(CITATION.sub(" ", text))}


def words_in(text):
    return {w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in STOPWORDS}


def split_sentences(text):
    return [s for s in SENTENCE_END.split(squash(text)) if s]


def cited_numbers(sentence):
    """The excerpt numbers the model named for a sentence, e.g. [1, 2] -> [1, 2]."""
    return [int(n) for group in CITATION.findall(sentence) for n in re.findall(r"\d+", group)]


def support_for(sentence, excerpts, model_picks=()):
    """Index of the excerpt that best supports the sentence, or None.

    A sentence with numbers goes to the excerpt holding the most of them (the model's pick wins a tie); a
    sentence without numbers goes to the excerpt sharing the most key words (at least 3)."""
    numbers = numbers_in(sentence)
    if numbers:
        counts = [len(numbers & numbers_in(e)) for e in excerpts]
        best = max(counts)
        if best:
            tied = [i for i, c in enumerate(counts) if c == best]
            return next((i for i in tied if i + 1 in model_picks), tied[0])
        return None
    words = words_in(sentence)
    overlaps = [len(words & words_in(e)) for e in excerpts]
    best = max(overlaps) if overlaps else 0
    if best < 3:
        return None
    tied = [i for i, c in enumerate(overlaps) if c == best]
    return next((i for i in tied if i + 1 in model_picks), tied[0])


def evidence_for(sentences, excerpt):
    """The one or two consecutive sentences of the excerpt that hold most of the answer's numbers (or key words)."""
    wanted_numbers = set().union(*(numbers_in(s) for s in sentences)) if sentences else set()
    wanted_words = set().union(*(words_in(s) for s in sentences)) if sentences else set()
    parts = split_sentences(excerpt)
    best, best_score = parts[:1], (-1, -1)
    for i in range(len(parts)):
        for size in (1, 2):
            window = parts[i:i + size]
            if len(window) < size:
                continue
            text = " ".join(window)
            score = (len(wanted_numbers & numbers_in(text)), len(wanted_words & words_in(text)) - 0.01 * size)
            if score > best_score:
                best, best_score = window, score
    return " ".join(" ".join(best).split()[:EVIDENCE_WORDS * 2])


def attribute(reply, hits, label_of):
    """(text with code-chosen citations, [(excerpt index, evidence sentence)]) for a model reply.

    label_of(hit) gives the citation label such as 'WEF 2025, p.18'. A sentence goes to the excerpt that holds its
    numbers (or key words). Only when nothing supports it are the model's own [n] kept (those that exist);
    a sentence with neither is left uncited, and an answer with no citation at all is attributed to excerpt 1."""
    excerpts = [h["text"] for h in hits]
    sentences = split_sentences(reply)
    plain_sentences = [CITATION.sub("", s).strip() for s in sentences]
    chosen = []
    for sentence, plain in zip(sentences, plain_sentences):
        picks = cited_numbers(sentence)
        index = support_for(plain, excerpts, picks)
        chosen.append([index] if index is not None else
                      [n - 1 for n in dict.fromkeys(picks) if 1 <= n <= len(hits)])
    if not any(chosen):
        chosen[-1:] = [[0]]
    out, used = [], {}
    for sentence, plain, indexes in zip(sentences, plain_sentences, chosen):
        for i in indexes:
            used.setdefault(i, []).append(plain)
        if not indexes:
            out.append(plain)
            continue
        label = "; ".join(label_of(hits[i]) for i in indexes)
        if cited_numbers(sentence):  # the model cited: put the code's citation where its mark was
            stem = plain.rstrip(".!? ")
            out.append(f"{stem} [{label}]{plain[len(stem):].strip()}")
        else:
            out.append(f"{plain} [{label}]")
    evidence = [(i, evidence_for(parts, excerpts[i])) for i, parts in used.items()]
    return " ".join(out), evidence
