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
