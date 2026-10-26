import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from rapidfuzz import fuzz

from app.models import CategorizedTransaction, CategoryTotal, RawTransaction, Status, Summary
from app.normalizer import normalize_merchant
from app.rules import (
    EXCLUDED_CATEGORIES, EXPENSE_CATEGORIES, INCOME, REVIEW_THRESHOLD, RULES, Rule,
)

FUZZY_MIN_SCORE = 88
FUZZY_MIN_PATTERN_LEN = 6
FUZZY_CONFIDENCE = 0.6  # below the threshold on purpose: a fuzzy match only suggests

_REFUND_WORDS = re.compile(r"\b(REFUND|RETURN|REVERSAL|CREDIT|CHARGEBACK)\b", re.IGNORECASE)


@dataclass(frozen=True)
class _Entry:
    rule: Rule
    pattern: str
    regex: re.Pattern
    words: int


_ENTRIES = tuple(
    _Entry(rule, p, re.compile(rf"\b{re.escape(p)}\b"), len(p.split()))
    for rule in RULES
    for p in rule.patterns
)


def categorize(txn: RawTransaction, override: str | None = None) -> CategorizedTransaction:
    """Decide one row. `override` is a category the user chose for this exact row."""
    merchant = normalize_merchant(txn.description)

    if override:
        status = Status.EXCLUDED if override in EXCLUDED_CATEGORIES else Status.CATEGORIZED
        row = _build(txn, merchant, status, override, 1.0, f"You set this row to {override}.")
        return row.model_copy(update={"user_set": True})

    if txn.amount == 0:
        return _review(txn, merchant, "The amount is zero.")
    if not merchant:
        return _review(txn, merchant, "There is no description to work from.")

    matches = [e for e in _ENTRIES if _applies(e, txn.amount) and e.regex.search(merchant)]
    if matches:
        return _from_matches(txn, merchant, matches)

    fuzzy = _best_fuzzy(merchant, txn.amount)
    if fuzzy:
        entry, score = fuzzy
        return _review(
            txn, merchant,
            f"Looks like '{entry.pattern}' ({score:.0f}% similar) but it is not an exact match.",
            suggestion=entry.rule.category, confidence=FUZZY_CONFIDENCE,
        )

    if txn.amount > 0:
        if _REFUND_WORDS.search(txn.description):
            reason = "Looks like a refund, but the original merchant is not recognised."
        else:
            reason = "Money in from an unknown source: could be a refund or income."
    else:
        reason = "Unknown merchant."
    return _review(txn, merchant, reason)


def categorize_all(
    transactions: Sequence[RawTransaction],
    overrides: Mapping[int, str] | None = None,
    keep_rows: Collection[int] = (),
) -> list[CategorizedTransaction]:
    """Categorize every row, then flag repeats of the same date, merchant and amount.

    `overrides` maps a row number to the category the user chose for it.
    `keep_rows` are rows the user confirmed are real charges: they are not flagged.
    """
    overrides = overrides or {}
    results = [categorize(t, overrides.get(t.row)) for t in transactions]
    keep = set(keep_rows)

    seen: dict[tuple, CategorizedTransaction] = {}
    for i, r in enumerate(results):
        if r.date is None or r.status is Status.EXCLUDED:
            continue
        first = seen.setdefault((r.date, r.merchant, r.amount), r)
        if first is r or r.row in keep or r.user_set:
            continue
        results[i] = r.model_copy(update={
            "status": Status.NEEDS_REVIEW,
            "category": None,
            "suggestion": first.category or first.suggestion,
            "duplicate_of": first.row,
            "confidence": min(r.confidence, 0.5),
            "reason": f"Possible duplicate of row {first.row}. Keep it if it is a real second charge.",
        })
    return results


def summarize(results: Sequence[CategorizedTransaction]) -> Summary:
    spend: dict[str, Decimal] = {}
    counts: dict[str, int] = {}
    income = Decimal(0)
    excluded = 0
    review_count = 0
    review_net = Decimal(0)

    for r in results:
        if r.status is Status.CATEGORIZED:
            if r.category == INCOME:
                income += r.amount
            else:
                spend[r.category] = spend.get(r.category, Decimal(0)) - r.amount
                counts[r.category] = counts.get(r.category, 0) + 1
        elif r.status is Status.EXCLUDED:
            excluded += 1
        else:
            review_count += 1
            review_net -= r.amount

    categories = sorted(
        (CategoryTotal(category=c, total=t, count=counts[c]) for c, t in spend.items()),
        key=lambda c: c.total,
        reverse=True,
    )
    return Summary(
        categories=categories,
        income=income,
        excluded_count=excluded,
        needs_review_count=review_count,
        needs_review_net=review_net,
    )


def _applies(entry: _Entry, amount: Decimal) -> bool:
    return not (entry.rule.money_in_only and amount <= 0)


def _contains(longer: str, shorter: str) -> bool:
    return f" {shorter} " in f" {longer} "


def _from_matches(
    txn: RawTransaction, merchant: str, matches: list[_Entry]
) -> CategorizedTransaction:
    # A pattern that is just part of a longer matching one is less specific, so drop it:
    # "AMAZON WEB SERVICES" replaces "AMAZON", "TRANSFER TO SAVINGS" replaces "TRANSFER TO".
    specific = [
        m for m in matches
        if not any(o.pattern != m.pattern and _contains(o.pattern, m.pattern) for o in matches)
    ]
    # Anything left that points to different categories is a real conflict
    # ("HILTON GARDEN PIZZA" is a hotel word and a food word). Do not pick one: ask.
    categories = sorted({m.rule.category for m in specific})
    if len(categories) > 1:
        return _review(
            txn, merchant,
            "Matches more than one category: " + ", ".join(categories) + ".",
            confidence=0.5,
        )

    entry = min(specific, key=lambda m: m.rule.confidence)
    rule = entry.rule
    money_in = txn.amount > 0 and rule.category in EXPENSE_CATEGORIES

    if rule.confidence < REVIEW_THRESHOLD:
        reason = rule.note or f"Only a weak match for {rule.category}."
        if money_in:
            reason += " This is money coming in, so it may be a refund."
        return _review(txn, merchant, reason, suggestion=rule.category, confidence=rule.confidence)

    if rule.category in EXCLUDED_CATEGORIES:
        return _build(
            txn, merchant, Status.EXCLUDED, rule.category, rule.confidence,
            f"Matched '{entry.pattern}': not spending, left out of the totals.",
        )
    if rule.category == INCOME:
        return _build(
            txn, merchant, Status.CATEGORIZED, INCOME, rule.confidence,
            f"Matched '{entry.pattern}': money received.",
        )
    if money_in:
        # Money coming in from a known merchant is only treated as a refund when the
        # description says so. Otherwise it could be a payout or something else: ask.
        if not _REFUND_WORDS.search(txn.description):
            return _review(
                txn, merchant,
                f"Money in from '{entry.pattern}'. Probably a refund, but the description "
                "does not say so. Please confirm.",
                suggestion=rule.category, confidence=0.5,
            )
        reason = (
            f"Refund from '{entry.pattern}', so it reduces {rule.category} "
            "instead of counting as income."
        )
    else:
        reason = f"Matched '{entry.pattern}'."
    return _build(txn, merchant, Status.CATEGORIZED, rule.category, rule.confidence, reason)


def _best_fuzzy(merchant: str, amount: Decimal) -> tuple[_Entry, float] | None:
    words = merchant.split()
    best: _Entry | None = None
    best_score = 0.0
    for e in _ENTRIES:
        if not _applies(e, amount) or len(e.pattern) < FUZZY_MIN_PATTERN_LEN or len(words) < e.words:
            continue
        for i in range(len(words) - e.words + 1):
            score = fuzz.ratio(" ".join(words[i:i + e.words]), e.pattern)
            if score > best_score:
                best, best_score = e, score
    if best is not None and best_score >= FUZZY_MIN_SCORE:
        return best, best_score
    return None


def _build(
    txn: RawTransaction, merchant: str, status: Status, category: str | None,
    confidence: float, reason: str, suggestion: str | None = None,
) -> CategorizedTransaction:
    return CategorizedTransaction(
        row=txn.row, date=txn.date, description=txn.description, merchant=merchant,
        amount=txn.amount, category=category, suggestion=suggestion, status=status,
        confidence=confidence, reason=reason,
    )


def _review(
    txn: RawTransaction, merchant: str, reason: str,
    suggestion: str | None = None, confidence: float = 0.0,
) -> CategorizedTransaction:
    return _build(txn, merchant, Status.NEEDS_REVIEW, None, confidence, reason, suggestion)