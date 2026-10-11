---
name: write-freya-workflow
description: Write a Freya workflow JSON directly from a bank's brief pack (workflow mode of build.py). The builder validates, saves and exports; you write and repair workflow.json (and openapi.json when none is given).
---

# Write the Freya workflow directly

Your folder holds `brief_bundle.md` (every input file, each under a header), `inputs/` (the originals: open PDFs or other binaries listed in the bundle with the Read tool), `docs/` (Freya's workflow and tool documentation: read `docs/workflow-format.md` and `docs/tools-and-code.md` completely), `tool_base_url.txt`, and `skill/check.py`. You write **`workflow.json`**. Do not read anything outside this folder; do not save anything on Freya.

## 1. The tool API (`openapi.json`)
If `openapi.json` exists, it is the only tool API: use its paths, methods, field names and enums exactly.
If it does not exist, write it from the bank's integration/service documents in the bundle: one path per service, with exactly the documented path, method, request field names and types, and the documented response shape (`responses.200.content.application/json.schema`). `servers[0].url` = the content of `tool_base_url.txt`. Later documents and decision mails override earlier ones; note conflicts in `x-notes`.

## 2. Read the brief completely, then list its rules
Number every rule (sentences the bank wants said verbatim, counters, limits, branches, handovers, forbidden content, data that must never be spoken). Each rule must map to a node, transition, code step, hook or fixed line. Where documents disagree, the latest dated decision wins.

## 3. Write `workflow.json` (top-level `{initial_node, system_prompt, nodes, global_nodes, test_variables}`; no `agent_config`)
- **Call variables** the brief gives (for example a customer number and `now`) go into `test_variables` with realistic sample values, and are used as `{{name}}`. A tool body field that carries a call variable has `"default": "{{name}}"` (baked, never model-filled).
- **Exact sentences** the bank prescribes are fixed `on_enter: {"type": "tts", "text": ...}` lines or terminal `spoken_message`s, word for word, in the call's language. The model writes free text only where the brief leaves wording open.
- **Logic in code, not prompts:** counters (silence, retries, calming replies), branching on service results, date arithmetic on `now`, masking of numbers, choosing among items. Use `code` nodes (passthrough, `vars`, no `{{`/`}}` inside code, never raise, write string flags) and route on their flags with deterministic `equals` conditions. Remember that Freya runs a snippet inside a function: helpers are locals.
- **Service calls:** a call that must always happen at a point is a `pre_actions` call in a passthrough `api_request` node (node-level `response_mapping` with `data.` paths, then an `always` fallback). A call the model decides is a tool on a conversation node, with an instruction-style description and a `post_process_code` hook that adds a plain `what_to_do_next` sentence to `result["data"]` (it stops silent turns and ignored failures). Treat non-200 / error results explicitly (a route or a what_to_do_next), honestly: never claim success without a success result.
- **Extraction** for what the caller says, as enums routed with `equals`; every field has `min_confidence`; dates as type `date` only when relative words must resolve against today, otherwise strings resolved in code against `now`.
- **Endings and handovers:** every way the call can end is its own `end_call` node whose `terminal.function.name` names the destination or outcome (for example `transfer_agent`, `main_menu`, `back_to_ivr`, `end_no_input`), preceded by the bank's exact sentence (in `spoken_message` with `message_mode: "custom"`, or a tts line before). If the documents define a handover service or exit code, call/return it as documented.
- **Global behaviours** (silence, insults, out-of-scope questions, "repeat that") use `global_nodes` or code counters, not copies in every node; exclude terminal nodes.
- Every passthrough node ends with an `always` transition; every `max_node_turns` has a `max_turn_transition`; every path reaches an `end_call`; no `null` values.

## 4. Check before you stop
```
python3 skill/check.py workflow.json openapi.json --quick
```
Fix every error. Then reply "workflow ready". When the builder sends an error list, fix `workflow.json` (or `openapi.json` if the API description was wrong) and check again.

## Lessons from earlier builds (keep them)
- The model does not count or compare dates reliably: code does, and the prompt receives the result.
- After a tool result the model sometimes says nothing: a `what_to_do_next` line fixes it.
- A step re-entered through a code loop gets no routing after a tool result: end such flows through a tool-call transition the hook names.
- Never let a fixed line or prompt contain a word the brief forbids at that point; never say "recorded/done/sent" before a success result.
