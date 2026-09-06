import pytest

from app.scraping.phone import normalise_phone, slugify


class TestNormalisePhone:

    @pytest.mark.parametrize('raw,expected', [
        ('+2348031234567', '08031234567'),
        ('2348031234567', '08031234567'),
        ('8031234567', '08031234567'),
        ('+2347011234567', '07011234567'),
        ('09121234567', '09121234567'),
        ('09131234567', '09131234567'),
        ('09151234567', '09151234567'),
        ('09161234567', '09161234567'),
        ('0819 123 4567', '08191234567'),
    ])
    def test_valid_numbers_normalise(self, raw, expected):
        assert normalise_phone(raw) == expected

    @pytest.mark.parametrize('raw', [
        '',
        None,
        '+234 1 496 1607',      # Lagos landline, not a mobile prefix — real number seen live on BusinessList
        '08201234567',          # 0820 is outside the 0802-0819 valid range
        '07101234567',          # 0710 is outside the 0700-0709 valid range
        '09171234567',          # 0917 is not in the valid list
        '123',                  # too short / garbage
        '070-123-4567',         # only 10 digits once hyphens are stripped
    ])
    def test_invalid_numbers_rejected(self, raw):
        assert normalise_phone(raw) == ''

    def test_strips_non_digit_formatting(self):
        assert normalise_phone('080-312-34567') == '08031234567'


class TestSlugify:

    @pytest.mark.parametrize('text,expected', [
        ('Port Harcourt', 'port-harcourt'),
        ('fabric store', 'fabric-store'),
        ('  Lagos  ', 'lagos'),
        ('Ado-Ekiti', 'ado-ekiti'),
        ("São Paulo".lower(), 's-o-paulo'),
    ])
    def test_slugify(self, text, expected):
        assert slugify(text) == expected
