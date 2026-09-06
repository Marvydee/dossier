# Dossier

**MDJ FORGE** — a trusted record of real businesses, compiled on demand, starting with Nigeria.

Sign up, name a category and a city, get 10 verified business contacts pulled
fresh from real directories — deduplicated, phone-normalised, and never a
dead entry. Pay with tokens via Paystack once your free ones run out.

---

## Current status

| Piece | Status |
|---|---|
| Scraping engine (`backend/app/scraping/`) | ✅ Built, tested, verified against live sites |
| Database schema (`supabase/`) | ✅ Applied to a live Supabase project |
| FastAPI backend (API, auth, jobs, billing) | ✅ Built, tested, verified end-to-end against live Supabase + Paystack |
| Next.js frontend | ✅ Built ("Field Ledger" design) |

The old single-file `scraper.py` at the repo root is retired — its logic now
lives in `backend/app/scraping/`, parameterised instead of hardcoded, with a
real test suite.

---

## Data sources (all free, no API key)

- **BusinessList.com.ng** — Nigeria business directory. Category + city scoped.
- **Finelib.com** — Nigeria business directory. Category scoped (nationwide; city is matched from each listing's address).
- **OpenStreetMap** (Overpass API) — works for any city worldwide, given coordinates. This is the only source with data outside Nigeria.

All three were verified against the live sites, not assumed — see
`backend/tests/test_scrapers.py` and `backend/tests/test_overpass.py` for
what was actually checked (real HTML fixtures, a live Overpass query bug that
was found and fixed).

90 categories are live — from pharmacies and supermarkets to auto repair
workshops, bars & lounges, plumbers, accountants, and daycares — each with
`businesslist_slug`/`finelib_slug`/OSM tags verified against the live sites,
not guessed. See `supabase/seed/categories.sql`.

Every generation delivers a fixed 10 businesses, split evenly across the
selected cities, randomly sampled so two identical searches never return the
same list, and filtered so every entry has at least one working contact
method. See `backend/app/scraping/sampling.py` for the reasoning — an
earlier "phone AND email required" version returned near-empty results
against real data.

---

## Running the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # fill in Supabase + Paystack keys
pytest -v                        # 116 tests, all offline
uvicorn app.main:app --reload    # http://127.0.0.1:8000
```

## Running the frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # fill in Supabase URL + anon key
npm run dev                        # http://localhost:3000
```

Design direction is "Field Ledger": cool parchment background, charcoal-navy
text, a serif display face (Fraunces, upright — italic is reserved for the
wordmark only) paired with a humanist sans (Karla), a single pine-green
accent, hairline rules instead of card shadows. Tokens live in
`frontend/src/app/globals.css`. Responsive down to mobile, verified with
real Playwright screenshots (`frontend/responsive-check.mjs`), zero
horizontal overflow across 24 page/viewport combinations.

Dev mode note: `next.config.ts` sets `allowedDevOrigins: ["localhost",
"127.0.0.1"]` — without it, Turbopack's dev server silently breaks the HMR
websocket (and hydration along with it) when accessed via `127.0.0.1`
instead of `localhost`. Found and fixed live; see the git history for the
diagnosis if it ever regresses.

---

## Repo layout

```
backend/app/scraping/   # the scraping engine — businesslist, finelib, overpass,
                         # phone normalisation, dedupe, sampling, Excel export, orchestration
backend/app/routers/    # FastAPI routes — catalog, jobs, billing
backend/tests/          # pytest suite (116 tests) + live-site HTML fixtures
supabase/migrations/    # schema: profiles, categories, cities, generation_jobs,
                         # token_transactions, payments, RLS policies
supabase/seed/          # category and city catalog data
frontend/               # Next.js app (App Router, TypeScript, Tailwind v4)
```
