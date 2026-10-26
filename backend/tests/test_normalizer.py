import pytest

from app.normalizer import normalize_merchant


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("ADOBE CREATIVE CLOUD", "ADOBE CREATIVE CLOUD"),
        ("UBER *TRIP HELP.UBER.COM", "UBER TRIP HELP UBER COM"),
        ("JOES CAFE 9921", "JOES CAFE"),
        ("SQ *BLUE BOTTLE COFFEE", "BLUE BOTTLE COFFEE"),
        ("AMAZON MKTP US*2K4X91", "AMAZON MKTP US"),
        ("ZOOM.US 888-799-9666", "ZOOM US"),
        ("POS DEBIT STAPLES 00123", "STAPLES"),
        ("  joe's   diner  ", "JOES DINER"),
        ("7-ELEVEN 1234", "ELEVEN"),
        ("GOOGLE*ADS1234567890", "GOOGLE ADS"),  # name stuck to a long number
        ("ZOOM 3X9Q", "ZOOM"),  # mixed code is still dropped
    ],
)
def test_normalize_merchant(raw, expected):
    assert normalize_merchant(raw) == expected