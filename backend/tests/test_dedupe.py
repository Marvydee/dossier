from app.scraping.dedupe import deduplicate, match_city, _normalise_name


class TestNormaliseName:

    def test_lowercases_and_strips_punctuation(self):
        assert _normalise_name("Alpha Pharmacy & Stores Ltd.") == 'alpha pharmacy stores ltd'

    def test_collapses_whitespace(self):
        assert _normalise_name('Mama   Cass   Restaurant') == 'mama cass restaurant'


class TestMatchCity:

    CITIES = [
        {'slug': 'lagos', 'label': 'Lagos'},
        {'slug': 'port-harcourt', 'label': 'Port Harcourt'},
    ]

    def test_matches_city_mentioned_in_address(self):
        assert match_city('Block G1, Sura Shopping Complex, Lagos Island, Nigeria', self.CITIES) == 'lagos'

    def test_matches_multi_word_city(self):
        assert match_city('12 Aba Road, Port Harcourt, Rivers State', self.CITIES) == 'port-harcourt'

    def test_no_match_returns_empty_string(self):
        assert match_city('Somewhere in Abuja, FCT', self.CITIES) == ''

    def test_case_insensitive(self):
        assert match_city('12 Marina Street, LAGOS ISLAND', self.CITIES) == 'lagos'


class TestDeduplicate:

    def test_exact_phone_match_merges(self):
        records = [
            {'name': 'Alpha Pharmacy', 'phone': '08031234567', 'email': '', 'website': '',
             'address': '', 'source': 'BusinessList'},
            {'name': 'Alpha Pharmacy Ltd', 'phone': '08031234567', 'email': 'a@x.com', 'website': '',
             'address': '', 'source': 'Finelib'},
        ]
        merged = deduplicate(records)
        assert len(merged) == 1
        assert merged[0]['email'] == 'a@x.com'
        assert merged[0]['source'] == 'Multiple'

    def test_name_substring_match_merges(self):
        records = [
            {'name': 'Shoprite', 'phone': '', 'email': '', 'website': '', 'address': '',
             'source': 'OpenStreetMap'},
            {'name': 'Shoprite Palms Lekki', 'phone': '09014000001', 'email': '', 'website': 'https://shoprite.ng',
             'address': 'Lekki, Lagos', 'source': 'BusinessList'},
        ]
        merged = deduplicate(records)
        assert len(merged) == 1
        # Longer/more specific name wins
        assert merged[0]['name'] == 'Shoprite Palms Lekki'
        assert merged[0]['phone'] == '09014000001'
        assert merged[0]['website'] == 'https://shoprite.ng'

    def test_unrelated_businesses_stay_separate(self):
        records = [
            {'name': 'Mama Cass Restaurant', 'phone': '08011112222', 'email': '', 'website': '',
             'address': '', 'source': 'BusinessList'},
            {'name': 'Mr Bigs', 'phone': '08033334444', 'email': '', 'website': '',
             'address': '', 'source': 'Finelib'},
        ]
        merged = deduplicate(records)
        assert len(merged) == 2

    def test_most_complete_record_wins_per_field(self):
        records = [
            {'name': 'Cactus', 'phone': '', 'email': 'cactus@example.com', 'website': '',
             'address': '', 'source': 'Finelib'},
            {'name': 'Cactus', 'phone': '08022223333', 'email': '', 'website': 'https://cactus.ng',
             'address': 'VI, Lagos', 'source': 'BusinessList'},
        ]
        merged = deduplicate(records)
        assert len(merged) == 1
        row = merged[0]
        assert row['phone'] == '08022223333'
        assert row['email'] == 'cactus@example.com'
        assert row['website'] == 'https://cactus.ng'
        assert row['address'] == 'VI, Lagos'

    def test_single_source_not_tagged_multiple(self):
        records = [
            {'name': 'Solo Store', 'phone': '08011119999', 'email': '', 'website': '',
             'address': '', 'source': 'BusinessList'},
        ]
        merged = deduplicate(records)
        assert merged[0]['source'] == 'BusinessList'
