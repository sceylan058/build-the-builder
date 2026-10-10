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
