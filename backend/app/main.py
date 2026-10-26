import json
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.categorizer import categorize_all, summarize
from app.csv_parser import ParseError
from app.parser import MAX_BYTES, parse_statement
from app.rules import ALL_CATEGORIES
from app.schemas import StatementResponse

app = FastAPI(title="Statement Categorizer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

SignMode = Literal["auto", "negative_is_expense", "positive_is_expense"]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/categories")
def categories() -> list[str]:
    return list(ALL_CATEGORIES)


def _read_overrides(raw: str | None) -> dict[int, str]:
    """Parse the user's row fixes: a JSON object like {"5": "Meals"} (row number -> category)."""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        overrides = {int(row): category for row, category in data.items()}
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(
            status_code=422, detail="overrides must be a JSON object of row number to category."
        ) from exc
    unknown = sorted({c for c in overrides.values() if c not in ALL_CATEGORIES}, key=str)
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown category '{unknown[0]}'.")
    return overrides


@app.post("/api/statements", response_model=StatementResponse)
async def upload_statement(
    file: Annotated[UploadFile, File()],
    overrides: Annotated[str | None, Form()] = None,
    sign: SignMode = "auto",
    day_first: bool = False,
    keep_rows: Annotated[list[int] | None, Query()] = None,
) -> StatementResponse:
    """Read a statement, categorize every row and return the rows plus totals.

    overrides: categories the user chose for specific rows, as JSON {"row": "category"}.
    keep_rows: rows the user confirmed are real charges (not duplicates).
    Nothing is stored: the same file is sent again with the user's fixes each time.
    """
    fixes = _read_overrides(overrides)
    filename = file.filename or ""
    content = await file.read(MAX_BYTES + 1)  # never read more than the limit allows
    try:
        parsed = parse_statement(content, filename, sign=sign, day_first=day_first)
    except ParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    results = categorize_all(parsed.transactions, fixes, keep_rows or [])
    return StatementResponse(
        filename=filename or "statement",
        transactions=results,
        summary=summarize(results),
        warnings=parsed.warnings,
    )