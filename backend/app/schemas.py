from pydantic import BaseModel

from app.models import CategorizedTransaction, Summary


class StatementResponse(BaseModel):
    filename: str
    transactions: list[CategorizedTransaction]
    summary: Summary
    warnings: list[str]