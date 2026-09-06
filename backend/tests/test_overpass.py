"""The original `is_in:country` area-name approach was tested live against
the real Overpass API and found broken (0 results for every city — that tag
is essentially unpopulated in current OSM data), and a country-boundary
fallback pulled in an unrelated same-named place from another country. The
radius-around-coordinates approach below was verified working live against
real Lagos, Nigeria data before being adopted. These tests mock the HTTP call
and focus on query construction and result mapping.
"""
from unittest.mock import patch, MagicMock

from app.scraping.overpass import query_overpass


def _fake_response(json_data):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


class TestQueryOverpass:

    @patch('app.scraping.overpass.requests.post')
    def test_query_uses_radius_not_area_name_matching(self, mock_post):
        mock_post.return_value = _fake_response({'elements': []})

        query_overpass(6.5244, 3.3792, shop_tags=['supermarket'], amenity_tags=[])

        sent_query = mock_post.call_args.kwargs['data']['data']
        assert 'around:15000,6.5244,3.3792' in sent_query
        assert 'is_in:country' not in sent_query
        assert 'area[' not in sent_query

    @patch('app.scraping.overpass.requests.post')
    def test_maps_shop_tag_results(self, mock_post):
        mock_post.return_value = _fake_response({'elements': [
            {'type': 'node', 'tags': {'name': 'Shoprite', 'shop': 'supermarket',
                                       'phone': '+234 90 1400 0001'}},
        ]})

        results = query_overpass(6.5244, 3.3792, shop_tags=['supermarket'], amenity_tags=[])

        assert len(results) == 1
        assert results[0]['name'] == 'Shoprite'
        assert results[0]['_matched_tag'] == 'supermarket'
        assert results[0]['phone'] == '+234 90 1400 0001'

    @patch('app.scraping.overpass.requests.post')
    def test_skips_unnamed_nodes(self, mock_post):
        mock_post.return_value = _fake_response({'elements': [
            {'type': 'node', 'tags': {'shop': 'supermarket'}},  # no name
        ]})

        results = query_overpass(6.5244, 3.3792, shop_tags=['supermarket'], amenity_tags=[])

        assert results == []

    def test_no_tags_returns_empty_without_a_request(self):
        assert query_overpass(6.5244, 3.3792, shop_tags=[], amenity_tags=[]) == []

    @patch('app.scraping.overpass.requests.post')
    @patch('app.scraping.overpass.time.sleep', return_value=None)
    def test_retries_once_then_gives_up(self, mock_sleep, mock_post):
        mock_post.side_effect = Exception('rate limited')

        results = query_overpass(6.5244, 3.3792, shop_tags=['supermarket'], amenity_tags=[])

        assert results == []
        assert mock_post.call_count == 2
