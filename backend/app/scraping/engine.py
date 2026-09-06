"""Orchestrates one generation job across all three sources."""
import time
from typing import Callable, Optional

from .businesslist import scrape_businesslist
from .finelib import scrape_finelib
from .overpass import query_overpass, DEFAULT_RADIUS_M
from .phone import normalise_phone
from .dedupe import deduplicate, match_city
from .emails import extract_emails
from .sampling import filter_has_contact, sample_evenly_by_city

ProgressCallback = Optional[Callable[[int, int, str], None]]

DEFAULT_RESULTS_PER_JOB = 10


def run_job(
    categories: list[dict],
    cities: list[dict],
    *,
    max_pages_per_search: int = 3,
    request_delay: float = 1.5,
    website_timeout: int = 8,
    overpass_radius_m: int = DEFAULT_RADIUS_M,
    results_per_job: int = DEFAULT_RESULTS_PER_JOB,
    progress_cb: ProgressCallback = None,
) -> list[dict]:
    """Run a generation job and return rows ready for scraping.excel.save_to_excel.

    categories: [{slug, label, businesslist_slug, finelib_slug, osm_shop_tag, osm_amenity_tag}, ...]
    cities:     [{slug, label, is_nigeria, lat, lon}, ...]

    The returned set is capped at `results_per_job` total, split as evenly as
    possible across the selected cities, randomly sampled from the pool of
    contactable records (phone and/or email present) so that two users
    running the identical search don't receive an identical list, and no
    business with zero contact methods is ever delivered.
    """

    def report(current, total, message):
        if progress_cb:
            progress_cb(current, total, message)

    nigerian_cities = [c for c in cities if c.get('is_nigeria')]
    all_results = []

    # ── Source 1: BusinessList — category x Nigerian city ───────────────
    bl_categories = [c for c in categories if c.get('businesslist_slug')]
    total_bl = len(bl_categories) * len(nigerian_cities)
    count = 0
    for category in bl_categories:
        for city in nigerian_cities:
            count += 1
            report(count, total_bl, f'BusinessList: {category["label"]} in {city["label"]}')
            try:
                results = scrape_businesslist(
                    category['businesslist_slug'], city['slug'],
                    max_pages=max_pages_per_search,
                    request_delay=request_delay,
                    timeout=website_timeout,
                )
            except Exception:
                results = []
            for r in results:
                r['category'] = category['slug']
                r['city']     = city['slug']
                r['source']   = 'BusinessList'
            all_results.extend(results)
            time.sleep(request_delay)

    # ── Source 2: Finelib — category only, city matched from address ────
    fl_categories = [c for c in categories if c.get('finelib_slug')]
    for i, category in enumerate(fl_categories, 1):
        report(i, len(fl_categories), f'Finelib: {category["label"]}')
        try:
            results = scrape_finelib(
                category['finelib_slug'],
                max_pages=max_pages_per_search,
                request_delay=request_delay,
                timeout=website_timeout,
            )
        except Exception:
            results = []
        for r in results:
            r['category'] = category['slug']
            r['city']     = match_city(r.get('address', ''), nigerian_cities)
            r['source']   = 'Finelib'
        all_results.extend(results)
        time.sleep(request_delay)

    # ── Source 3: OpenStreetMap — once per selected city, any country ───
    shop_tag_map    = {c['osm_shop_tag']: c['slug'] for c in categories if c.get('osm_shop_tag')}
    amenity_tag_map = {c['osm_amenity_tag']: c['slug'] for c in categories if c.get('osm_amenity_tag')}
    if shop_tag_map or amenity_tag_map:
        for i, city in enumerate(cities, 1):
            report(i, len(cities), f'OpenStreetMap: {city["label"]}')
            try:
                results = query_overpass(
                    city['lat'], city['lon'],
                    shop_tags=list(shop_tag_map.keys()),
                    amenity_tags=list(amenity_tag_map.keys()),
                    radius_m=overpass_radius_m,
                )
            except Exception:
                results = []
            for r in results:
                tag = r.get('_matched_tag', '')
                r['category'] = shop_tag_map.get(tag) or amenity_tag_map.get(tag, '')
                r['city']     = city['slug']
                r['source']   = 'OpenStreetMap'
            all_results.extend(results)
            time.sleep(2)

    if not all_results:
        return []

    # ── Normalise phone numbers ──────────────────────────────────────────
    for r in all_results:
        r['phone'] = normalise_phone(r.get('phone', ''))

    # ── Deduplicate across all three sources ─────────────────────────────
    merged = deduplicate(all_results)

    # ── Fill in missing emails by visiting each business's website ───────
    for r in merged:
        if not r.get('email') and r.get('website'):
            try:
                found = extract_emails(r['website'], timeout=website_timeout)
            except Exception:
                found = []
            if found:
                r['email'] = ', '.join(found[:3])
            time.sleep(request_delay)

    # ── Quality check: never deliver a business with no contact method ───
    contactable = filter_has_contact(merged)

    # ── Randomise + cap: fixed-size, evenly-split, non-deterministic ─────
    city_slugs = [c['slug'] for c in cities]
    sampled = sample_evenly_by_city(contactable, city_slugs, results_per_job)

    return [{
        'Business Name': r.get('name', ''),
        'Email':         r.get('email', ''),
        'Phone Number':  r.get('phone', ''),
        'Website':       r.get('website', ''),
        'Address':       r.get('address', ''),
        'City':          r.get('city', ''),
        'Category':      r.get('category', ''),
        'Source':        r.get('source', ''),
    } for r in sampled]
