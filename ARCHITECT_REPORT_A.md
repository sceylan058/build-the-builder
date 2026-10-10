# Architect report: Phase A

## 1. Inventory and slots
- Kit VERSION 3.
- Workspace: 5 workflows, no duplicates. Checked via `GET /api/v2/workflow?workspaceId=`.
- Slots: practice-a = fca15556 (agent 292ae78f), practice-b = 80940a9d (agent 71c4002e), dev-clean = 86726d23 (the old probe). dev-raw, hidden-1 and hidden-2 are created on first use (max 8 workflows).
- "İş Akışı" and "Freya Bank Collections Base" are not ours and were left untouched.

## 2. What was built
- `builder/build.py`:
  - CLI: `<brief...> <tool_api> [--slot] [--no-save] [--practice-test A|B]`.
  - Inputs: file, directory or zip.
  - Isolated `work/<slot>/` behind a PreToolUse guard (unit-tested; denials are logged).
  - Stages: write → compile → check (≤3 repair rounds) → dry-run → save/publish/verify model → export → trace.
  - Time guard at 20/25 min. Retries through Freya outages until 29 min (5xx and timeouts are never sent to the model as config errors).
- `builder/check.py`: 5 rules. `dev/tests/test_check.py` has 32 tests, all passing.
- `dev/tests/practice_leak_scan.py` (clean), `dev/secret_scan.sh`, `dev/tools/sim.py` (simulation wrapper with a hard timeout that closes our stuck simulation).
- `README_BUILDER.md`, `requirements.txt`, `CHANGELOG.md`.
- SKILL.md is a config-writing guide only. `gen.py` bakes body fields named like call variables.
- Trace: see `traces/practice-b.log` (first 30 lines shown in the chat log of this phase).

## 3. Acceptance
| | Result |
|---|---|
| a. practice-a build | 266 s total (write 200 s), 0 repair rounds, check OK, dry-run valid, saved v16, model matches AGENT_LLM, exported |
| a. practice-b build | 845 s total (write 84 s, save 751 s because of Freya read timeouts), 0 repair rounds, check OK, saved v18, exported |
| b. tests | practice-a **10/10** (sim c727957d); practice-b **3/3** (sim 5e60df6f). Each ran once to completion. |
| c. reproducibility | 373 config fields: 356 identical. Differences: 15 provenance notes and 2 prompt wordings (opening task, third-party enter). |
| d. fake host | built A+B in 87 s; all 9 tool URLs on https://example.invalid/v9; no mock host left |
| e. schema drift | the unchanged config fails check.py with 9 clear errors; the adapted config passes |
| f. commit | see the git log (`phase A: final-run interface + static checks`) |

## 4. Problems found and fixed
- **Practice-case leaks** in the configs, the example and SKILL.md (PUB-12's birth date and phone digits, phrases from PUB-02/06/07, PUB-01's amount). Removed; a scan now guards against them.
- **Rule numbers** fooled the provenance lint. Fixed.
- **Renamed tool fields** silently disabled the clamps. check.py now verifies the argument names.
- **Freya outages** (UTC):
  - 19:53–20:01: 503 "API key validation unavailable".
  - 20:04–20:16: save read timeouts.
  - Simulation 7eb7c9df stuck "running" from 19:51 to 21:34; closed through the documented `PUT /simulations/{id}` with status completed.

  build.py now treats 5xx and timeouts as outages, and long runs go through `dev/tools/sim.py`.
- **The guard denied the model's own spilled tool output.** That path is now allowed (test: allowed; other paths under ~/.claude are still denied).

## 5. Open risks
- **Biggest risk:** for A+B the model mostly copies `example.config.json`, which was built from Brief B (353/363 fields identical). The practice-b results therefore say little about a hidden brief. Practice-a, where the model had to adapt the example, is the better evidence. A hidden brief with different identity questions, outcomes and fields has not been tested end to end with the model.
- **The raw-material brief format** (mail + memo + code list) is untested.
- **Practice traces were built from a dirty tree.** Final runs must start from a clean commit.
- **Freya's latency** can eat the 30-minute budget (one save took 12.5 min).
- **Stability:** no `--reps 3` stability run yet.

Appendix: `builder/skill/SKILL.md` and `builder/skill/SCHEMA.md` are in the repo.

Node list of practice-b (22):
- opening: converse (who is on the line)
- setup: clock
- third_party: callback
- identity: verify
- fetch_account: get_account
- compute_facts: item facts
- negotiate: converse
- record: create_promise + add_note
- 11 end_* nodes: outcome from the ledger
- farewell: closing line
- close: close_call
- hang_up: end call
