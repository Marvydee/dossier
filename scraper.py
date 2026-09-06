"""
This standalone script has been retired now that Docket Prospector is a
multi-tenant platform rather than a single local script.

Its logic (BusinessList/Finelib/OpenStreetMap scraping, phone normalisation,
dedupe, Excel export) now lives as an importable package, parameterised
instead of hardcoded, at:

    backend/app/scraping/

That package is what the platform's background worker calls per generation
job. See backend/tests/ for its test suite, and the root README for how the
platform fits together.
"""

raise SystemExit(
    "scraper.py has been retired — see backend/app/scraping/ for the current, "
    "parameterised version of this logic."
)
