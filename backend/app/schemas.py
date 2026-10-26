from pydantic import BaseModel, Field

from app.models import CategorizedTransaction, Summary


class StatementResponse(BaseModel):
    filename: str
    transactions: list[CategorizedTransaction]
    summary: Summary
    warnings: list[str]


class RuleRequest(BaseModel):
    description: str = Field(min_length=1, max_length=300)  # the row's description
    category: str


class RuleResponse(BaseModel):
    merchant: str
    category: str