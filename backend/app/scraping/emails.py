import re

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from .http import HTTP_HEADERS

EMAIL_REGEX = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'

JUNK_DOMAINS = {
    'example.com', 'test.com', 'domain.com', 'email.com',
    'youremail.com', 'sample.com', 'placeholder.com',
    'wix.com', 'wordpress.com', 'sentry.io', 'sentry-cdn.com',
    'github.com', 'githubusercontent.com', 'jquery.com',
    'google.com', 'facebook.com', 'instagram.com', 'twitter.com',
    'schema.org', 'w3.org', 'png', 'jpg', 'jpeg', 'gif', 'svg',
}


def _is_valid(email):
    if not re.match(r'^' + EMAIL_REGEX + r'$', email):
        return False
    domain = email.split('@')[1].lower()
    if any(junk in domain for junk in JUNK_DOMAINS):
        return False
    if any(p in email.lower() for p in ['noreply', 'no-reply', 'donotreply',
                                          'notifications', 'bounce', 'mailer']):
        return False
    return True


def extract_emails(website_url, timeout=8):
    """Visit a business website and extract any email addresses found."""
    if not website_url:
        return []

    emails = set()

    def scrape_page(url):
        try:
            r = requests.get(url, headers=HTTP_HEADERS, timeout=timeout, allow_redirects=True)
            soup = BeautifulSoup(r.text, 'html.parser')

            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('mailto:'):
                    candidate = href[7:].split('?')[0].strip()
                    if _is_valid(candidate):
                        emails.add(candidate.lower())

            for e in re.findall(EMAIL_REGEX, r.text):
                if _is_valid(e):
                    emails.add(e.lower())

            return soup, url
        except Exception:
            return None, url

    soup, base_url = scrape_page(website_url)
    if not soup:
        return []

    if not emails:
        for a in soup.find_all('a', href=True):
            text = (a.get_text() + a['href']).lower()
            if any(w in text for w in ['contact', 'about', 'reach us', 'get in touch']):
                full = urljoin(base_url, a['href'])
                if urlparse(full).netloc == urlparse(base_url).netloc:
                    scrape_page(full)
                    if emails:
                        break

    return list(emails)
