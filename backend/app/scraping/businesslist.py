import time

import requests
from bs4 import BeautifulSoup

from .http import HTTP_HEADERS
from .pagination import find_next_page_url


def scrape_businesslist(category_slug, city_slug, *, max_pages, request_delay, timeout):
    """Search BusinessList Nigeria (businesslist.com.ng) for businesses matching category + city.

    Real listing markup (verified against the live site, 2026-08-27):
      <div class="company ..."> (skip the "company_ad" sponsored variant)
        <div class="company_header"><h3>N | <a href="/company/...">Name</a></h3>
        <div class="address">...</div>
        <div class="cont">
          <div class="s"><i class="fa fa-phone"/><span>+234 ...</span></div>
          <div class="s"><i class="fa fa-envelope"/><span>E-mail or actual address</span></div>
          <div class="s"><i class="fa fa-globe"/><span>Website or placeholder</span></div>
    Pagination uses a real rel="next" arrow link, handled by find_next_page_url.
    """
    results = []
    url  = f'https://www.businesslist.com.ng/category/{category_slug}/city:{city_slug}'
    page = 0

    while page < max_pages:
        page += 1
        try:
            resp = requests.get(url, headers=HTTP_HEADERS, timeout=timeout)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
        except Exception:
            break

        blocks = [b for b in soup.find_all('div', class_='company')
                  if 'company_ad' not in b.get('class', [])]
        if not blocks:
            break

        for block in blocks:
            name_link = block.select_one('.company_header h3 a')
            name = name_link.get_text(strip=True) if name_link else ''
            if not name:
                continue

            addr_el = block.select_one('.address')
            address = addr_el.get_text(' ', strip=True) if addr_el else ''

            phone = email = website = ''

            phone_icon = block.select_one('.s i.fa-phone')
            if phone_icon:
                span = phone_icon.find_parent('div', class_='s').find('span')
                text = span.get_text(strip=True) if span else ''
                if any(ch.isdigit() for ch in text):
                    phone = text

            mail_icon = block.select_one('.s i.fa-envelope')
            if mail_icon:
                span = mail_icon.find_parent('div', class_='s').find('span')
                text = span.get_text(strip=True) if span else ''
                if '@' in text:
                    email = text

            web_icon = block.select_one('.s i.fa-globe')
            if web_icon:
                span = web_icon.find_parent('div', class_='s').find('span')
                text = span.get_text(strip=True) if span else ''
                if '.' in text and text.lower() != 'website':
                    website = text

            results.append({'name': name, 'phone': phone, 'email': email,
                             'website': website, 'address': address})

        next_url = find_next_page_url(soup, resp.url)
        if not next_url or page >= max_pages:
            break

        time.sleep(request_delay)
        url = next_url

    return results
