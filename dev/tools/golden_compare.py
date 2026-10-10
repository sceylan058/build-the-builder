"""Compare a generated workflow with a golden one: structure (everything but code) and behaviour (code run on fixtures).

    python3 tools/golden_compare.py golden/b.json out/brief-b.workflow.json
"""
import copy, json, sys, textwrap


def X(code, g):
    """exec the way Freya does: inside a function."""
    names = [k for k in g if k != "vars"]
    src = "def __run(vars, " + ", ".join(names) + "):\n" + textwrap.indent(code, "    ") + "\n__run(VARS, " + ", ".join("N_" + k for k in names) + ")\n"
    exec(src, dict({"VARS": g["vars"]}, **dict(("N_" + k, g[k]) for k in names)))

RENAME = {"account_facts": "item_facts", "debt_statement": "summary_line", "facts_state": "compute_facts_state",
          "pfacts_json": "item_facts_json", "known_pids": "item_ids", "product_count": "item_count"}
CODE_KEYS = ("pre_process_code", "post_process_code")


def rename(o):
    s = json.dumps(o)
    for a, b in RENAME.items():
        s = s.replace("{{" + a + "}}", "{{" + b + "}}").replace('"' + a + '"', '"' + b + '"')
    return json.loads(s)


def strip_code(o):
    o = copy.deepcopy(o)
    for n in o["nodes"].values():
        for t in n.get("tools", []):
            for k in CODE_KEYS:
                t.pop(k, None)
        for a in n.get("pre_actions", []):
            for k in CODE_KEYS:
                a.pop(k, None)
            p = a["function"]["parameters"]["properties"]
            if "code" in p:
                p["code"]["default"] = "<code>"
    return o


def diff(a, b, path=""):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append(f"+ {path}.{k} = {json.dumps(b[k])[:160]}")
            elif k not in b:
                out.append(f"- {path}.{k} = {json.dumps(a[k])[:160]}")
            else:
                out += diff(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, f"{path}[{i}]")
    elif a != b:
        out.append(f"~ {path}: {json.dumps(a)[:160]}  ->  {json.dumps(b)[:160]}")
    return out


# ---------------------------------------------------------------- behaviour on fixtures
PRODUCTS = [{"product_id": "p1", "type": "credit_card", "card_last4": "6604", "past_due": 300, "days_late": 4, "minimum_payment": 90},
            {"product_id": "p2", "type": "personal_loan", "past_due": 900, "days_late": 20, "instalment_amount": 300},
            {"product_id": "p3", "type": "car_loan", "past_due": 75.5, "days_late": 45, "instalment_amount": 25}]


def code_of(n):
    return n["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]


def tool(wf, node, name):
    return [t for t in wf["nodes"][node]["tools"] if t["function"]["name"] == name][0]


def run(wf, now, prods):
    v = {"now": now, "title": "Ms", "last_name": "Rossi", "products": json.dumps(prods)}
    log = []
    N = wf["nodes"]
    X(code_of(N["setup"]), {"vars": v})
    X(code_of(N["compute_facts"]), {"vars": v})
    vi = tool(wf, "identity", "verify_identity")
    for body, data in [({"field": "date_of_birth", "answer": "08/01/1991"}, {"ok": True, "verified": False, "wrong_answers_left": 3, "hint": "day_month_swapped"}),
                       ({"field": "date_of_birth", "answer": "8 January 1991"}, {"ok": True, "verified": True, "wrong_answers_left": 3, "all_verified": False}),
                       ({"field": "phone_last4", "answer": "6 6 0 1"}, {"ok": True, "verified": False, "wrong_answers_left": 2}),
                       ({"field": "phone_last4", "answer": "x"}, {"ok": False, "error": "unreadable"}),
                       ({"field": "phone_last4", "answer": "6604"}, {"ok": True, "verified": True, "wrong_answers_left": 2, "all_verified": True})]:
        cfg = {"body": dict(body, customer_id="c")}
        X(vi["pre_process_code"], {"vars": v, "config": cfg})
        res = {"status": "success", "data": data, "status_code": 200, "header": {}}
        X(vi["post_process_code"], {"vars": v, "result": res})
        log.append(("verify", cfg["body"]["answer"], res["data"]["what_to_do_next"], v.get("id_state")))
    tr = tool(wf, "negotiate", "transfer_to_agent")
    cb = tool(wf, "third_party", "schedule_callback")
    res = {"data": {"ok": False}, "status_code": 500}
    X(cb["post_process_code"], {"vars": v, "result": res}); log.append(("callback fail", res["data"]["what_to_do_next"]))
    rec_names = [t["function"]["name"] for t in N["record"]["tools"]]
    cp = tool(wf, "record", "create_promise")
    for body, data, sc in [({"product_id": "p1", "amount": 300, "date": "2026-10-31"}, None, 500),
                           ({"product_id": "p1", "amount": "300", "date": "2026-10-31"}, {"ok": True, "promise_id": "x"}, 200),
                           ({"product_id": "personal loan", "amount": 950, "date": "2026-10-30"}, None, 500),
                           ({"product_id": "personal loan", "amount": 950, "date": "2026-10-30"}, None, 500)]:
        cfg = {"body": dict(body, customer_id="c")}
        X(cp["pre_process_code"], {"vars": v, "config": cfg})
        res = {"status": "success" if data else "error", "data": data, "status_code": sc}
        X(cp["post_process_code"], {"vars": v, "result": res})
        log.append(("promise", json.dumps(cfg["body"], sort_keys=True), res["data"]["what_to_do_next"]))
    if "add_note" in rec_names:
        an = tool(wf, "record", "add_note")
        for pid, reason in (("car loan", "refused"), ("p2", "service_error")):
            cfg = {"body": {"product_id": pid, "reason": reason, "customer_id": "c"}}
            X(an["pre_process_code"], {"vars": v, "config": cfg}); res = {"data": {"ok": True}, "status_code": 200}
            X(an["post_process_code"], {"vars": v, "result": res}); log.append(("note", cfg["body"]["product_id"], res["data"]["what_to_do_next"]))
    cfg = {"body": {"queue": "restructuring", "customer_id": "c"}}
    vt = dict(v)
    X(tr["pre_process_code"], {"vars": vt, "config": cfg}); res = {"data": {"ok": True}, "status_code": 200}
    X(tr["post_process_code"], {"vars": vt, "result": res}); log.append(("transfer", res["data"]["what_to_do_next"], vt.get("transfer_queue")))
    ends = sorted(k for k in N if k.startswith("end_"))
    scenarios = {"ledger_now": v.get("ledger_json"), "transfer": vt.get("ledger_json"),
                 "empty": None, "notes_paid": "N:paid,paid", "notes_mixed": "N:paid,dispute", "gave_up": "G"}
    for sc, led in scenarios.items():
        for e in ends:
            vv = dict(v)
            vv.pop("close_outcome", None); vv.pop("close_reason", None)
            if led is None:
                vv.pop("ledger_json", None)
            elif led.startswith("N:"):
                r = led[2:].split(",")
                vv["ledger_json"] = json.dumps({"promises": [], "records": [], "notes": [["p1", r[0]], ["p2", r[1]]]})
            elif led == "G":
                vv["ledger_json"] = json.dumps({"promises": [], "records": [], "gave_up": ["p1"]})
            else:
                vv["ledger_json"] = led
            X(code_of(N[e]), {"vars": vv})
            log.append(("end", sc, e, vv.get("close_outcome"), vv.get("close_reason"), vv.get("closing_line")))
    keys = ("today_facts", "callback_facts", "calendar_facts", "account_facts", "item_facts", "debt_statement", "summary_line")
    facts = dict((RENAME.get(k, k), v.get(k)) for k in keys if k in v)
    return facts, log


if __name__ == "__main__":
    g, n = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
    sd = diff(strip_code(rename(g)), strip_code(n))
    print(f"STRUCTURE: {len(sd)} differences")
    for x in sd:
        print("  ", x)
    total = 0
    for now in ("2026-10-14T11:00", "2026-10-16T18:30", "2026-10-23T09:00"):
        for prods in (PRODUCTS[:1], PRODUCTS):
            fg, lg = run(g, now, prods)
            fn, ln = run(n, now, prods)
            for k in sorted(set(fg) | set(fn)):
                if fg.get(k) != fn.get(k):
                    total += 1
                    print(f"FACTS DIFF {now} n={len(prods)} {k}:\n   old: {str(fg.get(k))[:300]}\n   new: {str(fn.get(k))[:300]}")
            for a, b in zip(lg, ln):
                if a != b:
                    total += 1
                    print(f"BEHAVIOUR DIFF {now} n={len(prods)}:\n   old: {a}\n   new: {b}")
            if len(lg) != len(ln):
                total += 1
                print("BEHAVIOUR DIFF: different number of steps", len(lg), len(ln))
    print(f"BEHAVIOUR: {total} differences")
