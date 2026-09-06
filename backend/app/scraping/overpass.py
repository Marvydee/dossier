import time

import requests

OVERPASS_URL = 'https://overpass-api.de/api/interpreter'
DEFAULT_RADIUS_M = 15000


def query_overpass(lat, lon, shop_tags, amenity_tags, *, radius_m=DEFAULT_RADIUS_M, timeout=35):
    """Query OpenStreetMap's Overpass API for shops/amenities around a point.

    Uses a radius search around known coordinates rather than name-based area
    matching. That was tested live and found broken: OSM's `is_in:country` tag
    is essentially unpopulated (0 results for every city tried), and even a
    country-boundary-based fix pulled in an unrelated same-named place in
    another country alongside the intended city. A radius around a known
    city-centre point has no such ambiguity and was verified working live.

    Returns each matching node's tags plus '_matched_tag': the shop= or
    amenity= value that matched, so the caller can map it back to a category.
    """
    if not shop_tags and not amenity_tags:
        return []

    clauses = []
    if shop_tags:
        shop_regex = '|'.join(shop_tags)
        clauses.append(f'node["shop"~"{shop_regex}"](around:{radius_m},{lat},{lon});')
    if amenity_tags:
        amenity_regex = '|'.join(amenity_tags)
        clauses.append(f'node["amenity"~"{amenity_regex}"](around:{radius_m},{lat},{lon});')

    query = f'[out:json][timeout:30];\n({"".join(clauses)});\nout body;'

    data = None
    for attempt in range(2):
        try:
            resp = requests.post(OVERPASS_URL, data={'data': query}, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception:
            if attempt == 0:
                time.sleep(1.5)

    if data is None:
        return []

    results = []
    for element in data.get('elements', []):
        tags = element.get('tags', {})
        name = tags.get('name', '').strip()
        if not name:
            continue

        matched_tag = tags.get('shop') or tags.get('amenity') or ''
        street    = tags.get('addr:street', '')
        addr_city = tags.get('addr:city', '')
        address   = ', '.join(p for p in (street, addr_city) if p)

        results.append({
            'name':         name,
            'phone':        tags.get('phone') or tags.get('contact:phone', ''),
            'email':        tags.get('email') or tags.get('contact:email', ''),
            'website':      tags.get('website') or tags.get('contact:website', ''),
            'address':      address,
            '_matched_tag': matched_tag,
        })

    return results
