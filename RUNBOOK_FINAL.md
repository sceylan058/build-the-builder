# RUNBOOK: final run at 20:00 Istanbul (17:00 UTC)

Repo: https://github.com/sceylan058/build-the-builder (currently PUBLIC). Working copy: `~/Desktop/build-the-builder`. Builder code = tag `freeze-2` (fallback: `freeze-1`, `e57be25`). The clean-clone rehearsal below was run at `freeze-1`; see the freeze-2 note at the end.
Do not change builder logic during the run. Hidden-brief content never goes into code, config examples or prompts.

## What the rehearsal proved (clean clone at freeze-1, both briefs in parallel, no manual step)
| | V-CLEAN (one file) | V-RAW (directory of 4 files + API) |
|---|---|---|
| wall time | 205 s | 556 s (model stage 547 s; Freya was slow) |
| credentials | `api_key` → `claude_login (Credit balance is too low)` (fallback worked) | same |
| model cost | $1.22 | $1.09 |
| repair rounds | 0 | 0 |
| check.py / Freya dry-run | OK / valid | OK / valid |
| workflow / agent id | 86726d23… / 9bccc985… | 2674e1a4… / e25a7405… |
| published, model = AGENT_LLM | v7, yes | v10, yes |
| size | 25 nodes, 9 model tools, 18 engine actions | 25 nodes, 8 model tools, 18 engine actions |
| export | `submission/dev-clean.workflow.json` | `submission/dev-raw.workflow.json` |

**The builder API key is out of credit.** Every build starts with one failed model call and falls back to the Claude login (it is recorded in the trace). Before 20:00: top up the key, or make sure the Claude login in the terminal is valid and has usage left. A login that is also exhausted stops the build with "MODEL CREDENTIALS FAILED".

## 0. Pre-flight (19:30)
1. `cd ~/Desktop/build-the-builder && source env.sh`
2. `git status --short` must show nothing under `builder/`, `tools/`, `freya.py`. `git log -1 --format=%h` = the commit you intend to submit from. `git tag --list 'freeze*'`.
3. `python3 -m unittest dev/tests/test_check.py dev/tests/test_resolver.py dev/tests/test_offer_engine.py dev/tests/test_identity_close.py dev/tests/test_build_credentials.py` → OK.
4. Freya reachable: `python3 -c "import freya; print(freya.api('GET','/api/v2/workflow',workspaceId=freya.workspace_id(),limit=1)['total'])"`. The workspace holds 7 workflows; two new slots make 9 (assumed limit 10). If the API answers 5xx, wait: the builder retries until minute 29.
5. `.anthropic_key` present (or login valid, see above). `.freya-agents.json` present (it stays local, it is gitignored).

## 1. Put the hidden files in place
| Form of the brief | Where |
|---|---|
| one file | `briefs/hidden-1.md` (keep its extension) and its tool API `briefs/hidden-1.openapi.json` |
| several files (mail, extract, memo, code list …) | a directory `briefs/hidden-2/` holding ONLY the brief files; the tool API OUTSIDE it as `briefs/hidden-2.openapi.json`. A zip also works as a brief path. |

The API file is always the LAST argument and must be an OpenAPI file with `paths`. If the organizers ship the API file with a different name, copy it to the name above; do not edit its content.

## 2. Build (two terminals, in parallel)
Terminal 1:
```
cd ~/Desktop/build-the-builder && source env.sh
python3 builder/build.py briefs/hidden-1.md briefs/hidden-1.openapi.json --slot hidden-1 2>&1 | tee traces/hidden-1.console.log
```
Terminal 2:
```
cd ~/Desktop/build-the-builder && source env.sh
python3 builder/build.py briefs/hidden-2 briefs/hidden-2.openapi.json --slot hidden-2 2>&1 | tee traces/hidden-2.console.log
```
(Swap the file/directory forms if hidden-2 is the single file. Console output goes to `*.console.log`, never to `traces/<slot>.log`, which build.py writes itself.)
Do NOT run `tools/run_cases.py` on a hidden brief: the practice cases have different rules.
Each build is limited to 30 minutes; the guard stops new repair rounds at 20 and saves the best valid workflow at 25.

## 3. What to check in each trace (`traces/<slot>.log`)
| Line | Expected |
|---|---|
| `START utc=… commit=<hash>` | the intended commit, **no `(dirty)`** (hidden slots create new files, so tracked files are not rewritten; the rehearsal showed `(dirty)` only because dev-clean/dev-raw traces are tracked) |
| `input … sha256=` and `tool API … paths=[…] server=…` | every hidden file listed; the 7 tool paths; the server of the hidden API |
| `credentials:` | `api_key`, or `api_key -> claude_login (reason)` then `claude_login (fallback)` |
| `model call N [stage] model=…` | present for every call; `model session … cost=` lines |
| `[check round 0] check.py: OK` | OK (a failing round is followed by `repair N`; at most 3) |
| `[dry-run] Freya validation: {"valid": true…}` | valid |
| `final workflow: N nodes, M model tools, K engine actions; check OK` | check OK |
| `[save] … workflow_id=… agent_id=… version=… published=True … matches AGENT_LLM=True` | all three |
| `[export] submission/<slot>.workflow.json sha256=…` | file written |
| `END utc=… total=…s` | total below 1800 s |
Warning signs: `GUARD denied` lines (a few are fine), `MODEL CREDENTIALS FAILED`, `RESULT: no workflow could be compiled`, `check … FAILED with N error(s)` in the final line, `PRACTICE`/`run_cases` anywhere.

Also open the exported workflow once and confirm every tool URL starts with the hidden API's `servers[0].url`:
`python3 -c "import json,re;print(set(re.findall(r'https?://[^\"/]+/[^\"/]+',open('submission/hidden-1.workflow.json').read())))"`.

## 4. Files to submit
`submission/hidden-1.workflow.json`, `submission/hidden-2.workflow.json` (exports of the published workflows), and per slot `traces/<slot>.log`, `traces/<slot>.jsonl`, `traces/<slot>.console.log`.

## 5. Commit and push (only submission/ and traces/)
```
cd ~/Desktop/build-the-builder && source env.sh
git add submission/hidden-1.workflow.json submission/hidden-2.workflow.json traces/hidden-1.* traces/hidden-2.*
bash dev/secret_scan.sh                      # must print "SECRET SCAN: clean"
git commit -m "final run: hidden-1 and hidden-2 exports and traces"
git push
git log -1 --format=%H                       # the hash for the form
git diff --stat <START commit of the trace> HEAD -- builder tools freya.py   # must be empty: the code is the run's code
```
The scan covers tracked and not-yet-ignored files, including the trace and console logs and `.anthropic_key` contents. If it fails, remove the offending file from the commit; never push.

## 6. The submission form (fill in)
```json
{
  "repo_url": "https://github.com/sceylan058/build-the-builder",
  "commit": "<paste the hash from `git log -1 --format=%H`>",
  "run_command": "python3 builder/build.py {brief_path} {tool_api_path}",
  "briefs": [
    {"name": "hidden-1", "workflow": "submission/hidden-1.workflow.json", "trace": "traces/hidden-1.log"},
    {"name": "hidden-2", "workflow": "submission/hidden-2.workflow.json", "trace": "traces/hidden-2.log"}
  ]
}
```
Trace extras: `traces/<slot>.jsonl` (raw messages) and `traces/<slot>.console.log`.

## 7. If a build crashes or fails
1. Read the last lines of `traces/<slot>.log` and the console log. Freya 5xx/timeouts are retried automatically; an outage that outlasts minute 29 ends the build: simply start it again (slots update in place; nothing piles up).
2. A model/credential failure: fix the key or the login, start again.
3. A Python traceback in `builder/`: make the **minimal generic fix** (an input-handling crash on a format the parser did not expect, a missing key in a generated structure). Never add a hidden-brief value, rule, word, enum or name anywhere in `builder/`. Run the five unit tests, run `dev/secret_scan.sh`, commit the fix with a message that says what generic case it handles, push, then re-run the whole build from the start (the trace of the final run must be a full run on the final commit).
4. `check.py` errors that survive three repair rounds: the build still saves the best workflow; read the error list in the trace. Do not hand-edit the config or the workflow. If the cause is generic (a check that rejects a valid construct), fix the checker generically and re-run.
5. Never use `--reuse-config` for the submitted run unless a generic generator fix is the only change since the model wrote the config: it skips the model stage, and the trace says so.

## Note on freeze-2
`freeze-2` = freeze-1 + the scripted hardship step, the open-offer wording and the stage-based safety-net outcome (CHANGELOG.md has the gate table). The rehearsal numbers above were measured at freeze-1. To fall back: `git checkout freeze-1` (or tag the final run from it); nothing else changes.
