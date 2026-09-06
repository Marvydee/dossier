"""Turns a raw deduped pool of scraped businesses into what a user actually
receives: a fixed-size, randomised, quality-checked sample.

Two independent problems this solves:
  1. Without randomisation, every user searching the same category+city gets
     byte-for-byte the same list — worthless for two paying customers
     competing for the same leads.
  2. A raw scrape can produce a record with no usable contact method at all
     (neither phone nor email) — that's not a lead, and should never ship.

Note on "phone AND email" vs "phone OR email": verified live against real
BusinessList/Finelib results (2026-09-05) that requiring both is too strict
to be useful — neither site exposes email on its search-results card in the
large majority of cases (a sample of 20 real Lagos pharmacies had phone
numbers for all 20 and an email for 0), so "both required" made almost every
real search return zero results. "At least one" is the bar that matches what
the sources actually provide while still guaranteeing every delivered row is
contactable.
"""
import random


def filter_has_contact(records: list[dict]) -> list[dict]:
    """Keep only records with at least one usable contact method (phone or
    email). A record with neither isn't a lead — drop it rather than
    silently deliver a dead end."""
    return [r for r in records if r.get('phone') or r.get('email')]


def sample_evenly_by_city(records: list[dict], cities: list[str], total: int) -> list[dict]:
    """Randomly select up to `total` records spread as evenly as possible
    across `cities`. Every call reshuffles — two users running the identical
    search get different results, not a deterministic top-N.

    If a city doesn't have enough records to fill its share, the shortfall is
    backfilled from whichever other selected cities have surplus, so the
    total still reaches `total` when enough data exists somewhere in the pool.
    Never returns a record with no contact method — that's enforced by
    filter_has_contact() being called before this, not by this function.
    """
    if not cities or total <= 0:
        return []

    by_city: dict[str, list[dict]] = {c: [] for c in cities}
    for r in records:
        city = r.get('city')
        if city in by_city:
            by_city[city].append(r)

    for pool in by_city.values():
        random.shuffle(pool)

    n = len(cities)
    base = total // n
    remainder = total % n
    bonus_cities = set(random.sample(cities, remainder)) if remainder else set()

    selected: list[dict] = []
    taken_counts: dict[str, int] = {}
    for city in cities:
        quota = base + (1 if city in bonus_cities else 0)
        take = by_city[city][:quota]
        selected.extend(take)
        taken_counts[city] = len(take)

    shortfall = total - len(selected)
    if shortfall > 0:
        remaining_pool = []
        for city in cities:
            remaining_pool.extend(by_city[city][taken_counts[city]:])
        random.shuffle(remaining_pool)
        selected.extend(remaining_pool[:shortfall])

    random.shuffle(selected)
    return selected
