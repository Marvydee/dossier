import re


def _normalise_name(name):
    name = name.lower()
    name = re.sub(r'[^\w\s]', '', name)
    return re.sub(r'\s+', ' ', name).strip()


def match_city(address, cities):
    """Find which of the given cities (list of {slug, label}) is mentioned in
    a free-text address. Returns the city's slug, or '' if none match."""
    address_lower = address.lower()
    for city in cities:
        if city['label'].lower() in address_lower:
            return city['slug']
    return ''


def deduplicate(records):
    """Merge records that share a normalised phone number or a similar business name.

    When merging, keeps the most complete value for each field (e.g. email from
    one record, website from another), and tags the merged record's source as
    'Multiple' when it was found on more than one source.
    """
    merged = []

    for rec in records:
        rec_name_norm = _normalise_name(rec.get('name', ''))
        rec_phone     = rec.get('phone', '')
        match = None

        for existing in merged:
            existing_name_norm = _normalise_name(existing.get('name', ''))

            same_phone = bool(rec_phone) and rec_phone == existing.get('phone', '')
            same_name  = bool(rec_name_norm) and bool(existing_name_norm) and (
                rec_name_norm in existing_name_norm or existing_name_norm in rec_name_norm
            )

            if same_phone or same_name:
                match = existing
                break

        if match is None:
            rec['sources'] = {rec.get('source', '')}
            merged.append(rec)
            continue

        for field in ('email', 'website', 'address', 'phone', 'category'):
            if not match.get(field) and rec.get(field):
                match[field] = rec[field]
        if len(rec.get('name', '')) > len(match.get('name', '')):
            match['name'] = rec['name']

        match['sources'].add(rec.get('source', ''))

    for rec in merged:
        sources = {s for s in rec.get('sources', set()) if s}
        rec['source'] = 'Multiple' if len(sources) > 1 else next(iter(sources), '')
        rec.pop('sources', None)

    return merged
