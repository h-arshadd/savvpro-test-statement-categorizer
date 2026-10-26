import csv
import datetime as dt
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal

from app.models import RawTransaction
from app.normalizer import normalize_merchant
from app.rules import EXPENSE_CATEGORIES, RULES


class ParseError(Exception):
    """The file cannot be read as a statement."""


@dataclass
class ParseResult:
    transactions: list[RawTransaction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


_SIGN_MODES = ("auto", "negative_is_expense", "positive_is_expense")

# Header names per field, in priority order ("description" beats "details").
_HEADERS = {
    "date": ("date", "transaction date", "trans date", "posting date", "post date", "posted date"),
    "description": ("description", "transaction description", "merchant", "payee", "narrative", "memo", "details"),
    "amount": ("amount", "transaction amount", "amt"),
    "debit": ("debit", "debits", "withdrawal", "withdrawals", "money out", "charges"),
    "credit": ("credit", "credits", "deposit", "deposits", "money in", "payments"),
}

_DATE_FORMATS = (
    "%Y-%m-%d", "%Y/%m/%d",
    "%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y", "%d/%m/%y",
    "%m-%d-%Y", "%d-%m-%Y",
    "%d.%m.%Y", "%d-%b-%Y", "%d %b %Y", "%b %d, %Y",
)

# Known business-expense merchants. Used only as evidence for which sign means "money out".
_EXPENSE_WORDS = tuple(
    re.compile(rf"\b{re.escape(p)}\b")
    for rule in RULES if rule.category in EXPENSE_CATEGORIES
    for p in rule.patterns
)

_CURRENCY_CODE = re.compile(r"^(?:USD|EUR|GBP|CAD|AUD|INR|PKR|JPY|CHF)\s*|\s*(?:USD|EUR|GBP|CAD|AUD|INR|PKR|JPY|CHF)$")

# Summary rows at the bottom of a statement (only skipped when they have no date).
_FOOTER = re.compile(
    r"^(totals?|(opening|closing|ending|beginning|previous|new) balance)\b", re.IGNORECASE
)


def parse_csv(content: bytes, *, sign: str = "auto", day_first: bool = False) -> ParseResult:
    """Read a CSV statement. Output convention: negative = money out, positive = money in.

    sign: "auto" guesses from the data, or force "negative_is_expense" / "positive_is_expense".
    day_first: how to read ambiguous dates like 03/04/2026.
    """
    if sign not in _SIGN_MODES:
        raise ValueError(f"sign must be one of {_SIGN_MODES}")

    text = _decode(content)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=_detect_delimiter(text))
    rows = [(reader.line_num, row) for row in reader]
    header_idx, cols = _find_header(rows)

    warnings: list[str] = []
    parsed: list[tuple[int, str, str, Decimal]] = []
    for line_no, row in rows[header_idx + 1:]:
        if not any(c.strip() for c in row):
            continue
        date_text = _clean_date_text(_cell(row, cols, "date"))
        description = " ".join(_cell(row, cols, "description").split())
        if not date_text and _FOOTER.match(description):
            warnings.append(f"Row {line_no}: skipped summary row '{description}'.")
            continue
        try:
            amount = _row_amount(row, cols)
        except ValueError as exc:
            warnings.append(f"Row {line_no}: {exc} - row skipped.")
            continue
        if amount is None:
            warnings.append(f"Row {line_no}: no amount - row skipped.")
            continue
        parsed.append((line_no, date_text, description, amount))

    if not parsed:
        raise ParseError("No transactions found in the file.")

    if "amount" in cols and sign != "negative_is_expense":
        if sign == "positive_is_expense" or _purchases_look_positive(parsed, warnings):
            parsed = [(n, d, desc, -a) for n, d, desc, a in parsed]

    fmt, ambiguous = _pick_date_format([d for _, d, _, _ in parsed if d], day_first)
    if ambiguous and fmt:
        order = "day/month" if fmt.startswith("%d") else "month/day"
        warnings.append(f"Date order is ambiguous in this file; assumed {order}.")

    transactions: list[RawTransaction] = []
    bad_dates = 0
    for line_no, date_text, description, amount in parsed:
        date = None
        if date_text and fmt:
            try:
                date = dt.datetime.strptime(date_text, fmt).date()
            except ValueError:
                date = None
        if date is None:
            bad_dates += 1
        transactions.append(
            RawTransaction(row=line_no, date=date, description=description, amount=amount)
        )
    if bad_dates:
        warnings.append(f"{bad_dates} row(s) have a missing or unreadable date.")

    return ParseResult(transactions=transactions, warnings=warnings)


def _purchases_look_positive(
    parsed: list[tuple[int, str, str, Decimal]], warnings: list[str]
) -> bool:
    """Decide the sign convention from rows whose merchant we know is an expense.

    Counting positive versus negative rows is not safe: a month with a few purchases and
    several client payments would look "flipped". Known expense merchants are better
    evidence. With no evidence we assume negative = money out and say so.
    """
    positive = negative = 0
    for _, _, description, amount in parsed:
        merchant = normalize_merchant(description)
        if amount != 0 and any(p.search(merchant) for p in _EXPENSE_WORDS):
            if amount > 0:
                positive += 1
            else:
                negative += 1

    if positive > negative:
        warnings.append(
            f"{positive} of {positive + negative} rows from known business merchants were "
            "positive, so purchases were assumed to be positive in this file and the signs "
            "were flipped. Use 'Amount signs' if that is wrong."
        )
        return True
    if positive == negative:
        warnings.append(
            "Could not tell which sign means money out (no known merchants to go by). "
            "Assumed negative amounts are purchases. Use 'Amount signs' if that is wrong."
        )
    return False


def parse_amount(text: str) -> Decimal | None:
    """'($1,234.50)' -> -1234.50, '12.50-' -> -12.50, '9.99 CR' -> 9.99, '1.200,50' -> 1200.50.

    Blank -> None. Anything else (stray letters, '1.2.3') raises ValueError so the row is
    skipped with a warning instead of being read wrongly.
    """
    s = text.strip().replace("\u2212", "-")
    if not s:
        return None
    negative = s.startswith("(") and s.endswith(")")
    # CR (credit) is money in, DR (debit) is money out, as on many card statements.
    marker = re.search(r"\s*\b(CR|DR)\.?$", s, re.IGNORECASE)
    if marker:
        negative = negative or marker.group(1).upper() == "DR"
        s = s[: marker.start()]
    s = _CURRENCY_CODE.sub("", s.strip())
    s = re.sub(r"[\s$€£¥₹()]", "", s)
    if s.endswith("-"):
        negative, s = True, s[:-1]
    elif s.startswith("-"):
        negative, s = True, s[1:]
    s = _normalize_separators(s.lstrip("+"))
    if not s:
        return None
    if not re.fullmatch(r"\d+(\.\d+)?|\.\d+", s):
        raise ValueError(f"cannot read amount '{text.strip()}'")
    value = Decimal(s)
    return -value if negative else value


def _normalize_separators(s: str) -> str:
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):  # 1.234,56
            return s.replace(".", "").replace(",", ".")
        return s.replace(",", "")  # 1,234.56
    if "," in s:
        if re.fullmatch(r"\d+,\d{1,2}", s):  # 12,50
            return s.replace(",", ".")
        return s.replace(",", "")  # 1,234
    return s


def _row_amount(row: list[str], cols: dict[str, int]) -> Decimal | None:
    if "amount" in cols:
        return parse_amount(_cell(row, cols, "amount"))
    debit = parse_amount(_cell(row, cols, "debit"))
    credit = parse_amount(_cell(row, cols, "credit"))
    if debit is None and credit is None:
        return None
    return abs(credit or Decimal(0)) - abs(debit or Decimal(0))


def _cell(row: list[str], cols: dict[str, int], key: str) -> str:
    i = cols.get(key)
    return row[i].strip() if i is not None and i < len(row) else ""


def _clean_date_text(text: str) -> str:
    return re.sub(r"[ T]\d{1,2}:\d{2}.*$", "", text.strip())


def _pick_date_format(values: list[str], day_first: bool) -> tuple[str | None, bool]:
    counts = {}
    for fmt in _DATE_FORMATS:
        n = 0
        for v in values:
            try:
                dt.datetime.strptime(v, fmt)
                n += 1
            except ValueError:
                pass
        counts[fmt] = n
    best = max(counts.values(), default=0)
    if best == 0:
        return None, False
    winners = [f for f in _DATE_FORMATS if counts[f] == best]
    if len(winners) > 1 and day_first:
        return next((f for f in winners if f.startswith("%d")), winners[0]), True
    return winners[0], len(winners) > 1


def _decode(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("latin-1")


def _detect_delimiter(text: str) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()][:10]
    best, best_count = ",", 0
    for d in (",", ";", "\t", "|"):
        count = sum(ln.count(d) for ln in lines)
        if count > best_count:
            best, best_count = d, count
    return best


def _find_header(rows: list[tuple[int, list[str]]]) -> tuple[int, dict[str, int]]:
    for idx, (_, row) in enumerate(rows[:30]):
        names = [c.strip().lower() for c in row]
        cols: dict[str, int] = {}
        for key, options in _HEADERS.items():
            for option in options:
                if option in names:
                    cols[key] = names.index(option)
                    break
        has_money = "amount" in cols or "debit" in cols or "credit" in cols
        if "date" in cols and "description" in cols and has_money:
            return idx, cols
    raise ParseError(
        "Could not find the column headers. Expected columns like Date, Description and "
        "Amount (or Debit/Credit)."
    )