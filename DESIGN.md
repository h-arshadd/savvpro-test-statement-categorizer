# Design

## Use case

**A freelancer or small business owner reading their business credit card statement at tax time.**

They download a CSV from their card provider and need every charge sorted into a category they can use on a tax return, plus a total per category. The expensive mistake here is a confident wrong answer: a personal dinner filed as a business expense, or a refund counted as income. So the app is built around one rule: **if it is not sure, it says so and asks.**

Categories: Software & Subscriptions, Travel, Meals, Office Supplies, Advertising, Phone & Internet, Interest & Bank Fees. Two more are not spending: **Income** and **Transfers & Card Payments** (left out of the totals).

This is a bookkeeping helper, not tax advice.

## The flow

```
Upload CSV -> Read rows -> Clean merchant name -> The brain -> Category / Needs Review / Excluded
                                                                  |
                                       User fixes review rows -> saved as a rule -> re-run
```

The backend is stateless. It reads the file in memory and never stores the statement. When the user fixes a row, the frontend saves a rule and uploads the same file again, so the result is always computed fresh from the file plus the saved rules.

## The brain

The brain is ordinary Python: a small list of rules plus a fixed order of checks. No AI model, no training data. Every decision comes with a plain-English reason that the API returns with the row.

### 1. Clean the merchant name (`normalizer.py`)

Bank descriptions are noisy: `SQ *BLUE BOTTLE COFFEE`, `AMAZON MKTP US*2K4X91`, `POS DEBIT STAPLES 00123`. The normalizer uppercases, strips prefixes like `POS`, `DEBIT`, `CARD`, strips processor prefixes like `SQ *` and `PAYPAL *`, removes punctuation, and drops any word that contains a digit (store numbers, reference codes). So `JOES CAFE 9921` becomes `JOES CAFE`.

### 2. Decide the row (`categorizer.py`), in this order

1. **A rule the user saved wins.** If the user already told the app what this merchant is, use that (confidence 1.0).
2. **Zero amount or empty description** goes to Needs Review. There is nothing to judge.
3. **Match against the rules.** Rules are whole-word phrases matched against the cleaned name (`AMAZON` does not match `AMAZONIA`).
   - The **longest matching phrase wins**, so `AMAZON WEB SERVICES` (Software) beats `AMAZON` (Office Supplies).
   - If the longest matches point to **different categories**, it goes to review.
4. **Confidence threshold.** Each rule has a confidence. Below **0.8** the row goes to Needs Review with the rule's category as a *suggestion*, not an answer.
5. **Misspellings.** If nothing matches exactly, a string-similarity check (`rapidfuzz`, 88%+ similar, only for patterns of 6+ characters) may find a near match, like `ADOBE CREATVE CLOUD`. This only produces a suggestion in Needs Review. It never auto-assigns.
6. **Nothing matches** goes to Needs Review with a reason ("Unknown merchant", or for money coming in, "could be a refund or income").

### Why some rules are deliberately below the threshold

| Rule | Confidence | Why it is always reviewed |
|---|---|---|
| Cafes, restaurants, coffee, etc. | 0.7 | Meals are only deductible with a business purpose. |
| Uber Eats, DoorDash, Grubhub | 0.6 | Food delivery could be personal or business. |
| Amazon | 0.5 | Could be business or personal. |
| `TRANSFER TO` / `TRANSFER FROM` a person | 0.6 | Could be a contractor payment, a client payment, or moving your own money. |

Specific rules are confident: `ADOBE`, `GITHUB`, `DELTA AIR`, `STAPLES`, `INTEREST CHARGE` and similar are 0.95; phone and internet providers are 0.85; income phrases are 0.9; known transfers like `TRANSFER TO SAVINGS` and `PAYMENT THANK YOU` are 0.95.

## Messy statement cases and what happens

| Case | What the app does |
|---|---|
| **Refund** (money in from a merchant it knows) | Counted as money back: it **reduces** that category's total. It is not income. |
| Money in from an unknown source | Needs Review (could be a refund or income). |
| Income rules (`CLIENT PAYMENT`, `STRIPE PAYOUT`, ...) | Only apply to money coming in, so an outgoing charge with a similar name is not income. |
| Transfers and card payments | **Excluded** from totals. Shown in the table, counted separately. |
| Possible duplicate (same date, merchant and amount) | The repeat goes to Needs Review with "Possible duplicate of row N". The user can confirm "It's a real charge" so it is counted. |
| Amount signs differ between banks | `auto` mode guesses from the data (if most amounts are positive, purchases are assumed to be positive and signs are flipped) and shows a warning. The user can force either convention. |
| Different amount formats | `-59.99`, `($1,234.50)`, `12.50-`, `$2,000.00`, `1.200,50` and separate Debit/Credit columns are all read. |
| Ambiguous dates (`03/04/2026`) | The app picks an order, warns, and offers a day-first option. A date like `13/05/2026` settles it automatically. |
| Text above the header, Total / Closing balance rows | Header is found automatically; summary rows without a date are skipped with a warning. |
| Unreadable rows | Skipped with a warning naming the row, not silently dropped. |
| Wrong file type, empty file, file over 5 MB, no recognisable header | A clear error message, no crash. |

## Totals

Negative means money out, positive means money in, everywhere. Category totals are **net spend**: a refund reduces its category. Income is summed separately. Rows still in Needs Review are not in any category total; the summary shows how many there are and their net amount, so the user can see how much is still unsorted. Money is handled with `Decimal` end to end and sent to the frontend as strings, never floats.

## Learning from the user

When the user fixes a row, the app saves "this cleaned merchant name always means this category" in a small JSON file (`RulesStore`, written atomically so a crash cannot leave a half-written file). On the next upload, step 1 above applies it. A saved rule can also mark a merchant as "Transfers & Card Payments".

## Is `rapidfuzz` an AI model?

No. It computes a text similarity score between two strings (an edit-distance style calculation). It is a deterministic function with no model or training. It is only used to suggest, never to decide.

## How it is tested

Tests are in `backend/tests/` (normalizer, CSV parser, categorizer, rules store, API). They were written from the *intended* behaviour, and the expected totals for the sample statement were worked out by hand from the CSV rather than copied from the program's output.

AI-written tests can still be too agreeable, so passing tests are not treated as proof. Besides the test suite, the app was tried by hand with the sample statement and other CSVs (see AI_USAGE.md).

## Known limitations

- **CSV only.** No PDF or Excel.
- **Small rule list.** It covers common freelancer merchants. Anything else goes to Needs Review, which is the intended behaviour, and the user's fixes are remembered. New rules are added in `backend/app/rules.py`.
- **Sign auto-detect is a guess.** On an account where deposits outnumber purchases, `auto` can guess wrong. The app warns when it flips signs, and the user can override it.
- **One shared rules file.** There are no user accounts, so all saved rules are shared. Fine for a single user, not for a multi-user service.
- **Duplicate check is exact.** Same date, merchant and amount only.
- **Single currency, no tax logic.** Amounts are treated as one currency and no deductibility rules are applied beyond asking about meals.

## What I would do next

User accounts and per-user rules, PDF statements, a bigger and editable rules list, and multi-statement (whole year) totals.