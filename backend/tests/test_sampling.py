from app.scraping.sampling import filter_has_contact, sample_evenly_by_city


class TestFilterHasContact:
    """Requires at least one of phone/email, not both — verified live
    (2026-09-05) that BusinessList/Finelib search-results cards almost never
    expose an email, so "both required" made nearly every real search return
    zero results. See sampling.py's module docstring for the full context."""

    def test_keeps_record_with_both_phone_and_email(self):
        records = [{'phone': '08011112222', 'email': 'a@x.com'}]
        assert filter_has_contact(records) == records

    def test_keeps_record_with_only_phone(self):
        records = [{'phone': '08011112222', 'email': ''}]
        assert filter_has_contact(records) == records

    def test_keeps_record_with_only_email(self):
        records = [{'phone': '', 'email': 'a@x.com'}]
        assert filter_has_contact(records) == records

    def test_drops_record_missing_both(self):
        records = [{'phone': '', 'email': ''}]
        assert filter_has_contact(records) == []

    def test_missing_keys_entirely_are_treated_as_absent(self):
        assert filter_has_contact([{'name': 'No fields at all'}]) == []

    def test_mixed_pool_drops_only_the_fully_empty_ones(self):
        records = [
            {'name': 'A', 'phone': '0801', 'email': 'a@x.com'},
            {'name': 'B', 'phone': '', 'email': 'b@x.com'},
            {'name': 'C', 'phone': '0802', 'email': ''},
            {'name': 'D', 'phone': '', 'email': ''},
        ]
        result = filter_has_contact(records)
        assert {r['name'] for r in result} == {'A', 'B', 'C'}


def _named_pool(city, n):
    return [{'name': f'{city}-{i}', 'city': city} for i in range(n)]


class TestSampleEvenlyByCity:

    def test_exact_even_division(self):
        pool = _named_pool('lagos', 10) + _named_pool('abuja', 10)
        result = sample_evenly_by_city(pool, ['lagos', 'abuja'], total=10)

        assert len(result) == 10
        counts = {}
        for r in result:
            counts[r['city']] = counts.get(r['city'], 0) + 1
        assert counts == {'lagos': 5, 'abuja': 5}

    def test_single_city_gets_full_total(self):
        pool = _named_pool('lagos', 20)
        result = sample_evenly_by_city(pool, ['lagos'], total=10)
        assert len(result) == 10
        assert all(r['city'] == 'lagos' for r in result)

    def test_ten_cities_one_each(self):
        cities = [f'city{i}' for i in range(10)]
        pool = [r for c in cities for r in _named_pool(c, 5)]
        result = sample_evenly_by_city(pool, cities, total=10)

        assert len(result) == 10
        counts = {}
        for r in result:
            counts[r['city']] = counts.get(r['city'], 0) + 1
        assert counts == {c: 1 for c in cities}

    def test_remainder_distributed_not_dropped(self):
        # 3 cities, 10 total -> quotas must sum to exactly 10 (e.g. 4/3/3)
        pool = _named_pool('a', 10) + _named_pool('b', 10) + _named_pool('c', 10)
        result = sample_evenly_by_city(pool, ['a', 'b', 'c'], total=10)

        assert len(result) == 10
        counts = {}
        for r in result:
            counts[r['city']] = counts.get(r['city'], 0) + 1
        assert sum(counts.values()) == 10
        assert sorted(counts.values()) == [3, 3, 4]

    def test_backfills_shortfall_from_other_cities(self):
        # lagos can only supply 1 of its 5-quota share; abuja has plenty spare.
        pool = _named_pool('lagos', 1) + _named_pool('abuja', 20)
        result = sample_evenly_by_city(pool, ['lagos', 'abuja'], total=10)

        assert len(result) == 10   # still hits the target using abuja's surplus
        counts = {}
        for r in result:
            counts[r['city']] = counts.get(r['city'], 0) + 1
        assert counts['lagos'] == 1
        assert counts['abuja'] == 9

    def test_returns_fewer_than_total_if_the_whole_pool_is_too_small(self):
        pool = _named_pool('lagos', 2) + _named_pool('abuja', 1)
        result = sample_evenly_by_city(pool, ['lagos', 'abuja'], total=10)
        assert len(result) == 3   # never fabricates records that don't exist

    def test_records_for_unselected_cities_are_ignored(self):
        pool = _named_pool('lagos', 10) + _named_pool('kano', 10)
        result = sample_evenly_by_city(pool, ['lagos'], total=5)
        assert len(result) == 5
        assert all(r['city'] == 'lagos' for r in result)

    def test_empty_pool_returns_empty(self):
        assert sample_evenly_by_city([], ['lagos'], total=10) == []

    def test_empty_cities_returns_empty(self):
        pool = _named_pool('lagos', 10)
        assert sample_evenly_by_city(pool, [], total=10) == []

    def test_zero_total_returns_empty(self):
        pool = _named_pool('lagos', 10)
        assert sample_evenly_by_city(pool, ['lagos'], total=0) == []

    def test_repeated_calls_on_the_same_pool_vary(self):
        """The point of this function existing: two calls on an identical
        pool with an identical selection should not deterministically return
        the same subset/order every time."""
        pool = _named_pool('lagos', 50)
        results = [
            tuple(r['name'] for r in sample_evenly_by_city(pool, ['lagos'], total=5))
            for _ in range(5)
        ]
        assert len(set(results)) > 1   # not every run produced the identical tuple
