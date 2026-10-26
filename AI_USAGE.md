# AI Usage

## Tools

- **Claude** (Anthropic), through the claude.ai web chat. This was the only AI tool used.

## The big rule

No AI model is used when the app runs. The categorizer is plain Python rules (see [DESIGN.md](DESIGN.md)). There are no API keys in the project. AI was only used to help me write the code and docs.

## How it helped

- Talked through the use case and what can go wrong on real statements (refunds, transfers, duplicates, sign conventions, messy descriptions).
- Helped design the decision order of the categorizer and the confidence threshold.
- Wrote first drafts of the backend (parser, normalizer, categorizer, API), the tests, and the React frontend.
- Wrote first drafts of the README and DESIGN.md.

## How I worked with it

- Claude never ran anything. I ran every command on my own machine (Windows, PowerShell) and pasted the output back.
- One piece at a time, as complete files, so I could read each one before moving on.
- When something looked wrong, the AI was asked to read the existing code before suggesting changes.

### The order things happened in

1. **Prototype first.** I had the AI build a working prototype quickly (parser, normalizer, categorizer, API, React page, tests). It ran, the tests were green, and the sample statement looked right.
2. **Then I read the code to understand it.** I did not want to submit something I could not explain. Reading it file by file is where most of the problems below showed up. None of them were caught by the tests, because the tests were written by the same AI that wrote the code.
3. **Then I fixed what I found**, one piece at a time, and went back and asked the AI to review its own design critically instead of just adding features.

## Where the AI got things wrong

Fixed:

1. **A rule that could never match.** `rules.py` had a `CARD PAYMENT` pattern, but the normalizer strips a leading `CARD`, so the pattern could never match. Found while reviewing the code; removed.
2. **Commands for the wrong shell.** It suggested `ls -a`, which does not work in Windows PowerShell.
3. **A dead end in the review flow.** Duplicate flagging was first built with no way for the user to clear a false alarm. Saving a rule cannot clear a duplicate flag. Found while designing the frontend and fixed with the `keep_rows` option and a `duplicate_of` field.
4. **Saved rules could not be seen or undone.** The first version let the user save a merchant rule but never view or remove it, so one click on Amazon could make every future Amazon row automatic, with no way back. The built-in rules deliberately always ask about Amazon, and the saved rule quietly overrode that. Found on a critical review of the design; fixed with a Saved rules list in the UI and `GET /api/rules` and `DELETE /api/rules/{merchant}`, with tests.

Found but **not fixed yet**:

5. **The brain was confidently wrong, and the AI's design did not allow for that.** The whole point of the project is "if it is not sure, ask." But the brain is a list of word rules, and it cannot know everything about a merchant. The AI gave every rule a fixed confidence number (0.95 for ADOBE, HILTON, AUTOPAY and so on) as if a word match meant the row was understood. That number says how good the rule is, not how sure we are about this particular row. So a row that merely *contains* a known word gets full confidence. After reading the code I tried inputs built to trip it up (run against the current code):

| Description | Amount | What the app said | Why it is wrong |
|---|---|---|---|
| `HILTON GARDEN PIZZA` | -30.00 | **Travel**, 0.95, auto-categorized | Both `HILTON` and `PIZZA` match. "Longest match wins" compares characters, so HILTON (6) beats PIZZA (5). A different-category conflict is only sent to review when the lengths are equal. |
| `AVIS BEAUTY SALON` | -60.00 | **Travel**, 0.95, auto-categorized | `AVIS` is a car rental brand but also a common name. The rest of the description was ignored. |
| `AUTOPAY GYM MEMBERSHIP` | -30.00 | **Excluded**, 0.95, left out of the totals | `AUTOPAY` is how a bill was paid, not who was paid. A real expense silently disappeared from the totals. This is the worst one. |
| `TRANSFER TO SAVINGS ACCOUNT OF BOB` | -500.00 | **Excluded**, 0.95 | The known phrase `TRANSFER TO SAVINGS` matched as a prefix, even though the money went to a person. |
| `INVOICE FROM LANDLORD` | +2500.00 | **Income**, 0.9 | Any money in containing the word `INVOICE` counts as income. |

The common cause is the same each time: the brain trusts a rule match even when part of the description is unexplained or points elsewhere. A wrong guess is worse than asking, and these are exactly the wrong guesses the app is supposed to avoid. Ideas for the fix, not done yet: when more than one category matches, always ask instead of letting length decide; lower confidence when extra words in the description are not explained by the rule; and stop treating payment-method words like `AUTOPAY` as merchants. These limits are also listed in [DESIGN.md](DESIGN.md) under Known limitations.

### On AI-written tests

The tests were written by the AI, and AI-written tests tend to pass. A test only means something if it can fail. When I read them after the prototype, I saw the pattern: **the AI tested what will work if you pass this input, not what can break.** Almost every case is an input the code was built to handle: a clean known merchant (`ADOBE CREATIVE CLOUD`, `STAPLES 00123`), an obviously unknown one (`ZXQV HOLDINGS`), and a tidy refund. For example, the autopay test uses `AUTOPAY PAYMENT`, which is the exact string the rule was written for. Nothing tests `AUTOPAY GYM MEMBERSHIP`. There is a test that `AMAZON WEB SERVICES` beats `AMAZON`, but none where two different categories match and the longer word is the wrong one. A test written by the author of the code ends up checking the author's assumptions. All 79 tests pass, and the app was still confidently wrong on the table above.

What it should have asked is "what real input would make this wrong?", for example a known word inside a different business, a payment method that looks like a merchant, or a phrase that matches only half. I only found those by reading the code and then trying inputs on purpose to break it.

To limit this I wrote the expected category totals for the sample statement by hand from the CSV, not from the program's output. But I do not treat a green test run as proof, so I also tried the app by hand.

> **TODO before submitting: manual testing.** List the CSV files you tried and what you found, for example:
>
> - `freelancer_card.csv`: 17 rows, 8 categorized, 2 excluded, 7 needs review, matched what I expected.
> - (your own test file): what you expected, what happened, anything you changed because of it.

## Token usage

The claude.ai web chat does not show token counts itself. I used a browser extension (SelectorsHub's token counter) that shows an estimated token count for each chat. These are estimates, not exact figures from Anthropic: the extension excludes Claude's system prompt and project files, and a chat's size is not the same as the total tokens processed, because Claude re-reads the whole chat on every message.

Screenshots are in `docs/usage/`.

![Token estimate for the main build chat](docs/usage/chat-token-estimate-1.png)

| Chat | Estimated tokens (you / Claude / files) | Notes |
|---|---|---|
| This chat (docs, frontend review, final steps) | ~51.4K as of the screenshot (7.8K / 42.3K / 1.3K) | Still growing, re-check at the end |
| TODO: earlier chat(s) where the backend was built | TODO | Add one row per chat |
| **Total estimate** | TODO: add up the rows | Estimate only |

> **TODO before submitting:** add a row and a screenshot for each earlier chat you used, fill in the total, then delete this note.