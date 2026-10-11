# Changelog

Each entry: what changed, why, and the evidence (a command and its result).

## Phase A — final-run interface, git, traces, static checks

### A0 Inventory
- What: kit VERSION is 3. Workspace has 5 workflows (`GET /api/v2/workflow?workspaceId=…`, documented at docs.freyavoice.ai/api-reference/workflows/list-workflows). Slots remapped in `.freya-agents.json`: brief-a→practice-a, brief-b→practice-b, probe→dev-clean. dev-raw, hidden-1, hidden-2 are created on first use (max 8 of the assumed 10). Two workflows we did not create ("İş Akışı", "Freya Bank Collections Base") are left untouched.
- Why: the 10-workflow limit; update in place.
- Evidence: `cat VERSION` → 3; list route → total 5.

### A0 Guardrail clean-up
- What: reverted our earlier one-line edit to `examples/agent_builder.py` (kit file). Moved the synthetic flight/insurance briefs and configs from `briefs/` and `out/` to `dev/legacy/`. Moved our helpers `chat.py`, `transcript.py`, `golden_compare.py` from `tools/` to `dev/tools/`. Moved the skill from `.claude/skills/build-phone-agent/` to `builder/skill/`, and the old traces to `dev/legacy/traces/`.
- Why: kit files must stay unmodified; the builder must never read other-domain material.
- Evidence: `grep -c '"end": time' examples/agent_builder.py` → 0; `ls briefs` → brief-a.md, brief-b.md.

### A1 Git
- What: `git init`; `.gitignore` (env.sh, *.env, .freya-agents.json, .personas*.json, results/, backup/, work/, caches); `dev/secret_scan.sh` (fails on fak_…, sk-ant-…, or the values of FREYA_BANK_TEAM_KEY / FREYA_API_KEY / ANTHROPIC_API_KEY in tracked or unignored files).
- Evidence: scan clean on the tree; a planted copy of the team key makes it exit 1.

### A2 builder/build.py
- What: the single final entrypoint `python3 builder/build.py <brief...> <tool_api> [--slot] [--no-save] [--practice-test A|B]`.
  - Input handling: file, directory or zip inputs; `work/<slot>/` holds the inputs, `openapi.json`, `brief_bundle.md`, a copy of the skill (with check.py) and `docs/`.
  - Isolation: the model runs with cwd=work/<slot> behind a PreToolUse guard that denies anything outside it.
  - Stages: write → compile → check (+≤3 repair rounds) → dry-run → save/publish/verify model → export to submission/ → trace.
  - Time guard: no new round after 20 min, save the best by 25 min.
  - Trace: traces/<slot>.log + .jsonl, with secrets redacted.
- Also: SKILL.md is now a config-writing guide only (no practice tests, no saving).
  - gen.py bakes any body field named like a call variable (no hard-coded `customer_id`).
  - No hard-coded tool API path or mock host remains in builder/.
- Why: the organisers run one command per hidden brief, with its own tool API file, and re-run it from the commit.
- Evidence: guard unit test — 14/14 cases (inside allowed; `..`, `~`, absolute paths, other tools denied). `grep -rn "tools/openapi.json\|freya-bank-mock" builder/` returns only generic check.py code.

### A3 builder/check.py
- What: 5 rules.
  1. OpenAPI conformance, including the config's enum usage and role argument names.
  2. Graph lint.
  3. Every snippet run the way Freya runs it, inside a function: 336 `now` values (3 weeks: one with a holiday, a month end, a year end; 4 times; 4 formats) × 1, 2 and 3 items synthesised from the API's response schema.
  4. Provenance.
  5. Spoken text before verification.

  Unit tests: `dev/tests/test_check.py`, 32 tests, with a failing fixture for every rule.
- Problems found by the new checks:
  - The provenance lint and a new `dev/tests/practice_leak_scan.py` found practice-case specifics in our configs and SKILL.md: PUB-12's birth date and phone digits, phrases from the PUB-02/06/07 scripts, and PUB-01's amount. All removed.
  - Rule numbers ("13.") made the provenance lint accept a changed deadline. Rule numbering, rule references, and the digits inside dates and times no longer count as brief values.
  - Drift testing showed that renamed tool fields silently disabled the record clamps. check.py now verifies every argument name the config uses.
- Evidence: `python3 -m unittest dev/tests/test_check.py` → 32 OK. Baseline A/B configs → check OK with the full grid. Grid ran 1008 compute executions in 0.4 s.

### A4 Acceptance and fixes
- What: see ARCHITECT_REPORT_A.md.
  - practice-a 10/10, practice-b 3/3.
  - Reproducibility: 356/373 fields identical.
  - Fake host and schema drift both pass.
  - Fixes: outage-aware retries; validator 5xx not sent to the model; spilled tool output allowed by the guard; `dev/tools/sim.py` with a hard timeout.

## Phase C

### C1 Dates anchored on `now`
- Root cause: the record step had no today in its prompt, and the date clamp had no lower bound. The model used the real clock ("today" = Sat 10 Oct), and the clamp moved that to Mon 12 Oct, a past date (PUB-01 in the runner check, VC-01).
- Fix (gen.py):
  - `resolve_date()` resolves a customer's phrase (today, tomorrow, the day after tomorrow, this/next <weekday> by the brief's week start, "the 30th", "30 October", ordinals in words, vague → "vague") against `now`, never the clock.
  - `words_to_number()` normalises amounts in words.
  - The record pre-hook resolves non-ISO dates and worded amounts in code and never sends a date before today.
  - Every converse/verify step after a clock gets `{{today_facts}}` automatically.
- Evidence: `dev/tests/test_resolver.py` passes (21 days + month and year ends × relative phrases; day numbers and words; 10 amount phrases). check.py tests 32 OK.
- Not done: dates are still read from the conversation by the dialogue model and only validated and clamped in the hook. A per-turn extraction plus code agreement store was not built.

### C5 Calls that do not end
- Finding: the "open" third-party calls had ended in 4–10 s (`assistant-ended-call`, close_call before end_call). Freya's judging stage lagged, and our dev timeout closed the simulation before the verdicts. No generator defect.
- Fix: dev/run_dev.py hard timeout raised to 40 min per 10 cases (minimum 20 min).

### C2 + C3 Speech robustness and hardship as a code state
- Root cause: our own prompt rule ("small talk or a question back is a non-answer: move to the next offer") made the model escalate the offer ladder while the customer was only chatting. This recorded the floor instead of the full amount (PUB-04 0/3 in pieces and talkative). The model also counted attempts itself and lost the hardship state.
- Fix (gen.py, generic): a converse node with `offer_state` gets:
  - per-turn extraction: `turn_intent` enum, `turn_item` position, the customer's own date and amount in their words (last value wins, pieces joined, never an unrelated event's date);
  - an automatic per-turn code node (always transition → `<node>_turn` → back), verified with a live probe. It counts refusals only on `refuse`, makes small talk and questions explicit no-attempt turns, sets a hardship flag that removes every offer for that item, and resolves the date and amount against `now`, the limits and the floor.
  - Its `CODE STATE` is injected into the prompt. The non-answer rule was removed from the example config and SKILL.md.
- Evidence: `dev/tests/test_offer_engine.py` (small talk uses no attempt; refusal counting; hardship blocks offers; dates and amounts resolved, too-late, non-business day, below-floor, vague). check.py OK on A/B.

### C4 Identity generality
- Root cause: identity normalisation knew only `date` and `digits`. A partly given answer (2 of 4 digits) was sent and could burn an attempt. A greeting could assume a call variable the brief does not declare.
- Fix:
  - New kinds `year` and `code`, plus spoken digits ("double", "oh", "forty four"), spoken years, character-by-character codes, and ordinal day words in dates.
  - An optional `length`: an answer of the wrong length is blanked (not counted), and the model is told to ask for the rest.
  - check.py R4: every call variable must be named in the brief.
- Evidence: `dev/tests/test_identity_close.py` normaliser tests. Offline: the config compiled against `openapi.drift.json` with postcode (code) and birth_year (year, length 4) passes check.py; "S W one A one A A" → SW1A1AA, "nineteen eighty three" → 1983, "nineteen" → blanked.

### C6 Close-rule schema
- Root cause: `from_note` could only take the first non-paid note, so V-CLEAN's "last" rule could not be expressed (VC-14).
- Fix: `from_note.order: first|last`, a `from_note.priority` list, and conditions `notes_with`, `notes_none`, `count {of, op, n}`, alongside `notes_any`, `notes_all`, `records`, `recorded_by`, `flag`, `hint`, `gave_up`.
- Evidence: close-rule tests on 1–3 items, including Brief B's rule (first → dispute) and V-CLEAN's (last → refused). 46 unit tests OK.

### C2 follow-up (found in the first live run of the rebuilt practice-a)
- Root cause 1: once a step has been re-entered through the per-turn loop, Freya runs no routing after a tool result (no `route_evaluated` event; "model returned no speakable content"). After `transfer_to_agent` the call was never closed (PUB-09 in pieces and talkative).
- Fix: in an `offer_state` step, every route on a flag tool's variable gets a tool-call twin, and that tool's success text says "Now call transition_to_<end>".
- Root cause 2: the resolver checked weekday names before day numbers, so "Monday the 26th" became next Monday (PUB-07 in pieces).
- Fix: an explicit day number or ordinal wins over a weekday name.
- Evidence: new resolver tests; 46+ unit tests OK. Live verification follows in C8.
