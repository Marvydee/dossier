from urllib.parse import urljoin


def find_next_page_url(soup, current_url):
    """Detect a 'next page' pagination link (rel="next" or a labelled Next link)."""
    next_link = soup.find('a', rel='next')
    if next_link and next_link.get('href'):
        return urljoin(current_url, next_link['href'])

    for a in soup.find_all('a', href=True):
        label = a.get_text(strip=True).lower()
        aria  = (a.get('aria-label') or '').lower()
        if label in ('next', 'next »', '»', 'next page') or 'next' in aria:
            return urljoin(current_url, a['href'])

    return None
