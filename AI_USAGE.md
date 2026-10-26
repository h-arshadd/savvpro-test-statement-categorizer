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

## Where the AI got things wrong

1. **A rule that could never match.** `rules.py` had a `CARD PAYMENT` pattern, but the normalizer strips a leading `CARD`, so the pattern could never match. Found while reviewing the code; removed.
2. **Commands for the wrong shell.** It suggested `ls -a`, which does not work in Windows PowerShell.
3. **A dead end in the review flow.** Duplicate flagging was first built with no way for the user to clear a false alarm. Saving a rule cannot clear a duplicate flag. Found while designing the frontend and fixed with the `keep_rows` option and a `duplicate_of` field.

### On AI-written tests

The tests were written by the AI, and AI-written tests tend to pass. A test only means something if it can fail. To limit that, the tests were written from the intended behaviour (not from what the code happened to output), and the expected category totals for the sample statement were worked out by hand from the CSV. I ran them locally, but I do not treat a green test run as proof, so I also tried the app by hand.

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

