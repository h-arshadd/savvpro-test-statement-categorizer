import datetime as dt
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel


class Status(str, Enum):
    CATEGORIZED = "categorized"
    NEEDS_REVIEW = "needs_review"
    EXCLUDED = "excluded"  # transfers, card payments: not spending


class RawTransaction(BaseModel):
    row: int  # original row number in the file
    date: dt.date | None
    description: str
    amount: Decimal  # negative = money out, positive = money in


class CategorizedTransaction(BaseModel):
    row: int
    date: dt.date | None
    description: str
    merchant: str  # normalized
    amount: Decimal
    category: str | None  # None while the row needs review
    suggestion: str | None = None  # best guess for rows that need review
    duplicate_of: int | None = None  # row number of the charge this one repeats
    user_set: bool = False  # the user chose this category themselves
    status: Status
    confidence: float
    reason: str  # why the brain decided this, shown to the user


class CategoryTotal(BaseModel):
    category: str
    total: Decimal  # net spend: refunds reduce it
    count: int


class Summary(BaseModel):
    categories: list[CategoryTotal]  # expense categories, biggest first
    income: Decimal
    excluded_count: int
    needs_review_count: int
    needs_review_net: Decimal  # net money out on rows still waiting for review