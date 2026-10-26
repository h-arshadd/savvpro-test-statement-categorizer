import re

_PREFIX = re.compile(r"^(?:(?:POS|DEBIT|CHECKCARD|CARD|PURCHASE|RECURRING)\s+)+")
_PROCESSOR = re.compile(r"^(?:SQ|TST|PP|PAYPAL|SP|APLPAY)\s*\*\s*")
_NON_WORD = re.compile(r"[^A-Z0-9& ]+")
# "ADS1234567890": a name stuck to a long number. Keep the name, drop the number.
_NAME_THEN_NUMBER = re.compile(r"^([A-Z]+)\d{4,}$")


def normalize_merchant(raw: str) -> str:
    """Turn a messy bank description into a clean merchant name."""
    text = raw.upper().strip().replace("'", "")
    text = _PREFIX.sub("", text)
    text = _PROCESSOR.sub("", text)
    text = _NON_WORD.sub(" ", text)
    words = [_NAME_THEN_NUMBER.sub(r"\1", w) for w in text.split()]
    kept = [w for w in words if not any(c.isdigit() for c in w)]
    return " ".join(kept or words)