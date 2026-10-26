# Statement Categorizer

Upload a business credit card statement (CSV) and get every transaction sorted into a tax category, with a total per category. If the app is not sure about a row, it says so and asks you instead of guessing.

**Use case:** a freelancer or small business owner who needs their business card statement sorted at tax time.

The part that decides categories is plain Python rules in `backend/app/`. No AI model is used at runtime and there are no API keys. See [DESIGN.md](DESIGN.md) for how it decides and [AI_USAGE.md](AI_USAGE.md) for how AI tools were used to build it.

## What you can do in the app

- Upload a `.csv` statement (up to 5 MB).
- See every row with its category and whether it was categorized, excluded or needs review (filterable).
- See totals per category, income, and how many rows are excluded or waiting for review.
- Fix rows in **Needs Review**: accept the suggestion or pick a category. Your choice is saved as a rule for that merchant, so it applies to future uploads too.
- See your saved rules in the **Saved rules** list under the upload form and remove any of them.
- Confirm that a flagged possible duplicate is a real charge.
- Download the result as a CSV (all rows, with status, category, suggestion and the reason for each decision).
- Choose how to read the file if it guesses wrong: sign convention (which amounts are expenses) and day-first dates.

## Requirements

- Python 3.10 or newer
- Node.js (developed and tested with Node 24)

## Run it

You need two terminals: one for the backend, one for the frontend.

### 1. Backend (terminal 1)

Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

macOS / Linux:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API runs at http://127.0.0.1:8000. Check http://127.0.0.1:8000/api/health, it should return `{"status":"ok"}`. Interactive API docs are at http://127.0.0.1:8000/docs.

### 2. Frontend (terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The dev server proxies `/api` to the backend on port 8000, so start the backend first.

### 3. Try it

Upload `sample_data/freelancer_card.csv` (a fake statement). It has 17 rows: 8 are categorized, 2 are excluded (a transfer and a card payment), and 7 need review (a cafe, an Amazon purchase and refund, a possible duplicate, and so on).

## Run the tests

Run from the `backend/` folder with the virtual environment active:

```bash
python -m pytest
```

## Configuration

Both settings are optional environment variables for the backend.

| Variable | Default | What it does |
|---|---|---|
| `RULES_FILE` | `backend/data/rules.json` | Where your saved merchant rules are stored. |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated list of frontend origins allowed to call the API. |

Uploaded statements are processed in memory and are never saved. Only your saved merchant rules are written to disk (`backend/data/` is git-ignored).

## API

| Method and path | What it does |
|---|---|
| `GET /api/health` | Health check. |
| `GET /api/categories` | List of category names. |
| `POST /api/statements` | Upload a statement (multipart field `file`). Optional query: `sign` (`auto`, `negative_is_expense`, `positive_is_expense`), `day_first` (true/false), `keep_rows` (repeatable row number to confirm as a real charge). Returns the categorized rows, a summary and any warnings. |
| `GET /api/rules` | Saved merchant rules. |
| `POST /api/rules` | Save a rule: `{ "description": "JOES CAFE 9921", "category": "Meals" }`. |
| `DELETE /api/rules/{merchant}` | Remove a saved rule (the merchant name as returned by `GET /api/rules`, URL-encoded). 404 if there is no such rule. |

Money values in responses are strings (for example `"-59.99"`) to avoid floating point errors. Negative means money out, positive means money in.

## Supported CSV files

- Header row with a date, a description and either one amount column or separate debit/credit columns (many common header names are recognised). A few lines of text above the header are fine.
- Comma, semicolon, tab or pipe separated.
- Amounts like `-59.99`, `($1,234.50)`, `12.50-` and `1.200,50`.
- Several date formats, including `2026-09-01`, `09/01/2026` and `01.09.2026`.
- Summary rows such as "Total" or "Closing balance" are skipped. Rows that cannot be read are skipped with a warning shown in the app.

PDF and Excel files are not supported.

## Project layout

```
backend/
  app/
    main.py          API routes
    csv_parser.py    reads a CSV into transactions
    parser.py        file type and size checks
    normalizer.py    cleans messy merchant descriptions
    rules.py         the category rules and their confidence
    categorizer.py   the decision logic and totals
    rules_store.py   saves the user's merchant rules to a JSON file
    models.py        data models
    schemas.py       API request and response models
    config.py        environment settings
  tests/             pytest tests
  requirements.txt
frontend/            React + Vite app
sample_data/         fake statement for trying the app
```