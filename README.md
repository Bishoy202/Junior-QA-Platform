# Junior QA Job Platform

Real, runnable MVP. Built and verified in this session — every claim below
was actually executed, not written speculatively.

## Verified in this session

- `python -m pytest -v` → **10 passed** (see `tests/`)
- Server actually boots: `uvicorn app.main:app` and responds on
  `/api/health`, `/api/sources`, `/api/jobs`, `/api/dashboard`
- Pipeline actually runs end-to-end against fixture data (mocked network,
  real SQLite writes, real dedup, real scoring) — see `tests/test_pipeline.py`
- **A real bug was found and fixed during this build**: `wuzzuf_collector`'s
  output doesn't include an `extra_json` key, and `jobs.extra_json` is
  `NOT NULL`. `INSERT OR IGNORE` was silently dropping every row instead
  of erroring. Fixed in `app/pipeline.py` (`NOT_NULL_DEFAULTS`). Worth
  knowing because it's the kind of bug that makes a pipeline *look*
  successful (no exception, no crash) while inserting zero rows.

## NOT verified — be aware

- **Live Wuzzuf fetch**: blocked in this environment by an egress
  allowlist (`x-deny-reason: host_not_allowed` from wuzzuf.net) — a real,
  checkable restriction, not a claim taken on faith. Test this from your
  own machine, where the network is unrestricted.
- **Adzuna / Jooble live calls**: not tested against the real APIs — no
  credentials were supplied. The adapters call the documented endpoints
  (`GET api.adzuna.com/v1/api/jobs/{country}/search/1`,
  `POST jooble.org/api/{key}`) but response-shape assumptions
  (`payload["results"]`, `payload["jobs"]`) haven't been confirmed against
  a real response. Test this first with a small `results_per_page`/`ResultOnPage`
  once you have real keys, and check the actual JSON keys match.

## Source policy

| Source | Status | Why |
|---|---|---|
| Wuzzuf | Enabled | Official public RSS feed, no key needed |
| Adzuna | Enabled, needs free credentials | Official API. Does not cover Egypt — supplementary/international only |
| Jooble | Enabled, needs free credentials | Official API. Register at **eg.jooble.org/api/about** for an Egypt-scoped key — a key from jooble.org only returns US listings (confirmed via Jooble's own docs and by directly fetching eg.jooble.org/api/about). |
| LinkedIn / Indeed / Glassdoor | Hard-disabled | No legitimate public job-search API exists for any of them; scraping violates their ToS |

## Run it

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # fill in Adzuna/Jooble keys when you have them
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/

## Test it

```bash
pytest -v
```

## Structure

```
app/
  main.py            FastAPI app + routes
  db.py              schema + connection
  pipeline.py        per-source isolation, dedup, insert
  scoring.py         explainable junior-QA fit scoring
  adapters/
    wuzzuf_collector.py   (your original, reused as-is)
    wuzzuf.py              thin wrapper
    adzuna.py
    jooble.py
    base.py                shared normalize()
frontend/
  index.html         dashboard / jobs / applications, real API calls only
tests/               10 tests, run against fixtures — no live network calls
```
