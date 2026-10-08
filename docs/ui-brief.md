# Phase 10 brief: the web page

This file is the full brief for building the page. Read it all before writing code.

## Goal

A Streamlit page, `app.py` in the project root, where a visitor types a question about data-job postings in Egypt and gets a clear answer. Visitors are 18 to 45: students, fresh graduates, career switchers, recruiters. The page must look current and confident, and it must teach people how to ask, because most visitors do not know what the chatbot can answer.

All data is synthetic and the page must say so, visibly and without being annoying.

## Hard rules (a security reviewer will read the code)

1. The page calls only `chatbot.service`. It never opens the database itself, never writes SQL, never imports `chatbot.queries` or `chatbot.router` directly.
2. No API keys, no `.env`, no network calls from the page. The anthropic package is not used here.
3. Visitor text and database text are untrusted. Never put them inside HTML passed to `unsafe_allow_html=True`. Use `st.text`, `st.dataframe`, `st.write` on plain strings, or escape with `html.escape`. `unsafe_allow_html` is allowed only for CSS and markup that you wrote yourself.
4. Session id: create one `uuid.uuid4().hex` per visitor in `st.session_state` and pass it as `session` to `ask()`. Do not use IP addresses or anything personal.
5. Show the rate-limit message when `reply["limited"]` is true and disable the input for `retry_after` seconds.
6. Open the service once with `st.cache_resource`. Do not pass a database path from a URL parameter or a text box.
7. Do not log questions in the page. Logging belongs to the service (`log_path`).
8. Do not add a feature that is not in this brief without asking.

## The service you call

```python
from chatbot.service import Service
service = Service()                       # opens data/jobs.duckdb if it exists, else data/sample.duckdb
reply = service.ask("what does a data analyst earn in Cairo?", session=session_id)
facts = service.facts()
more = service.suggest("sal")             # up to 6 question suggestions while typing
```

`reply` always has these keys: `ok`, `text` (the full answer as plain text), `understood` (one line, how the question was read), `notes` (list of short honest limits), `function` and `params`, `data` (the numbers, see below), `follow_ups` (up to 3 questions that are guaranteed to work), `limited`, `retry_after`, `hint`, `tips` (list of how-to-ask tips with an example, filled when the question failed), `examples` (dict of grouped example questions, filled when the question failed).

`facts` has: `postings`, `with_salary`, `first_posted`, `last_posted`, `last_run`, `last_run_status`, `roles`, `cities`, `skills`, `synthetic_note`, `limits_note`.

Module constants you can import for static panels: `EXAMPLES` (dict group to list of questions), `HOW_TO_ASK` (list of dicts with `title`, `tip`, `example`).

### What `reply["data"]` contains, by `reply["function"]`

- `salary_for_role`: `typical`, `lowest`, `highest`, `with_salary`, `postings`, plus the filters (`role`, `city`, `skill`)
- `top_skills`: `skills` list of `{skill, postings, share}`, `postings_with_skills`
- `skills_with`: `skill`, `skills` list of `{skill, postings, share}`, `postings_with_skill`
- `top_companies`: `companies` list of `{company, postings}`
- `jobs_by_city`: `cities` list of `{city, postings}`, `no_city`
- `jobs_by_role`: `roles` list of `{role, postings}`
- `count_postings`: `total` plus filters and `min_salary`
- `top_paying`: `group_by`, `order`, `groups` list of `{group, typical, with_salary}`
- `new_postings`: `total`, `days`, `latest_date`, `postings` list of `{title, company, city, salary_min, salary_max, posted_date}`

Render these as native Streamlit elements: a big number for a salary, a horizontal bar chart for rankings, a table for postings (each posting also has `job_id` and `first_seen_date`; do not show those). Salaries are monthly EGP. When `data` is empty, show `reply["text"]`.

## Design direction

Trendy, youthful, confident. Think a modern product landing page, not a government form and not a default Streamlit app.

- Dark mode first with a clean light mode. One strong accent (a violet to cyan gradient is a good start), used on the hero, the main button and the chart bars. Everything else stays calm.
- A bold hero: one short headline, one line under it, and a large search box that is the first thing the eye lands on. The placeholder text cycles through real example questions.
- Rounded cards (16 to 20 px), soft shadows or glow, generous spacing, a bento-style grid for the facts and the how-to-ask tips.
- Type: one geometric sans (Plus Jakarta Sans or Inter through Google Fonts), large headings, small calm body text.
- Motion that helps: answers fade in, bars grow. Nothing flashy. Respect `prefers-reduced-motion`.
- Microcopy is friendly and short, no slang that dates quickly, no emoji spam (one or two where they carry meaning).
- Mobile first. Most 18 to 25 year olds will open it on a phone. The search box, chips and answers must work at 360 px wide.
- Contrast and keyboard use must pass WCAG AA. Charts must not rely on color alone.
- Arabic questions can be typed. Let the input and the echo line follow the text direction of what the visitor typed.

## Helping people search (the most important part)

1. Example chips under the box, grouped by `EXAMPLES` (Pay, Skills, Hiring, New). One click asks the question.
2. A short "How to ask" panel from `HOW_TO_ASK`: six tips, each with a clickable example. Collapsed by default after the first answer, open on first visit.
3. Live suggestions while typing, from `service.suggest()`. Debounce so it does not run on every keystroke.
4. An "Understood as" pill above every answer, from `reply["understood"]`, so people see how their question was read. Show `reply["notes"]` as small callouts below it.
5. Follow-up chips under every answer, from `reply["follow_ups"]`, titled "Ask next".
6. A friendly failure state: when `reply["ok"]` is false, show `reply["hint"]` or `reply["text"]`, then the tips and the grouped examples from the reply. Never show a blank error.
7. A small "What I can't do" line from `facts["limits_note"]`.
8. A facts strip: number of postings, date range, last pipeline run, and the synthetic note from `facts["synthetic_note"]`.

## Files and tests

- `app.py` (the page). Put CSS in `ui/style.css` and load it as a string; no inline style with user text.
- Add `streamlit` to `requirements.txt` without a version (versions are pinned in Phase 11).
- `tests/test_app.py`: use `streamlit.testing.v1.AppTest` to check that the page loads without exceptions, that clicking an example chip shows an answer, that a refused question shows tips, and that an empty submit shows the prompt. Also a source check: `app.py` must not import `duckdb`, `chatbot.queries`, `chatbot.router`, `anthropic` or `os.environ` secrets, and must not contain `unsafe_allow_html` next to any variable that holds visitor or database text.
- Run `pytest` before finishing. All existing tests must still pass.

## Running and deploying

- Local: `streamlit run app.py`.
- Public: Streamlit Community Cloud can deploy straight from the GitHub repo using `app.py`. It cannot see the real database on this computer, so it uses `data/sample.duckdb`, which is committed and fully synthetic. Rebuild it only when needed with `python make_sample_db.py`, because every rebuild adds a few MB to the git history.
- Do not deploy or push anything yourself. Prepare it and tell the owner which commands to run.

## Done means

The page runs locally, every example chip works, a refused question teaches the visitor what to ask, the layout holds at 360 px and at 1440 px, and the checklist in "Hard rules" is true.
