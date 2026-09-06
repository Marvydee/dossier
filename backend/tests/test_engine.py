"""Integration-style tests for the job orchestrator. All three sources are
mocked so this exercises engine.py's own logic (which categories/cities go to
which source, OSM tag-to-category mapping, progress reporting, phone
normalisation + dedupe + email-fill wiring + the completeness filter and
even-split random sampling) without any network calls.

Uses patch.multiple as a context manager (not a decorator) — using it as a
decorator on pytest test methods clashes with pytest's own fixture-injection
inspection of the function signature.

Note: most fixture records below carry both a phone and an email even when
the test isn't about completeness, specifically so they survive the
completeness filter and the test can still inspect the output rows. Tests
that are actually about the completeness filter itself use deliberately
incomplete records.
"""
from unittest.mock import patch, DEFAULT

from app.scraping.engine import run_job

CATEGORIES = [
    {'slug': 'pharmacy', 'label': 'Pharmacy', 'businesslist_slug': 'pharmacies',
     'finelib_slug': 'online-pharmacy', 'osm_shop_tag': None, 'osm_amenity_tag': 'pharmacy'},
    {'slug': 'restaurant', 'label': 'Restaurant', 'businesslist_slug': 'restaurants',
     'finelib_slug': None, 'osm_shop_tag': None, 'osm_amenity_tag': 'restaurant'},
]

CITIES = [
    {'slug': 'lagos', 'label': 'Lagos', 'is_nigeria': True, 'lat': 6.5244, 'lon': 3.3792},
    {'slug': 'london', 'label': 'London', 'is_nigeria': False, 'lat': 51.5074, 'lon': -0.1278},
]


def _patched_sources():
    return patch.multiple(
        'app.scraping.engine',
        scrape_businesslist=DEFAULT,
        scrape_finelib=DEFAULT,
        query_overpass=DEFAULT,
        extract_emails=DEFAULT,
    )


class TestRunJob:

    def test_businesslist_only_called_for_nigerian_cities(self):
        with _patched_sources() as m:
            m['scrape_businesslist'].return_value = []
            m['scrape_finelib'].return_value = []
            m['query_overpass'].return_value = []

            run_job(CATEGORIES, CITIES, request_delay=0)

            called_cities = {c.args[1] for c in m['scrape_businesslist'].call_args_list}
            assert called_cities == {'lagos'}   # never called for London

    def test_finelib_called_once_per_category_regardless_of_city_count(self):
        with _patched_sources() as m:
            m['scrape_businesslist'].return_value = []
            m['scrape_finelib'].return_value = []
            m['query_overpass'].return_value = []

            run_job(CATEGORIES, CITIES, request_delay=0)

            # Only 'pharmacy' has a finelib_slug; called once, not once per city.
            assert m['scrape_finelib'].call_count == 1
            assert m['scrape_finelib'].call_args.args[0] == 'online-pharmacy'

    def test_finelib_result_city_is_matched_from_address(self):
        with _patched_sources() as m:
            m['scrape_businesslist'].return_value = []
            m['scrape_finelib'].return_value = [
                {'name': 'City Pharmacy', 'phone': '08031234567', 'email': 'info@citypharmacy.ng',
                 'website': '', 'address': '12 Marina, Lagos Island, Nigeria'},
            ]
            m['query_overpass'].return_value = []

            rows = run_job(CATEGORIES, CITIES, request_delay=0, results_per_job=10)

            assert len(rows) == 1
            assert rows[0]['City'] == 'lagos'
            assert rows[0]['Category'] == 'pharmacy'
            assert rows[0]['Source'] == 'Finelib'

    def test_overpass_called_for_every_city_including_international(self):
        with _patched_sources() as m:
            m['scrape_businesslist'].return_value = []
            m['scrape_finelib'].return_value = []
            m['query_overpass'].return_value = []

            run_job(CATEGORIES, CITIES, request_delay=0)

            called_cities = {c.args[0:2] for c in m['query_overpass'].call_args_list}
            assert called_cities == {(6.5244, 3.3792), (51.5074, -0.1278)}

    def test_overpass_tag_is_mapped_back_to_category_slug(self):
        with _patched_sources() as m:
            m['scrape_businesslist'].return_value = []
            m['scrape_finelib'].return_value = []
            m['query_overpass'].return_value = [
                {'name': 'Mama Cass', 'phone': '08031112222', 'email': 'hello@mamacass.ng',
                 'website': '', 'address': '', '_matched_tag': 'restaurant'},
            ]

            rows = run_job(CATEGORIES, CITIES, request_delay=0, results_per_job=10)

            assert len(rows) > 0
            assert all(r['Category'] == 'restaurant' for r in rows)
            assert all(r['Source'] == 'OpenStreetMap' for r in rows)

    def test_phone_normalised_and_invalid_numbers_dropped(self):
        with _patched_sources() as m:
            m['scrape_businesslist'].return_value = [
                {'name': 'Alpha Pharmacy', 'phone': '+2348031234567', 'email': 'info@alpha.ng',
                 'website': '', 'address': ''},
            ]
            m['scrape_finelib'].return_value = []
            m['query_overpass'].return_value = []

            rows = run_job(CATEGORIES, CITIES, request_delay=0, results_per_job=10)

            assert rows[0]['Phone Number'] == '08031234567'

    def test_missing_email_triggers_website_visit(self):
        with _patched_sources() as m:
            m['scrape_businesslist'].return_value = [
                {'name': 'Alpha Pharmacy', 'phone': '08031234567', 'email': '',
                 'website': 'https://alpha.ng', 'address': ''},
            ]
            m['scrape_finelib'].return_value = []
            m['query_overpass'].return_value = []
            m['extract_emails'].return_value = ['info@alpha.ng']

            rows = run_job(CATEGORIES, CITIES, request_delay=0, results_per_job=10)

            m['extract_emails'].assert_called_once_with('https://alpha.ng', timeout=8)
            assert rows[0]['Email'] == 'info@alpha.ng'

    def test_phone_only_record_survives_even_if_email_never_found(self):
        """Verified live (2026-09-05): BusinessList/Finelib search-results
        cards almost never expose an email directly, so requiring both phone
        and email made nearly every real search return zero results. A
        record with just a phone is still a usable lead."""
        with _patched_sources() as m:
            m['scrape_businesslist'].return_value = [
                {'name': 'Alpha Pharmacy', 'phone': '08031234567', 'email': '',
                 'website': 'https://alpha.ng', 'address': ''},
            ]
            m['scrape_finelib'].return_value = []
            m['query_overpass'].return_value = []
            m['extract_emails'].return_value = []  # website visited, still no email found

            rows = run_job(CATEGORIES, CITIES, request_delay=0, results_per_job=10)

            assert len(rows) == 1
            assert rows[0]['Phone Number'] == '08031234567'
            assert rows[0]['Email'] == ''

    def test_record_with_neither_phone_nor_email_is_filtered_out(self):
        with _patched_sources() as m:
            m['scrape_businesslist'].return_value = [
                {'name': 'No Contact Ltd', 'phone': '', 'email': '', 'website': '', 'address': ''},
            ]
            m['scrape_finelib'].return_value = []
            m['query_overpass'].return_value = []

            rows = run_job(CATEGORIES, CITIES, request_delay=0, results_per_job=10)

            assert rows == []

    def test_no_results_from_any_source_returns_empty_list(self):
        with _patched_sources() as m:
            m['scrape_businesslist'].return_value = []
            m['scrape_finelib'].return_value = []
            m['query_overpass'].return_value = []

            assert run_job(CATEGORIES, CITIES, request_delay=0) == []

    def test_a_source_exception_does_not_abort_the_job(self):
        with _patched_sources() as m:
            m['scrape_businesslist'].side_effect = Exception('boom')
            m['scrape_finelib'].return_value = []
            m['query_overpass'].return_value = [
                {'name': 'Mama Cass', 'phone': '08031112222', 'email': 'hello@mamacass.ng',
                 'website': '', 'address': '', '_matched_tag': 'restaurant'},
            ]

            rows = run_job(CATEGORIES, CITIES, request_delay=0, results_per_job=10)

            # BusinessList blew up, but OSM results still made it through.
            assert len(rows) > 0

    def test_progress_callback_is_invoked(self):
        with _patched_sources() as m:
            m['scrape_businesslist'].return_value = []
            m['scrape_finelib'].return_value = []
            m['query_overpass'].return_value = []

            calls = []
            run_job(CATEGORIES, CITIES, request_delay=0,
                    progress_cb=lambda current, total, message: calls.append((current, total, message)))

            assert len(calls) > 0
            assert all(isinstance(c[2], str) for c in calls)


def _pool_for_city(city_label, n=20, start=0):
    """A pool of fully complete, uniquely-named businesses for one city.

    Names are zero-padded ("Business 01", not "Business 1") so no name is an
    accidental substring of another — "Business 1" would otherwise collide
    with "Business 10".."Business 19" under the dedup's substring-match rule.
    `start` must be given a distinct range per city when pools are combined
    across cities in one test — otherwise two different cities' businesses
    generate identical phone numbers (both counting from 0) and collide
    under the dedup's phone-match rule, merging cross-city pairs into one.
    Both are test-data hazards, not real product bugs — real business names
    and phone numbers don't recycle like a bare loop counter does.
    """
    return [
        {
            'name': f'{city_label} Business {i:04d}',
            'phone': f'0803{start + i:07d}',
            'email': f'contact{start + i}@{city_label.lower()}.example.com',
            'website': '', 'address': '',
        }
        for i in range(n)
    ]


def _overpass_side_effect_by_city(pools_by_lat):
    """query_overpass is called once per selected city with that city's own
    (lat, lon) — unlike businesslist, which only ever runs for Nigerian
    cities, this is the source that can genuinely return data tagged to
    either of our two test cities, so it's what these tests drive through."""
    def side_effect(lat, lon, **kwargs):
        return pools_by_lat.get(lat, [])
    return side_effect


class TestRunJobQualityAndSizing:
    """Covers the three product requirements added on top of the base engine:
    no user ever gets an identical deterministic list, every delivered
    business has both a phone and an email, and the total output is capped
    and split evenly across the selected cities."""

    def test_output_never_exceeds_results_per_job(self):
        with _patched_sources() as m:
            m['scrape_businesslist'].return_value = []
            m['scrape_finelib'].return_value = []
            m['query_overpass'].side_effect = _overpass_side_effect_by_city({
                6.5244: _pool_for_city('Lagos', start=0),
                51.5074: _pool_for_city('London', start=1000),
            })

            rows = run_job(CATEGORIES, CITIES, request_delay=0, results_per_job=10)

            assert len(rows) == 10

    def test_output_split_evenly_across_two_cities(self):
        with _patched_sources() as m:
            m['scrape_businesslist'].return_value = []
            m['scrape_finelib'].return_value = []
            m['query_overpass'].side_effect = _overpass_side_effect_by_city({
                6.5244: _pool_for_city('Lagos', start=0),
                51.5074: _pool_for_city('London', start=1000),
            })

            rows = run_job(CATEGORIES, CITIES, request_delay=0, results_per_job=10)

            per_city = {}
            for r in rows:
                per_city[r['City']] = per_city.get(r['City'], 0) + 1
            assert per_city == {'lagos': 5, 'london': 5}

    def test_uneven_split_distributes_remainder(self):
        """3 cities, 10 total -> 4/3/3, not silently rounded down to 9 or up to 12."""
        three_cities = CITIES + [
            {'slug': 'abuja', 'label': 'Abuja', 'is_nigeria': True, 'lat': 9.0765, 'lon': 7.3986},
        ]
        with _patched_sources() as m:
            m['scrape_businesslist'].return_value = []
            m['scrape_finelib'].return_value = []
            m['query_overpass'].side_effect = _overpass_side_effect_by_city({
                6.5244: _pool_for_city('Lagos', start=0),
                51.5074: _pool_for_city('London', start=1000),
                9.0765: _pool_for_city('Abuja', start=2000),
            })

            rows = run_job(CATEGORIES, three_cities, request_delay=0, results_per_job=10)

            assert len(rows) == 10
            per_city = {}
            for r in rows:
                per_city[r['City']] = per_city.get(r['City'], 0) + 1
            assert sorted(per_city.values()) == [3, 3, 4]

    def test_every_row_has_at_least_one_contact_method(self):
        with _patched_sources() as m:
            m['scrape_businesslist'].return_value = [
                {'name': 'No Email Ltd', 'phone': '08099998888', 'email': '', 'website': '', 'address': ''},
                {'name': 'No Phone Ltd', 'phone': '', 'email': 'x@y.com', 'website': '', 'address': ''},
                {'name': 'No Contact Ltd', 'phone': '', 'email': '', 'website': '', 'address': ''},
            ]
            m['scrape_finelib'].return_value = []
            m['query_overpass'].side_effect = _overpass_side_effect_by_city({
                6.5244: _pool_for_city('Lagos', n=5, start=0),
                51.5074: _pool_for_city('London', n=5, start=1000),
            })

            rows = run_job(CATEGORIES, CITIES, request_delay=0, results_per_job=20)

            assert len(rows) > 0
            assert all(r['Phone Number'] or r['Email'] for r in rows)
            names = {r['Business Name'] for r in rows}
            # A single contact method is enough to survive the filter...
            assert 'No Email Ltd' in names
            assert 'No Phone Ltd' in names
            # ...but zero contact methods never does.
            assert 'No Contact Ltd' not in names

    def test_two_runs_of_the_identical_search_produce_different_output(self):
        """The whole point of randomised sampling: two users (or the same
        user running it twice) searching the exact same thing should not
        receive an identical list."""
        with _patched_sources() as m:
            m['scrape_businesslist'].return_value = []
            m['scrape_finelib'].return_value = []
            m['query_overpass'].side_effect = _overpass_side_effect_by_city({
                6.5244: _pool_for_city('Lagos', start=0),
                51.5074: _pool_for_city('London', start=1000),
            })

            rows_a = run_job(CATEGORIES, CITIES, request_delay=0, results_per_job=6)
            rows_b = run_job(CATEGORIES, CITIES, request_delay=0, results_per_job=6)

            names_a = [r['Business Name'] for r in rows_a]
            names_b = [r['Business Name'] for r in rows_b]
            assert names_a != names_b

    def test_insufficient_complete_records_returns_fewer_than_requested(self):
        with _patched_sources() as m:
            # Only 2 complete businesses exist in the whole pool, but we ask for 10.
            m['scrape_businesslist'].return_value = [
                {'name': 'A', 'phone': '08031110000', 'email': 'a@x.com', 'website': '', 'address': ''},
                {'name': 'B', 'phone': '08022220000', 'email': 'b@x.com', 'website': '', 'address': ''},
            ]
            m['scrape_finelib'].return_value = []
            m['query_overpass'].return_value = []

            rows = run_job(CATEGORIES, CITIES, request_delay=0, results_per_job=10)

            # Never crashes, never pads with incomplete data — just returns what's real.
            assert len(rows) == 2
            assert all(r['Phone Number'] and r['Email'] for r in rows)
