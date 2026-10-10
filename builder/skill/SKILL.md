---
name: build-phone-agent
description: Build a Freya phone agent from a bank's brief, test it on the practice customers and fix what fails. Use when asked to build or improve a phone agent from a brief.
---

# Build a phone agent from a brief

You turn the brief into a **config**. `gen.py` turns the config into a workflow. You never write workflow JSON by hand. Every rule, word, tool name and outcome comes from the brief and its tool API file.

| File | What it is |
|---|---|
| `SCHEMA.md` | every config field |
| `example.config.json` | a complete config for one particular brief. Copy its shape, never its values. |
| `gen.py` | config → workflow. `--selftest` prints what the model will see. It stops with `config error: …` when a field is missing. |
| `tools/chat.py`, `tools/transcript.py` | chat one turn at a time; print a finished call's turns and tool calls |

## Time limit: 30 minutes, tests included

- At the start, run `date +%s > /tmp/build_start`. Check how long you've been running before every round: `echo $(( $(date +%s) - $(cat /tmp/build_start) ))`.
- Have the config written by minute 12 and the first test started by minute 15. **Never start a test after minute 21**, and make no changes after minute 24.
- If the practice service is down (HTTP 500, `error code: 1101`), wait at most 3 minutes in total. A saved, untested agent is better than a run that goes over the limit.

## Steps

1. **Read** every brief file you were given (a brief that extends another needs both), then the tool API file, then `SCHEMA.md` and `example.config.json`.
2. **List the brief's rules** in order. Give each one a home:
   - a calendar or item value;
   - a node or route in `flow`;
   - a prompt line (`task`, `enter`);
   - an outcome rule;
   - a closing line.
3. **Design the flow from the brief, not from the example.** Pick only the nodes the brief needs:
   - **Who is on the line:** a `converse` node with a fixed `tts` first line and an `extract` enum, routed with `eq`.
   - **Identity check:** only if the brief asks for one: a `verify` node.
   - **Time facts and booking windows:** a `clock` node, placed before the first prompt that needs them.
   - **Records to load:** a `fetch` node (the engine calls the tool, no model involved), then a `compute` node if the records hold items with rules (limits, tiers, offers).
   - **The conversation:** `converse` nodes. Put writes that must happen only after a confirmation in their own `converse` node, reached by a tool-call route.
   - **Every ending:** a route to `end:<hint>`. The outcome is computed from the ledger by `outcomes.rules`, so the model never picks it.
4. **Write `out/<slot>.config.json`** (`<slot>` is the last brief's file name without `.md`). Point `openapi` at the tool API file you were given.
   - Assign roles: one `close` tool; `record` for writes that must succeed; `note` for per-item reasons; `flag` for single actions such as a transfer or a booking; `fetch` and `verify`.
   - Put dates and amounts in code: `items.fields` expressions, tier `limit` rules, `ladder` steps.
5. **Generate and check:**
   ```bash
   G=.claude/skills/build-phone-agent/gen.py
   python3 $G out/<slot>.config.json out/<slot>.workflow.json
   python3 $G out/<slot>.config.json --selftest '<items JSON as the fetch tool returns them>' '<a now value>'
   ```
   Check the self-test by hand against at least one example from the brief: limits, holidays, offers, windows.
6. **Save it:** `python3 -c "import freya,json,sys; print(json.dumps(freya.save_workflow(sys.argv[1], json.load(open(sys.argv[2])))))" <slot> out/<slot>.workflow.json`. The same slot updates the same workflow, and saving publishes it.
7. **Test it:** `python3 tools/run_cases.py <agent_id> --brief <letter> --out results/<slot>-N.json`, in the foreground.
   - For each FAIL, run `python3 tools/transcript.py results/<slot>-N.json <case>`, find the rule involved, and fix the config.
   - Change `gen.py` only when the schema cannot express the rule.
   - If the kit has no practice cases for this brief, do one chat smoke test with `tools/chat.py`. The chat route skips the opening tts line.
8. **Finish with one line:** the `workflow_id`, the `agent_id` and the last test score.

## What the tests taught us (keep these in the prompts)

- **Code decides, the model talks.** The model does not compare dates reliably. The calendar lists OK / TOO LATE for each item, and record `clamp` rules fix arguments in the pre-hook.
- **Give offers or options as a numbered `ladder`** with an explicit STOP line. A general rule ("offer X once") makes the model add extra offers. Write any if/otherwise condition into each step's text.
- **The judge reads words literally.** Never say "recorded" (or a similar word) before a tool result confirms it, not even in the opening line.
- **Customers give answers in pieces** ("forty-four" … "zero one"). Tell the model to join the pieces and ask only for the rest. Small talk or "you tell me" after an offer is a non-answer: go to the next step and never repeat an offer. Make any "offer once" rule say: if the reply does not clearly accept, treat it as declined. A message cut off mid-sentence still counts if it holds a complete answer.
- **The step after a confirmed read-back starts with a tool call and no words.** It never asks for confirmation again.
- **Freya sometimes fails for a whole run.** Signs: calls end after one turn, tools return nothing, a `{{variable}}` is spoken aloud, or `function_call_error … snekbox` in the call. Code steps retry twice by themselves. Do not "fix" the config for an outage.

## Rules

- Never edit the agent on the platform by hand. Change the config or `gen.py`, generate, and save.
- When a tool call fails, the agent says so. It never claims a record that does not exist.
- One green run is a hint, not proof.
