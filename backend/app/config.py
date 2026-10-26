import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]  # backend/

RULES_FILE = Path(os.environ.get("RULES_FILE", BASE_DIR / "data" / "rules.json"))

CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]