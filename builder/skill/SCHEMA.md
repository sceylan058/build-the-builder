# Config schema (gen.py)

`gen.py` stops with `config error: ...` when a required field is missing or wrong. **R** marks a required field; anything else is optional, with the default shown. `example.config.json` is a complete example.

## Top level

| Field | Type | | Meaning |
|---|---|---|---|
| `openapi` | string | R | path to the tool API file. Every tool name must be a path in it. |
| `system_prompt` | string | R | rules that hold in every step |
| `calendar` | object | R | see Calendar |
| `tools` | object | R | tool name → tool spec. See Tools. |
| `flow` | object | R | `start` (a node name) and `nodes` (name → node). See Flow. |
| `outcomes` | object | R | see Outcomes |
| `closing` | object | R | see Closing |
| `items` | object | R if a `compute` node exists | see Items |
| `clock` | object | | `windows: [...]`, see Clock |
| `test_variables` | object | | default call variables; also set a safe `closing_line` |

## Calendar

| Field | Type | | Meaning / example |
|---|---|---|---|
| `workdays` | int[] | R | Monday = 0: `[0,1,2,3,4]` |
| `holidays` | string[] | R | `["2026-12-25"]`, `[]` if none |
| `now_var` | string | `now` | call variable that holds the current date and time |
| `numeric_date_order` | `dmy` \| `mdy` | `dmy` | how to read a date said only in numbers |
| `week_start` | int | `0` | first day of a week, for "this/next <weekday>" |
| `weekday_names`, `month_names` | string[] | English | names used in spoken dates |
| `holiday_word`, `weekend_word` | string | `bank holiday`, `weekend` | |
| `horizon_days` | int | `21` | how many days the calendar runs past the latest item limit |

## Tools (`tools.<name>`)

| Field | | Meaning |
|---|---|---|
| `role` | R | `verify`, `fetch`, `record`, `note`, `flag`, `plain`, `close` (exactly one `close` tool) |
| `description` | R except fetch and close | the trigger sentence: "CALL it when …" |
| `fields` | | `{arg: {description, enum}}` for the arguments the model fills in. Fields come from the API file; `customer_id` is always filled in automatically. |
| `record` | R for role record | `item_arg`, `noun` (for example the word for one entry), `give_up` (what to say and do after a second failure when a note tool exists), `give_up_alone` (the same when it does not), `clamp: [{arg, type: number\|date, max_field, business_day}]`, `confirm` (for example `"{amount} on {date}"`), `confirm_note` |
| `note` | R for role note | `item_arg`, `reason_arg` |
| `flag` | R for role flag | `var` (variable set on success), `value_arg` (copy this argument) or `value` (a constant), `ledger_key` (store in the ledger for outcome rules), `ok_text`, `fail_text` |

Role behaviour:
- **record:** writes never retry by themselves. After the first failure the agent calls the tool once more; after the second it stops and gives up. The agent says "recorded" only after `ok: true`. Recorded items go into `ledger.records`.
- **note:** adds `[item, reason]` to `ledger.notes`.
- **verify:** used by a `verify` node.
- **fetch:** used by a `fetch` node.
- **plain:** strips headers only.

## Flow (`flow.nodes.<name>`)

A target is a node name or `end:<hint>`. Each hint creates an `end_<hint>` node, which computes the outcome, says the closing line, calls the close tool and hangs up.

| `type` | Required | Optional |
|---|---|---|
| `converse` | `task` | `enter` (`{"tts": text}` or `{"llm": prompt}`), `tools`, `tool_overrides` (`{tool: {description, fields}}`), `extract` (Freya extraction_schema items), `routes`, `turns` (default 20), `overflow` (target when the turn cap is reached), `first_entry_only` (default true) |
| `verify` | `task`, `verify: {tool, questions: [{field, ask, kind: date\|digits\|text}], args: {field, answer}, response: {verified, ok?, all_verified?, wrong_left?, hint?, swap_hint?}, on_pass, on_fail}` | the same as converse |
| `clock` | `next` | `routes`. It writes `{{today_facts}}` and one variable per `clock.windows[]` entry. |
| `fetch` | `tool`, `map: [{path: "data.x", var}]`, `ok_field`, `next`, `fail` | `retries` (default 2), `description` |
| `compute` | `next`, `fail` | It writes `items.facts_var`, `{{calendar_facts}}` and `items.summary_var`. |

A route is `{"to", "when", "description"}`. `when` is one of:
- `{"eq": [var, value]}`
- `{"set": var}`
- `{"unset": var}`
- `{"lt": [var, n]}`
- `{"any": [...]}`
- `{"all": [...]}`
- `"always"`

A tool-call route is `{"to", "tool_call": true, "description"}`; the model calls it as `transition_to_<target node>`. Mark the route that ends recording with `"done": true`.

## Items (the list a fetch returns)

| Field | | Meaning |
|---|---|---|
| `source_var` | R | variable that holds the list (from a `fetch` map) |
| `id_field` | R | id field of one item |
| `noun`, `noun_plural` | R | the word for one item and for several |
| `label` | R | `{field, templates: {value: "text with {item_field}"}}`: how an item is spoken |
| `fields` | R | ordered `name → Python expression`. Available: `it` (the item), `f` (fields computed so far), `T` (the item's tier), `today`, `num`, `first_num`, `money`, `by_value(v, map, default)`, `rule_date(rule, today, limit)`. A date result gives `{x_say}` and `{x_iso}` in texts; a number gives `{x_m}` (two decimals). |
| `tiers` | | `{field, list: [{name, min, max, limit: rule, ladder: [{text, date: rule}]}]}`. The tier is chosen by the item's `field` value. |
| `limit_field` | | a date field that is the latest allowed date. It drives the calendar's OK / TOO LATE notes. |
| `ladder` | | `{header, step, footer}` texts for the ordered offers or options; `{n}`, `{s}`, `{k}`, `{text}` are filled in |
| `text`, `header` | R | the fact line for one item (format fields: item fields, computed fields, `n`, `id`, `label`, `tier`) and the line above the list |
| `summary` | R | `{line, single, multi}`: the sentence that states all items (`{line}`, `{lines}`, `{count}`) |
| `facts_var`, `summary_var` | R | variable names for prompts |

A date rule is one of:
- `{"type": "business_days" | "calendar_days" | "end_of_month", "n": N}`
- `"today"`, `"next_business_day"`, `"last_business_day_of_week"`, `"business_days_after:N"`
- `"limit"`: the item's limit date

## Clock

`clock.windows[]`: `{var, intro, outro, start: "HH:MM", end: "HH:MM", days: ["today" | "next_business_day" | "business_days_after:N"], business_days_only}`.

## Outcomes

| Field | | Meaning |
|---|---|---|
| `rules` | R | ordered list, first match wins: `{when, outcome, reason}` or `{when, from_note: {skip, map: {note_reason: [outcome, reason]}}}`. `when` keys: `flag` (a ledger key is set), `records` (bool), `gave_up` (bool), `hint`, `notes_any` (bool), `notes_all` (a reason). `reason` is a string or `{from_flag, map}`. |
| `by_hint` | R | `hint → [outcome, reason]`, used when no rule matches. Every `end:<hint>` needs an entry. |
| `no_reason` | | outcomes that are sent without a reason |
| `args` | R | `{outcome: <close-tool arg>, reason: <close-tool arg, optional>}` |

## Closing

`lines`: `hint → line` plus `default`; `[var]` is replaced by a call variable. `after_records`: `{prefix, line, unless_flag}`, the sentence said before the closing line when something was recorded.
