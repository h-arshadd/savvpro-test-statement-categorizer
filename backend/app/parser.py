from pathlib import Path

from app.csv_parser import ParseError, ParseResult, parse_csv

MAX_BYTES = 5 * 1024 * 1024


def parse_statement(content: bytes, filename: str, **options) -> ParseResult:
    if not content:
        raise ParseError("The file is empty.")
    if len(content) > MAX_BYTES:
        raise ParseError("The file is too large (limit 5 MB).")
    ext = Path(filename).suffix.lower()
    if ext == ".csv":
        return parse_csv(content, **options)
    raise ParseError(f"Unsupported file type '{ext or filename}'. Upload a .csv statement.")