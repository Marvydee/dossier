import time

import requests
from bs4 import BeautifulSoup

from .http import HTTP_HEADERS
from .pagination import find_next_page_url


def scrape_finelib(category_slug, *, max_pages, request_delay, timeout):
    """Search Finelib Nigeria (finelib.com) for businesses in a category.

    Unlike BusinessList, finelib.com has no city in its category URLs — a category
    page lists businesses nationwide, so the caller matches city from each result's
    address text (see scraping.dedupe.match_city).

    Real listing markup (verified against the live site, 2026-08-27):
      <div class="box-682 bg-none">
        <div class="box-headings">...<a href="/listing/Name/id/">Name</a></div>
        <div class="listing-info-img">
          <div class="cmpny-lstng-1">address / location text</div>
          <div class="tel-no-div"><div class="cmpny-lstng-1">phone number</div></div>
    """
    results = []
    url  = f'https://www.finelib.com/shopping/{category_slug}'
    page = 0

    while page < max_pages:
        page += 1
        try:
            resp = requests.get(url, headers=HTTP_HEADERS, timeout=timeout)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
        except Exception:
            break

        blocks = [b for b in soup.find_all('div', class_='box-682')
                  if b.find('div', class_='box-headings') and b.find('div', class_='listing-info-img')]
        if not blocks:
            break

        for block in blocks:
            name_link = block.select_one('.box-headings a')
            name = name_link.get_text(strip=True) if name_link else ''
            if not name:
                continue

            info_divs = block.select('.listing-info-img .cmpny-lstng-1')
            address = info_divs[0].get_text(strip=True) if len(info_divs) > 0 else ''
            phone   = info_divs[1].get_text(strip=True) if len(info_divs) > 1 else ''

            results.append({'name': name, 'phone': phone, 'email': '',
                             'website': '', 'address': address})

        next_url = find_next_page_url(soup, resp.url)
        if not next_url or page >= max_pages:
            break

        time.sleep(request_delay)
        url = next_url

    return results
