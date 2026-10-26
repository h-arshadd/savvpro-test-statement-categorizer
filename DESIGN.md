# Design

## Use case

**A freelancer or small business owner reading their business credit card statement at tax time.**

They download a CSV from their card provider and need every charge sorted into a category they can use on a tax return, plus a total per category. The expensive mistake here is a confident wrong answer: a personal dinner filed as a business expense, or a refund counted as income. So the app is built around one rule: **if it is not sure, it says so and asks.**

Categories: Software & Subscriptions, Travel, Meals, Office Supplies, Advertising, Phone & Internet, Interest & Bank Fees, and **Other Business Expense** for anything that does not fit. Three more are not business spending: **Income**, **Transfers & Card Payments** and **Personal (not business)**. The last two are shown in the table but left out of the totals. Personal exists because a business card often carries a personal charge, and the user needs a way to say so.

This is a bookkeeping helper, not tax advice.

## The flow

```
Upload CSV -> Read rows -> Clean merchant name -> The brain -> Category / Needs Review / Not counted
                                                                  |
                          User changes any row -> same file sent again with the changes
```

The backend is stateless. It reads the file in memory, never stores the statement and keeps no data between requests. When the user changes a row, the frontend sends the same file again with the changes (`overrides`, a map of row number to category), so the result is always computed fresh from the file plus those changes. Close the page and they are gone.

## The brain

The brain is ordinary Python: a small list of rules plus a fixed order of checks. No AI model, no training data. Every decision comes with a plain-English reason that the API returns with the row.

### 1. Clean the merchant name (`normalizer.py`)

Bank descriptions are noisy: `SQ *BLUE BOTTLE COFFEE`, `AMAZON MKTP US*2K4X91`, `POS DEBIT STAPLES 00123`. The normalizer uppercases, strips prefixes like `POS`, `DEBIT`, `CARD`, strips processor prefixes like `SQ *` and `PAYPAL *`, removes punctuation, and drops any word that contains a digit (store numbers, reference codes). So `JOES CAFE 9921` becomes `JOES CAFE`. A name stuck to a long number is kept without the number: `GOOGLE*ADS1234567890` becomes `GOOGLE ADS`.

### 2. Decide the row (`categorizer.py`), in this order

1. **A category the user chose for this row wins.** It applies to that exact row only, not to the merchant (confidence 1.0).
2. **Zero amount or empty description** goes to Needs Review. There is nothing to judge.
3. **Match against the rules.** Rules are whole-word phrases matched against the cleaned name (`AMAZON` does not match `AMAZONIA`).
   - If one matching phrase is just a part of a longer matching one, the longer wins: `AMAZON WEB SERVICES` (Software) replaces `AMAZON` (Office Supplies).
   - If what is left still points to **different categories**, the row goes to review and names both. Length does not decide: `HILTON GARDEN PIZZA` is a hotel word and a food word, and the brain does not pick.
4. **Confidence threshold.** Each rule has a confidence. Below **0.8** the row goes to Needs Review with the rule's category as a *suggestion*, not an answer.
5. **Money in from a known merchant.** It is only treated as a refund (it reduces that category) if the description says so (`REFUND`, `RETURN`, `REVERSAL`, `CREDIT`, `CHARGEBACK`). Otherwise it could be a payout or something else, so it goes to review with a suggestion.
6. **Misspellings.** If nothing matches exactly, a string-similarity check (`rapidfuzz`, 88%+ similar, only for patterns of 6+ characters) may find a near match, like `MARIOTT HOTEL` for `MARRIOTT`. This only produces a suggestion in Needs Review. It never auto-assigns.
7. **Nothing matches** goes to Needs Review with a reason ("Unknown merchant", or for money coming in, "could be a refund or income").

The brain is a word list, so it cannot know everything about a merchant. Two things keep that safe. Where it can see a conflict it asks instead of choosing, and **the user can change any row**, not only the ones it asked about.

### Why some rules are deliberately below the threshold

| Rule | Confidence | Why it is always reviewed |
|---|---|---|
| Cafes, restaurants, coffee, etc. | 0.7 | Meals are only deductible with a business purpose. |
| Uber Eats, DoorDash, Grubhub | 0.6 | Food delivery could be personal or business. |
| Amazon | 0.5 | Could be business or personal. |
| `TRANSFER TO` / `TRANSFER FROM` a person | 0.6 | Could be a contractor payment, a client payment, or moving your own money. |

Specific rules are confident: `ADOBE`, `GITHUB`, `DELTA AIR`, `STAPLES`, `INTEREST CHARGE` and similar are 0.95; phone and internet providers are 0.85; income phrases are 0.9; known transfers like `TRANSFER TO SAVINGS` and `PAYMENT THANK YOU` are 0.95.

## What the brain does not know

The brain only recognizes merchants it has rules for, and the list is small on purpose. Everything else goes to Needs Review, which is intended behaviour and not a gap. A statement shows the store, not what was bought: `BEST BUY 00231` could be a fridge for the home or a monitor for the business, and no code can tell from the statement alone. So the app asks, and the user sets the category for that row.

## Messy statement cases and what happens

| Case | What the app does |
|---|---|
| **Refund** (money in, description says refund/return/reversal/credit, merchant known) | Counted as money back: it **reduces** that category's total. It is not income. |
| Money in from a known merchant with no refund wording | Needs Review with a suggestion. It could be a payout. |
| A known word inside another business (`HILTON GARDEN PIZZA`, `AVIS BEAUTY SALON`, `AUTOPAY GYM MEMBERSHIP`) | Needs Review. Conflicts are not guessed, and rules are written as the full name (`AVIS RENT A CAR`, `AUTOPAY PAYMENT`) not a loose word. |
| Money in from an unknown source | Needs Review (could be a refund or income). |
| Income rules (`CLIENT PAYMENT`, `INVOICE PAYMENT`, `STRIPE PAYOUT`, ...) | Only apply to money coming in, so an outgoing charge with a similar name is not income. |
| Transfers and card payments | **Excluded** from totals. Shown in the table, counted separately. |
| Possible duplicate (same date, merchant and amount) | The repeat goes to Needs Review with "Possible duplicate of row N". The user can confirm "It's a real charge" so it is counted. |
| Amount signs differ between banks | `auto` looks at rows from **known business merchants**: if most of them are positive, purchases are assumed positive and signs are flipped, with a warning. It does **not** count positive against negative rows, because a month with a few purchases and several client payments would look flipped. With no known merchants to go by, signs are kept (negative = money out) and the user is told it was a guess. The user can force either convention. |
| Different amount formats | `-59.99`, `($1,234.50)`, `12.50-`, `$2,000.00`, `1.200,50`, `59.99 CR` / `59.99 DR` and separate Debit/Credit columns are all read. An amount with stray letters (`1e5`) is skipped with a warning, not guessed. |
| Ambiguous dates (`03/04/2026`) | The app picks an order, warns, and offers a day-first option. A date like `13/05/2026` settles it automatically. |
| Text above the header, Total / Closing balance rows | Header is found automatically; summary rows without a date are skipped with a warning. |
| Unreadable rows | Skipped with a warning naming the row, not silently dropped. |
| Wrong file type, empty file, file over 5 MB, no recognisable header | A clear error message, no crash. |

## Totals

Negative means money out, positive means money in, everywhere. Category totals are **net spend**: a refund reduces its category. Income is summed separately. Rows still in Needs Review are not in any category total; the summary shows how many there are and their net amount, so the user can see how much is still unsorted. Money is handled with `Decimal` end to end and sent to the frontend as strings, never floats.

## Fixing rows

The user can change the category of any row: a Needs Review row (accept the suggestion or pick one), a row the brain was confident about but got wrong, or a row it excluded. There is also **Personal (not business)** and **Other Business Expense**, so a row never has to be forced into a wrong category. A changed row shows "set by you" and an Undo button.

A change applies to that one row only, not to the merchant. This is on purpose: the rows that reach review are the ones where the merchant does not decide the category (an Amazon order can be an office chair or a birthday gift), so one answer must not be applied to the next Amazon row. Nothing is stored. The first version of this app saved a rule per merchant to a JSON file; it was removed because it made exactly that mistake, and because the task does not need any state to live between uploads.

A row the user changed is not flagged as a duplicate, since choosing a category for it already counts it as a real charge.

## Is `rapidfuzz` an AI model?

No. It computes a text similarity score between two strings (an edit-distance style calculation). It is a deterministic function with no model or training. It is only used to suggest, never to decide.

## How it is tested

109 pytest tests in `backend/tests/` (normalizer, CSV parser, categorizer, API). Expected totals for the sample statement were worked out by hand from the CSV, not copied from the program's output.

The tests were written by the AI, so they mostly checked inputs the code was built for. They were extended with inputs meant to break it: a known word inside a different business, two confident rules that disagree, money in that is not a refund, a month with more payments in than purchases, and amounts with stray letters. `sample_data/tricky_cases.csv` holds several of these. There are no frontend tests; the frontend is checked with `npm run lint`, `npm run build` and by hand.

## Known limitations

- **CSV only.** No PDF or Excel.
- **Small rule list.** It covers common freelancer merchants (72 phrases). Anything else goes to Needs Review, which is the intended behaviour. New rules are added in `backend/app/rules.py`.
- **The brain can still be wrong.** It matches words, so a known word in a description the rules did not anticipate can still be filed with full confidence. Conflicts between categories are caught and asked about, and the user can change any row, but the app cannot see what it has not been taught. For example, `TRANSFER TO SAVINGS ACCOUNT OF BOB` still matches the known phrase `TRANSFER TO SAVINGS` and is left out of the totals.
- **Sign auto-detect is still a guess.** It uses known merchants as evidence and says so, but a file with no known merchants gets no flip. The user can override it.
- **Changes are per row and not stored.** Upload the same file again and you start fresh. A merchant with 30 rows needs 30 changes. Saving choices per user would fix that but needs accounts.
- **Every change sends the whole file again,** and the table shows every row with no paging. Fine for a few hundred rows, slow near the 5 MB limit.
- **Duplicate check is exact.** Same date, merchant and amount only.
- **Single currency, no tax logic.** Amounts are treated as one currency and no deductibility rules are applied beyond asking about meals.