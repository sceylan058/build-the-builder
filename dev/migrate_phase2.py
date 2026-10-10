"""One-off: migrate a pre-phase2 config to the phase-2 schema. python3 backup/pre-phase2/migrate.py old.json new.json"""
import json, sys

o = json.load(open(sys.argv[1]))
T = o["text"]
use_notes = bool(o.get("use_notes"))
FN = o.get("floor_offer_note", "")


def prompt(s):
    return s.replace("{{account_facts}}", "{{item_facts}}").replace("{{debt_statement}}", "{{summary_line}}")


def step(a):
    amt, date = a.get("amount", "full_or_floor"), a.get("date", "deadline")
    date = "limit" if date == "deadline" else date
    if amt == "floor":
        text = "{floor_m} on {date}" + (" (" + FN + ")" if FN else "")
    elif amt == "full":
        text = "{due_m} on {date}"
    else:
        text = "{due_m} on {date} [or {floor_m} on {date} if the customer already said the full amount is too much" + ("; " + FN if FN else "") + "]"
    return {"text": text, "date": date}


pt = o["product_types"]
floor_map = dict((k, v.get("floor_field", "")) for k, v in pt.items())
floor_spoken = dict((k, v.get("floor_spoken", "minimum")) for k, v in pt.items())
S = T["statement"]
sub = lambda s: s.replace("{name}", "{label}").replace("{past_due}", "{due_m}").replace("{floor}", "{floor_m}")

items = {
    "source_var": "products", "id_field": "product_id", "noun": "product", "noun_plural": "products",
    "label": {"field": "type", "templates": dict((k, v["spoken"]) for k, v in pt.items() if v.get("spoken"))},
    "tiers": {"field": "days_late", "list": [{"name": b["name"], "min": b["min"], "max": b["max"], "limit": b["deadline"],
                                             "ladder": [step(a) for a in b.get("attempts", [])]} for b in o["bands"]]},
    "fields": {
        "due": "num(it.get('past_due'))",
        "floor": "first_num(it.get(by_value(it.get('type'), " + repr(floor_map) + ", '')), f['due'])",
        "floor_spoken": "by_value(it.get('type'), " + repr(floor_spoken) + ", 'minimum')",
        "deadline": "rule_date(T['limit'], today)"},
    "limit_field": "deadline",
    "text": "{n}. product_id {id} = \"{label}\". Past due {due_m}, {days_late} days late. Floor ({floor_spoken}): {floor_m}. Acceptable amount: {floor_m} to {due_m}. Deadline (latest date): {deadline_say} ({deadline_iso}).",
    "ladder": {"header": "   OFFER LIST ({n} offer{s}; each refusal moves to the next offer, nothing goes in between):",
               "step": "     offer {k}: {text}",
               "footer": "     after offer {n} is refused: STOP, this product is refused. No floor offer, no other offer."},
    "header": "PRODUCTS, in this order:",
    "summary": {"line": sub(S["line"]), "single": S["single"], "multi": S["multi"]},
    "facts_var": "item_facts", "summary_var": "summary_line"}

cb = o["callback"]
tools = {
    "verify_identity": {"role": "verify", "description": T["verify_descr"], "fields": o["identity"].get("fields", {})},
    "get_account": {"role": "fetch"},
    "create_promise": {"role": "record", "description": T["promise_descr"], "fields": o.get("promise_fields", {}),
                       "record": {"item_arg": "product_id", "noun": "promise",
                                  "clamp": [{"arg": "amount", "type": "number", "max_field": "due"},
                                            {"arg": "date", "type": "date", "business_day": True, "max_field": "deadline"}],
                                  "confirm": "{amount} on {date}", "confirm_note": "When you tell the customer, use exactly this amount and date.",
                                  "give_up": T["give_up_notes"], "give_up_alone": T["give_up_single"]}},
    "schedule_callback": {"role": "flag", "description": T["callback_descr"], "fields": o.get("callback_fields", {}),
                          "flag": {"value": "booked", "var": "callback_state", "ok_text": "The callback is booked.",
                                   "fail_text": "The callback was NOT booked because the service failed. Try schedule_callback once more with the same values."}},
    "transfer_to_agent": {"role": "flag", "description": T["transfer_descr_post"], "fields": {"queue": {"description": T["transfer_queue_descr"]}},
                          "flag": {"value_arg": "queue", "ledger_key": "transfer", "var": "transfer_queue", "ok_text": "The transfer is done.",
                                   "fail_text": "The transfer did NOT work. Tell the customer you could not transfer the call right now."}},
    "close_call": {"role": "close"}}
if use_notes:
    tools["add_note"] = {"role": "note", "description": T["note_descr"], "fields": o.get("note_fields", {}),
                         "note": {"item_arg": "product_id", "reason_arg": "reason"}}

pre_tr = {"transfer_to_agent": {"description": T["transfer_descr_pre"], "fields": {"queue": {"enum": o["queues_before_verification"]}}}}
post_tr = {"transfer_to_agent": {"description": T["transfer_descr_post"], "fields": {"queue": {"enum": o["queues_after_verification"]}}}}
to_transfer = {"to": "end:transfer", "when": {"set": "transfer_queue"}, "description": "The call was transferred"}
tc = lambda to, d, **k: dict({"to": to, "tool_call": True, "description": d}, **k)

neg_routes = [to_transfer, tc("record", T["record_transition"])]
if not use_notes:
    neg_routes += [tc("end:" + h, T["ending_transitions"][h]) for h in o["single_product_endings"]]
rec_routes = [tc("end:done", T["done_transition"], done=True)]
if not use_notes:
    rec_routes.append(tc("end:service_error", T["service_error_transition"]))

q = o["identity"]["questions"]
nodes = {
    "opening": {"type": "converse", "task": T["opening_task"], "enter": {"tts": T["opening_line"]},
                "extract": [{"name": "who", "type": "string", "enum_values": ["confirmed", "someone_else", "wrong_number", "deceased", "unclear"],
                             "description": T["who_descr"], "min_confidence": 0.5}],
                "tools": ["transfer_to_agent"], "tool_overrides": pre_tr, "turns": 8, "overflow": "end:unclear",
                "routes": [{"to": "setup", "when": {"eq": ["who", "confirmed"]}, "description": "The person confirmed they are the customer"},
                           {"to": "setup", "when": {"eq": ["who", "someone_else"]}, "description": "Someone else answered"},
                           {"to": "end:wrong_number", "when": {"eq": ["who", "wrong_number"]}, "description": "Wrong number"},
                           {"to": "end:deceased", "when": {"eq": ["who", "deceased"]}, "description": "The customer has died"},
                           to_transfer, tc("end:unclear", T["unclear_transition"]), tc("end:declined_pre", T["declined_pre_transition"])]},
    "setup": {"type": "clock", "next": "identity",
              "routes": [{"to": "third_party", "when": {"eq": ["who", "someone_else"]}, "description": "Someone else answered"}]},
    "third_party": {"type": "converse", "task": T["third_party_task"], "enter": {"llm": T["third_party_enter"]}, "tools": ["schedule_callback"],
                    "turns": 12, "overflow": "end:no_callback",
                    "routes": [{"to": "end:callback", "when": {"eq": ["callback_state", "booked"]}, "description": "Callback booked"},
                               tc("end:no_callback", T["no_callback_transition"]), tc("end:wrong_number", T["wrong_number_transition"]),
                               tc("end:deceased", T["deceased_transition"])]},
    "identity": {"type": "verify", "task": T["identity_task"], "enter": {"llm": T["identity_enter"]}, "tools": ["verify_identity", "transfer_to_agent"],
                 "tool_overrides": pre_tr, "turns": 20, "overflow": "end:declined",
                 "verify": {"tool": "verify_identity", "questions": q, "args": {"field": "field", "answer": "answer"},
                            "response": {"ok": "ok", "verified": "verified", "all_verified": "all_verified", "wrong_left": "wrong_answers_left",
                                         "hint": "hint", "swap_hint": "swap"},
                            "on_pass": "fetch_account", "on_fail": "end:failed", "pass_description": "Both security questions passed"},
                 "routes": [to_transfer, tc("end:declined", T["declined_transition"])]},
    "fetch_account": {"type": "fetch", "tool": "get_account", "retries": 2, "ok_field": "ok", "description": "Account loaded",
                      "map": [{"path": "data.products", "var": "products"}, {"path": "data.ok", "var": "account_ok"}],
                      "next": "compute_facts", "fail": "end:account_error"},
    "compute_facts": {"type": "compute", "next": "negotiate", "fail": "end:account_error"},
    "negotiate": {"type": "converse", "task": prompt(T["negotiate_task"]), "enter": {"tts": "{{summary_line}}"}, "tools": ["transfer_to_agent"],
                  "tool_overrides": post_tr, "turns": 45, "overflow": "record" if use_notes else "end:refused", "routes": neg_routes},
    "record": {"type": "converse", "task": prompt(T["record_task"]), "enter": {"llm": T["record_enter"]},
               "tools": ["create_promise"] + (["add_note"] if use_notes else []), "turns": 15, "overflow": "end:done", "routes": rec_routes}}

H = o["outcomes"]
rules = [{"when": {"flag": "transfer"}, "outcome": "transferred", "reason": {"from_flag": "transfer", "map": o["queue_reason"]}},
         {"when": {"records": True}, "outcome": "promise"},
] + ([{"when": {"notes_all": "paid"}, "outcome": H["paid"][0], "reason": H["paid"][1]},
         {"when": {"notes_any": True}, "from_note": {"skip": ["paid"], "map": o.get("note_outcome", {})}}] if use_notes else []) + [
         {"when": {"hint": "done", "gave_up": True}, "outcome": H["service_error"][0], "reason": H["service_error"][1]},
         {"when": {"hint": "done"}, "outcome": H["refused"][0], "reason": H["refused"][1]}]
lines = dict((k, v) for k, v in o["closing_lines"].items() if k != "promise_prefix")

new = {
    "openapi": o["openapi"],
    "calendar": {"workdays": o["calendar"]["workdays"], "holidays": o["calendar"]["holidays"], "now_var": "now",
                 "numeric_date_order": "dmy", "week_start": 0, "horizon_days": 21},
    "system_prompt": T["system_prompt"],
    "items": items,
    "clock": {"windows": [{"var": "callback_facts", "intro": "A callback can ONLY be booked on: ",
                           "outro": ". Both ends of the time window are included. Any other day or time is outside the window.",
                           "start": cb["start"], "end": cb["end"], "days": cb["days"], "business_days_only": cb.get("business_days_only", True)}]},
    "tools": tools,
    "flow": {"start": "opening", "nodes": nodes},
    "outcomes": {"rules": rules, "by_hint": H, "no_reason": o.get("no_reason_outcomes", []), "args": {"outcome": "outcome", "reason": "reason"}},
    "closing": {"lines": lines, "after_records": {"prefix": o["closing_lines"]["promise_prefix"], "line": "done", "unless_flag": "transfer"}},
    "test_variables": o.get("test_variables", {})}
json.dump(new, open(sys.argv[2], "w"), indent=1)
print("migrated", sys.argv[2])
