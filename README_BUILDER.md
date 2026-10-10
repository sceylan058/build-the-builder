# Builder

One command builds, saves, publishes and exports a phone agent from a brief and its tool API file:

```bash
source env.sh          # FREYA_API_KEY, FREYA_API_URL (optional), FREYA_BANK_TEAM_KEY
pip install -r requirements.txt
python3 builder/build.py <brief_path> [<brief_path> ...] <tool_api_path> [--slot NAME] [--no-save]
# example: python3 builder/build.py briefs/hidden-1.md briefs/hidden-1.openapi.json
```

- A brief path can be a file, a directory (every file, sorted by name) or a `.zip`. The **last** positional argument is the tool API file (OpenAPI with `paths`).
- The slot (the name of the Freya workflow, updated in place) is `--slot`, or else the file stem of the last brief.
- Output: the Freya workflow is saved and published, `submission/<slot>.workflow.json` is the export, and `traces/<slot>.log` + `traces/<slot>.jsonl` are the trace.

## Environment

| Variable | Needed for |
|---|---|
| `FREYA_API_KEY` | saving, validating and exporting on Freya |
| `FREYA_API_URL` | optional, default `https://staging-app.freyavoice.ai` |
| a Claude login or `ANTHROPIC_API_KEY` | the config-writing model (Claude Agent SDK) |
| `BUILDER_MODEL` | optional, default `claude-opus-5-5` |

## Stages

1. The model writes `config.json` in an isolated folder `work/<slot>/`. That folder holds only the inputs, `openapi.json`, `brief_bundle.md`, the skill and `docs/`; a PreToolUse guard denies anything outside it.
2. `builder/skill/gen.py` compiles the config.
3. `builder/check.py` runs its checks: OpenAPI conformance, graph lint, a code run over a time/payload grid, provenance and spoken-text lint. Errors go back to the model, up to 3 repair rounds.
4. Freya dry-run validation.
5. Save, publish, and verify the published version and the agent model.
6. Export to `submission/`.
7. Trace.

The builder never runs practice tests unless `--practice-test A|B` is given (for development only). Time guard: no new repair round after 20 minutes; at 25 minutes the best valid workflow is saved.
