import re

# Valid Nigerian mobile prefixes (first 4 digits of the normalised 11-digit number)
VALID_PHONE_PREFIXES = {f'0{p}' for p in
                         list(range(700, 710)) + list(range(802, 820)) +
                         list(range(901, 910)) + [912, 913, 915, 916]}


def slugify(text):
    """Convert free text into a URL-friendly, lowercase, hyphenated slug."""
    text = text.strip().lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')


def normalise_phone(raw):
    """Convert any Nigerian phone format to the standard 11-digit 0XXXXXXXXXX.

    Returns '' if the number doesn't match a valid Nigerian mobile prefix.
    """
    if not raw:
        return ''

    digits = re.sub(r'\D', '', raw)
    if not digits:
        return ''

    if digits.startswith('234'):
        digits = '0' + digits[3:]
    elif len(digits) == 10 and not digits.startswith('0'):
        digits = '0' + digits

    if len(digits) != 11 or not digits.startswith('0'):
        return ''

    if digits[:4] not in VALID_PHONE_PREFIXES:
        return ''

    return digits
