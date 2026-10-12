# Changes

| What changed | Why | File(s) |
|---|---|---|
| Role, city, skill, limit and example lists moved into one config | The same lists were repeated in 5 places | `config.py`, `db/schema.py`, `chatbot/{router,queries,service,ai}.py`, `clean/rules.py`, `mock_source/generator.py`, `ui/render.py` |
| 14 data roles (+ other) with skills, seniority levels, salary bands, title patterns and router aliases (AI eng, ML eng, LLM, ML ops, CV...) | Wider, more realistic market coverage; every role can be asked about | `config.py`, `clean/rules.py`, `chatbot/router.py`, `tests/test_roles.py`, updated cases in `tests/test_router.py`, `test_rules.py`, `test_queries.py`, blind sets (unknown-skill case now uses COBOL) |
| Skill splitting no longer breaks `CI/CD`; new skills and acronyms (NLP, MLOps, GenAI...) | "CI/CD" was becoming "CI" and "Cd" | `clean/rules.py`, `config.py` |
| Salary parser rejects other currencies, hourly pay and out-of-range amounts, converts yearly pay | Wrong numbers were silently accepted | `clean/rules.py`, `config.py`, `clean/cleaner.py` |
| Data-quality report (missing shares, probable reposts, warnings in the log) | A bad source is noticed the same day | `clean/quality.py`, `run_pipeline.py` |
| Failed runs are rows in `pipeline_runs` and never make the manager skip a day | Failures were only in a text file | `run_pipeline.py`, `tests/test_pipeline_quality.py` |
| `run_pipeline.py --export-site` | One scheduled command can refresh the website data | `run_pipeline.py` |
| Static website: page, styles, "Data last updated", honest synthetic-data footer, Insights (4 Chart.js charts with table fallbacks), loading/error/empty/"can't answer" states, mobile and dark mode, a11y basics, CSP that only allows itself and cdnjs | GitHub Pages is static; replaces Streamlit on localhost | `site/index.html`, `site/css/style.css`, `site/js/{app,render,insights}.js` |
| Browser chatbot: port of router, nine answers, text and follow-ups, with the same limits and value checks; regexes and word lists exported from Python | Free chatbot with no server; cannot drift from Python | `site/js/{router,queries,text,answer,difflib,pyfmt}.js`, `chatbot/router.py` (`export_config`) |
| Data export to one compact JSON (126 KB) | Static data file for the site | `export_site_data.py`, `site/data/jobs.json` |
| Golden-file parity tests (Python vs JS), JS safety tests, site tests | Proves the browser version answers identically and keeps the guard rules; no key or raw HTML in the site | `make_router_golden.py`, `tests/data/router_golden.json`, `tests/test_router_golden.py`, `tests/test_site.py`, `tests_js/*.test.js`, `package.json` |
| GitHub Actions: tests, then deploy `site/` to Pages on main | Automatic, tested deploys | `.github/workflows/pages.yml` |
| Requirements split into core, extras and dev | The pipeline no longer needs Streamlit or the AI SDK | `requirements*.txt` |
| 60-day sample database | Richer Insights | `make_sample_db.py`, `data/sample.duckdb` |
| README rewritten for a recruiter (badge, live link, synthetic-data statement, architecture) | Understand the project in 2 minutes | `README.md` |

Skipped as requested: re-measuring router accuracy (item 12). Not done on purpose: free-form SQL (none existed), client-side rate limiting, reposts are reported but not deleted (the synthetic data has no real reposts).
