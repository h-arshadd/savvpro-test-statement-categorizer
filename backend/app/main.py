from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.categorizer import categorize_all, summarize
from app.csv_parser import ParseError
from app.normalizer import normalize_merchant
from app.parser import MAX_BYTES, parse_statement
from app.rules import ALL_CATEGORIES
from app.rules_store import RulesStore
from app.schemas import RuleRequest, RuleResponse, StatementResponse

app = FastAPI(title="Statement Categorizer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


def get_store() -> RulesStore:
    return RulesStore(config.RULES_FILE)


Store = Annotated[RulesStore, Depends(get_store)]
SignMode = Literal["auto", "negative_is_expense", "positive_is_expense"]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/categories")
def categories() -> list[str]:
    return list(ALL_CATEGORIES)


@app.post("/api/statements", response_model=StatementResponse)
async def upload_statement(
    store: Store,
    file: Annotated[UploadFile, File()],
    sign: SignMode = "auto",
    day_first: bool = False,
    keep_rows: Annotated[list[int] | None, Query()] = None,
) -> StatementResponse:
    """Read a statement, categorize every row and return the rows plus totals.

    keep_rows: rows the user confirmed are real charges (not duplicates).
    """
    filename = file.filename or ""
    content = await file.read(MAX_BYTES + 1)  # never read more than the limit allows
    try:
        parsed = parse_statement(content, filename, sign=sign, day_first=day_first)
    except ParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    results = categorize_all(parsed.transactions, store.all(), keep_rows or [])
    return StatementResponse(
        filename=filename or "statement",
        transactions=results,
        summary=summarize(results),
        warnings=parsed.warnings,
    )


@app.get("/api/rules")
def list_rules(store: Store) -> dict[str, str]:
    return store.all()


@app.post("/api/rules", response_model=RuleResponse)
def save_rule(body: RuleRequest, store: Store) -> RuleResponse:
    """Remember the user's fix: this merchant always gets this category from now on."""
    if body.category not in ALL_CATEGORIES:
        raise HTTPException(status_code=422, detail=f"Unknown category '{body.category}'.")
    merchant = normalize_merchant(body.description)
    if not merchant:
        raise HTTPException(status_code=422, detail="That description has no merchant name in it.")
    store.set(merchant, body.category)
    return RuleResponse(merchant=merchant, category=body.category)


@app.delete("/api/rules/{merchant}")
def delete_rule(merchant: str, store: Store) -> dict[str, str]:
    """Forget a saved rule, so rows from that merchant are decided by the built-in rules again."""
    if not store.delete(merchant):
        raise HTTPException(status_code=404, detail="There is no saved rule for that merchant.")
    return {"deleted": merchant}