import re

_PREFIX = re.compile(r"^(?:(?:POS|DEBIT|CHECKCARD|CARD|PURCHASE|RECURRING)\s+)+")
_PROCESSOR = re.compile(r"^(?:SQ|TST|PP|PAYPAL|SP|APLPAY)\s*\*\s*")
_NON_WORD = re.compile(r"[^A-Z0-9& ]+")


def normalize_merchant(raw: str) -> str:
    """Turn a messy bank description into a clean merchant name."""
    text = raw.upper().strip().replace("'", "")
    text = _PREFIX.sub("", text)
    text = _PROCESSOR.sub("", text)
    text = _NON_WORD.sub(" ", text)
    words = text.split()
    kept = [w for w in words if not any(c.isdigit() for c in w)]
    return " ".join(kept or words)