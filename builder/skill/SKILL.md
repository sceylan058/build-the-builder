---
name: build-phone-agent
description: Write the config for a Freya phone agent from a bank's brief and tool API file. The builder compiles, checks, saves and exports; you only write and repair the config.
---

# Write the config for a phone agent

Your working folder holds:

| Path | What it is |
|---|---|
| `brief_bundle.md` | the brief: every input file in order, each under a header with its name. It may be a clean specification, or raw bank material (a mail, a policy extract, a memo that changes it, a code list). |
| `inputs/` | the original files, in case the bundle lists a file you must open yourself |
| `openapi.json` | **the only tool API.** Tool names, body fields, types, allowed values and the server URL come from here. |
| `skill/SCHEMA.md` | every config field |
| `skill/example.config.json` | a complete config for a different brief. Copy its structure and its prompt technique, **never its values**. |
| `skill/gen.py`, `skill/check.py` | the compiler and the checker the builder runs after you |
| `docs/` | Freya's workflow and tool documentation, if you need detail |

You write **`config.json`** in this folder. You do not save anything on Freya and you do not run practice tests. Do not read anything outside this folder.

## Steps

1. Read `brief_bundle.md` completely, then `openapi.json`, `skill/SCHEMA.md` and `skill/example.config.json`.
   - **Raw material:** later documents (a memo, a correction) override earlier ones. Code lists give the allowed values. When two sources disagree, follow the latest dated one.
2. **List every rule of the brief, numbered.** For each one, note where it lives:
   - a calendar or item value;
   - a node or route;
   - a prompt line;
   - an outcome rule;
   - a closing line.

   Nothing may be left without a home.
3. **Write `config.json`**, with `"openapi": "openapi.json"`.
   - **Tool fields** are exactly the fields in `openapi.json`. Every enum value you use (outcomes, reasons, queues, identity fields, item types) must be listed there. A body field named like a call variable (for example the customer id) is filled from that variable automatically. List the brief's call variables in `call_variables`.
   - **Calendar:** working days, every holiday, the date order for numbers-only dates, the call variable that holds "now".
   - **Items** (what the account lookup returns): fields as Python expressions, tiers, limit rule, offer ladder, spoken summary. Put every date and amount rule in code; the model only reads the results.
   - **Flow:** only the steps the brief needs:
     - who is on the line (a fixed first line as `tts`, an `extract` enum);
     - the identity check (`verify`, if the brief has one);
     - a `clock` before any prompt that needs today's date or a booking window;
     - `fetch` + `compute`;
     - the conversation;
     - a separate recording step after the confirmed read-back;
     - every ending as `end:<hint>`.
   - **Outcomes:** `outcomes.rules` in the brief's order of precedence (first match wins), `by_hint` for every ending, and `args` naming the close tool's fields.
   - **Closing lines** for every ending, `forbidden_before_verification` (the words the brief forbids before identity is checked), and a safe `closing_line` in `test_variables`.
4. **Provenance.** Every holiday, time, count, ordinal and limit in the config must appear in the brief. Every sentence you put in double quotes in a prompt must be the brief's own words. If a value is derived (for example Monday to Friday becomes `[0,1,2,3,4]`), or a quoted phrase is your own, add it to `provenance.derived` with a one-line reason: `{"derived": {"<value or phrase>": "<why or formula>"}}`.
5. **Check it yourself before you stop:**
   ```bash
   python3 skill/gen.py config.json workflow.json
   python3 skill/check.py workflow.json openapi.json --config config.json --bundle brief_bundle.md --quick
   python3 skill/gen.py config.json --selftest '<items as the account tool returns them>' '<a now value from the brief>'
   ```
   Check the self-test by hand against an example in the brief: limits, holidays, offers, windows. Fix every check error. Then stop and say "config ready".

When the builder sends you an error list, fix `config.json` for every error and run the checks again.

## Prompt technique that passed the practice runs

- **Code decides, the model talks.**
  - The calendar lists OK / TOO LATE for each item, so the model never compares dates.
  - `clamp` rules on the record tool fix arguments in the pre-hook.
  - Give offers as a numbered `ladder` with an explicit STOP line, and write any if/otherwise condition into each step's text.
- **Never say "recorded" before a result says so,** not even in the opening line ("this call is recorded" failed an honesty check; "we are recording this call" passed).
- **State every item, one sentence each, in a fixed `tts` line** built by `compute` before asking anything.
- **Customers give answers in pieces.**
  - Join the pieces of consecutive messages and ask only for the missing part.
  - Small talk, a question back, or asking you to choose is a non-answer: go to the next step and never repeat an offer.
  - Any "offer once" rule must say: if the reply does not clearly accept, treat it as declined.
  - A message cut off mid-sentence still counts if it holds a complete answer.
- **The recording step starts with a tool call and no words,** and never asks for confirmation again. Writes are retried once by the hooks; after a second failure the customer is told plainly.
- **Endings are routes, never the model's choice of outcome:** the builder computes the outcome from what the tools recorded.
