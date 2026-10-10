# Phase 2 audit: domain dependencies (pre-phase2 gen.py)

Classes: (1) domain word, (2) structural logic, (3) tool/endpoint name, (4) assumption.

| file:line | term | class | general name / target |
|---|---|---|---|
| gen.py:57,149-157 | `BANDS`, `band_for(days_late)` | 2+4 | `tiers` keyed on a configurable item field |
| gen.py:58,259 | `PTYPES`, `product_types` | 1 | `items.label` (template chosen by a field) |
| gen.py:258,534,622 | `product_id` | 3 | `items.id_field`, `record.item_arg` |
| gen.py:265 | `past_due` | 1 | `items.fields` expression |
| gen.py:266 | `floor`, `floor_field` | 1 | `items.fields` expression |
| gen.py:269-270 | `days_late`, `deadline_for` | 1+2 | tier key; `date_rule()` from a config rule |
| gen.py:271-288 | attempts / "OFFER LIST" / "refusal" | 1+2 | `ladder` (steps with text + date rule, header/footer text) |
| gen.py:287 | facts line "product_id … Past due … days late … Floor" | 1 | `items.text` template |
| gen.py:292,324-327 | `STATEMENT`, `debt_statement` | 1 | `items.summary` templates, var `summary_line` |
| gen.py:299-304 | "TOO LATE", "every product" | 1 | `calendar.limit_field`, `items.noun` |
| gen.py:318 | "PRODUCTS, in this order" | 1 | `items.header` |
| gen.py:186,580,594 | ledger keys `promises`/`notes`/`gave_up`/`transfer` | 2+1 | `records` / `notes` / `gave_up` / `flags{}` |
| gen.py:342-358 | outcome cascade (transfer > promise > notes > service_error > refused) | 4 | ordered `outcome_rules` in config |
| gen.py:345,351,356,358 | `transferred`, `paid`, `no_promise`, `service_error`, `refused` | 4 | config `outcome_rules` / `hint_outcomes` |
| gen.py:729-730 | `QUEUE_REASON`, `NOTE_OUTCOME`, `USE_NOTES` | 1+4 | `outcome_rules[].reason.map`, note tool present or not |
| gen.py:446,459 | `all_verified`, `wrong_answers_left`, `hint` | 3 | `verify.response` field map |
| gen.py:394-430 | `norm_date` day-before-month | 4 | `calendar.numeric_date_order` |
| gen.py:60-61 | English weekday/month names | 4 | `calendar.weekday_names` / `month_names` (English documented default) |
| gen.py:63,202 | workdays default Mon–Fri | 4 | `calendar.workdays` required |
| gen.py:208-236 | callback window text, `CB` | 1+4 | `clock.windows[]` (name, days, hours, intro) |
| gen.py:745 | `transfer_to_agent`, `queue` | 3 | tool with role `flag` |
| gen.py:750 | `who` enum (confirmed/someone_else/…) | 4 | greeting `extract` in config |
| gen.py:752-852 | fixed node graph opening→setup→identity→fetch→compute→negotiate→record→farewell→close→hang_up | 4 | config `flow` (node library) |
| gen.py:773 | `schedule_callback` | 3 | tool role `flag` |
| gen.py:788,794,798 | `verify_identity` | 3+4 | optional `verify` node; no node when the brief has no check |
| gen.py:804-808 | `get_account` | 3 | `fetch` node(s), any tool |
| gen.py:835-841 | `create_promise`, `add_note` | 3 | tool roles `record` / `note` |
| gen.py:850 | `close_call` + `outcome`/`reason` | 3 | `close.tool`, `close.args` |
| gen.py:583 etc. | hook texts "promise", "product" | 1 | built from `items.noun`, `record.noun` |
| gen.py PROMISE_PRE | clamp `amount ≤ past_due`, `date ≤ deadline`, business day | 4 | `record.clamp[]` rules |
| SKILL.md (46 lines) | collections words in architecture, hints table | 1 | SKILL.md rewritten domain-free |
| hooktest.py (17) | fixtures with products/promises | 1 | fixtures moved into config `test_fixture` |
| examples/agent_builder.py | none (only "install", "refused" as English words) | – | no change |

Hard-coded in pre-phase2 gen.py:
- **Node count/order:** always 10 core nodes + one end node per hint (A 27, B 22).
- **Outcome values:** `transferred`, `promise`, `paid`, `no_promise`, `service_error`, `refused`.
- **Tool names:** `verify_identity`, `get_account`, `create_promise`, `add_note`, `schedule_callback`, `transfer_to_agent`, `close_call`.
- **Calendar:** Monday to Friday default, English names, day-before-month dates, deadlines measured in business days from `now`, the week starting Monday, the variable name `now`.
- **Identity:** always a check, fields `field` / `answer`, response `verified` / `all_verified` / `wrong_answers_left` / `hint`.
