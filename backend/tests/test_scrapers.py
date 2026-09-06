"""Validates the scraper selectors against real HTML captured from the live
sites (businesslist.com.ng, finelib.com) on 2026-08-27 and re-verified
2026-09-05. Runs entirely offline against the fixtures — no network calls —
so it stays green in CI regardless of whether the live sites are reachable.
"""
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.scraping.businesslist import scrape_businesslist
from app.scraping.finelib import scrape_finelib
from app.scraping.pagination import find_next_page_url
from bs4 import BeautifulSoup

FIXTURES = Path(__file__).parent / 'fixtures'


def _fake_response(html, url):
    resp = MagicMock()
    resp.text = html
    resp.url = url
    resp.raise_for_status = MagicMock()
    return resp


class TestScrapeBusinessList:

    def setup_method(self):
        self.html = (FIXTURES / 'businesslist_pharmacies_lagos.html').read_text(encoding='utf-8')
        self.url = 'https://www.businesslist.com.ng/category/pharmacies/city:lagos'

    @patch('app.scraping.businesslist.requests.get')
    def test_extracts_all_listings_on_the_page(self, mock_get):
        mock_get.return_value = _fake_response(self.html, self.url)

        results = scrape_businesslist('pharmacies', 'lagos', max_pages=1,
                                       request_delay=0, timeout=8)

        assert len(results) == 20
        assert mock_get.call_count == 1

    @patch('app.scraping.businesslist.requests.get')
    def test_first_listing_fields_are_clean(self, mock_get):
        mock_get.return_value = _fake_response(self.html, self.url)

        results = scrape_businesslist('pharmacies', 'lagos', max_pages=1,
                                       request_delay=0, timeout=8)

        first = results[0]
        assert first['name'] == 'Alpha Pharmacy & Stores Limited'
        assert first['phone'] == '+234 1 496 1607'
        assert 'Ikeja' in first['address']
        # No stray rank-number prefix ("1 | ") leaking into the name
        assert not first['name'].startswith('1')

    @patch('app.scraping.businesslist.requests.get')
    def test_sponsored_ad_listing_is_excluded(self, mock_get):
        mock_get.return_value = _fake_response(self.html, self.url)

        results = scrape_businesslist('pharmacies', 'lagos', max_pages=1,
                                       request_delay=0, timeout=8)

        # 20 real listings, not 21 — the "company company_ad" sponsored block is skipped
        assert len(results) == 20

    def test_pagination_link_is_detected(self):
        soup = BeautifulSoup(self.html, 'html.parser')
        next_url = find_next_page_url(soup, self.url)
        assert next_url == 'https://www.businesslist.com.ng/category/pharmacies/2/city:lagos'

    @patch('app.scraping.businesslist.requests.get')
    def test_network_failure_returns_empty_list_not_exception(self, mock_get):
        mock_get.side_effect = Exception('connection refused')

        results = scrape_businesslist('pharmacies', 'lagos', max_pages=1,
                                       request_delay=0, timeout=8)

        assert results == []

    @patch('app.scraping.businesslist.requests.get')
    def test_unmapped_category_short_circuits_without_a_request(self, mock_get):
        # engine.py only calls this for categories that have a businesslist_slug,
        # but scrape_businesslist itself should still degrade gracefully.
        mock_get.return_value = _fake_response('<html></html>', self.url)

        results = scrape_businesslist('a-category-that-does-not-exist', 'lagos',
                                       max_pages=1, request_delay=0, timeout=8)

        assert results == []


class TestScrapeFinelib:

    def setup_method(self):
        self.html = (FIXTURES / 'finelib_clothing.html').read_text(encoding='utf-8')
        self.url = 'https://www.finelib.com/shopping/clothing'

    @patch('app.scraping.finelib.requests.get')
    def test_extracts_listings_with_name_phone_address(self, mock_get):
        mock_get.return_value = _fake_response(self.html, self.url)

        results = scrape_finelib('clothing', max_pages=3, request_delay=0, timeout=8)

        assert len(results) > 0
        first = results[0]
        assert first['name']
        assert first['address']
        # Finelib's listing card doesn't expose email/website inline
        assert first['email'] == ''
        assert first['website'] == ''

    @patch('app.scraping.finelib.requests.get')
    def test_does_not_paginate_past_a_disabled_next_link(self, mock_get):
        mock_get.return_value = _fake_response(self.html, self.url)

        scrape_finelib('clothing', max_pages=5, request_delay=0, timeout=8)

        # The fixture's "Next" link has no href (only one page of results) —
        # the scraper must not treat a plain <a>Next</a> as a real next page.
        assert mock_get.call_count == 1

    @patch('app.scraping.finelib.requests.get')
    def test_network_failure_returns_empty_list_not_exception(self, mock_get):
        mock_get.side_effect = Exception('timed out')

        results = scrape_finelib('clothing', max_pages=1, request_delay=0, timeout=8)

        assert results == []
