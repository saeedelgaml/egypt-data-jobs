# Router accuracy

The free router in `chatbot/router.py` picks one of nine answers from the words of a question. This page says how well it does, and how that was measured.

## How it was measured

A separate assistant, which had not seen the router's code, wrote questions in the voice of a student who types casually (typos, slang, a few Arabic words). For each question it also wrote the correct outcome: the answer and its filters, or "refuse". The router then ran on the whole set and every question was marked right or wrong. Right means the same answer and exactly the same filters. A refusal counts as right only when a refusal was expected.

Three sets were used, each written separately. The score on the first run, before any fix for that set, is the honest number:

| Set | Questions | Right on first run |
|---|---|---|
| 1 | 59 | 47 (80%) |
| 2 | 79 | 63 (80%) |
| 3 | 71 | 56 (79%) |

Arabic words written in Latin letters (Franco-Arabic, such as "kam wazifa") are not supported on purpose. Eleven such questions were removed from the sets, and the table above does not count them. Nine of those eleven were wrong on the first run.

## What was fixed afterwards

After each run the wrong cases were grouped and fixed by category, not one by one: slang and chat words, skill aliases, questions that must be refused (trends, advice, deleting data, contact details, unknown skills, companies and cities), and wording such as "the lowest 3 paying roles". After the fixes the three sets score 59/59, 77/79 and 70/71. Those later numbers are not an accuracy estimate, because the fixes were made by looking at those exact questions. They are kept as regression tests in `tests/test_router.py` so a fix cannot break an old case unnoticed. The remaining wrong cases are listed in that file.

## What to expect on new questions

On new wording the first-run results suggest about 80 percent right. Most wrong answers on the first runs were refusals of a question the router could not read, which is the safe direction. A smaller part were a wrong reading, which the "Understood as" line makes visible.

## Limits

- Every question set was written by an AI assistant, not by real users.
- All sets are about the same synthetic data, so none of this says anything about the real job market.
- The router cannot answer a question that none of the nine answers covers.
