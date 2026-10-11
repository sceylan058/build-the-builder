"""Static safety nets for a generated workflow. Exit 1 on any error.

    python3 builder/check.py <workflow.json> <openapi.json> [--config C] [--bundle B] [--json]

Rules: 1 OpenAPI conformance, 2 graph lint, 3 code run over a time/payload grid (the way Freya runs snippets),
4 provenance lint (config literals must come from the brief), 5 spoken-text lint (no forbidden words before verification).
"""
import argparse, datetime, json, re, sys, textwrap

PH = re.compile(r"\{\{\s*([A-Za-z_][\w.\-]*)\s*\}\}")
SYSTEM_PREFIXES = ("system.", "call.", "date.", "time.")


# --------------------------------------------------------------------------------------------------- helpers

def api_functions(wf):
    """Every api_call function in the workflow: (where, function dict, owning node name or None, kind)."""
    out = []
    for name, n in wf.get("nodes", {}).items():
        for t in n.get("tools", []) or []:
            if t.get("function", {}).get("handler") == "__function__:api_call":
                out.append((f"node {name} tool {t['function'].get('name')}", t, name, "tool"))
        for a in n.get("pre_actions", []) or []:
            if a.get("function", {}).get("handler") == "__function__:api_call":
                out.append((f"node {name} pre_action {a['function'].get('name')}", a, name, "pre_action"))
    for t in wf.get("tools", []) or []:
        if t.get("function", {}).get("handler") == "__function__:api_call":
            out.append((f"lifecycle tool {t['function'].get('name')}", t, None, "lifecycle"))
    return out


def op_of(api, path):
    p = api.get("paths", {}).get(path, {})
    return p.get("post") or p.get("put") or next(iter(p.values()), None) if p else None


def req_schema(op):
    try:
        return op["requestBody"]["content"]["application/json"]["schema"]
    except Exception:
        return {}


def resp_schema(op):
    try:
        r = op["responses"].get("200") or next(iter(op["responses"].values()))
        return r["content"]["application/json"]["schema"]
    except Exception:
        return {}


def code_snippets(wf):
    """(where, code, kind) for code nodes and hooks."""
    out = []
    for name, n in wf.get("nodes", {}).items():
        for a in n.get("pre_actions", []) or []:
            f = a.get("function", {})
            if f.get("handler") == "__function__:code_exec":
                out.append((name, f["parameters"]["properties"]["code"]["default"], "node"))
            for k in ("pre_process_code", "post_process_code"):
                if a.get(k):
                    out.append((f"{name}:{f.get('name')}:{k}", a[k], k))
        for t in n.get("tools", []) or []:
            for k in ("pre_process_code", "post_process_code"):
                if t.get(k):
                    out.append((f"{name}:{t['function'].get('name')}:{k}", t[k], k))
    return out


def compile_wrapped(code, args):
    """Freya runs a snippet inside a function: compile it that way once."""
    src = "def __run(" + ", ".join(args) + "):\n" + textwrap.indent(code, "    ") + "\n"
    g = {}
    exec(compile(src, "<snippet>", "exec"), g)
    return g["__run"]


class Recorder(dict):
    """A vars dict that remembers which keys were written."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.written = set()

    def __setitem__(self, k, v):
        self.written.add(k)
        super().__setitem__(k, v)


def edges(n):
    out = [t.get("target_node") for t in n.get("transitions", []) or []]
    for k in ("max_turn_transition", "passthrough_default_transition"):
        if n.get(k):
            out.append(n[k])
    return [x for x in out if x]


def walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path, o


# --------------------------------------------------------------------------------------------------- rule 1

def rule_openapi(wf, api, cfg, E):
    servers = api.get("servers") or []
    if not servers or not servers[0].get("url"):
        E.append("R1 openapi: the tool API file has no servers[0].url")
        return
    base = servers[0]["url"].rstrip("/")
    for where, fn, node, kind in api_functions(wf):
        props = fn["function"].get("parameters", {}).get("properties", {})
        url = (props.get("url") or {}).get("default", "")
        if not url.startswith(base + "/"):
            E.append(f"R1 openapi: {where} calls {url!r}, expected {base}/<path>")
            continue
        path = url[len(base):]
        op = op_of(api, path)
        if not op:
            E.append(f"R1 openapi: {where} calls path {path!r}, which is not in the tool API file")
            continue
        sch = req_schema(op)
        allowed = sch.get("properties", {})
        body = (props.get("body") or {}).get("properties", {})
        for f, leaf in body.items():
            if f not in allowed:
                E.append(f"R1 openapi: {where} sends body field {f!r}, not in {path} (fields: {', '.join(allowed)})")
                continue
            spec = allowed[f]
            d = leaf.get("default")
            if isinstance(d, str) and "{{" not in d and spec.get("enum") and d not in spec["enum"]:
                E.append(f"R1 openapi: {where} bakes {f}={d!r}, not one of {spec['enum']}")
            if leaf.get("enum") and spec.get("enum"):
                bad = [x for x in leaf["enum"] if x not in spec["enum"]]
                if bad:
                    E.append(f"R1 openapi: {where} offers {f} values {bad}, not in {spec['enum']}")
            if isinstance(d, (int, float)) and not isinstance(d, bool) and spec.get("type") == "string":
                E.append(f"R1 openapi: {where} bakes a number into string field {f!r}")
        for f in sch.get("required", []):
            if f not in body:
                E.append(f"R1 openapi: {where} never sends required field {f!r} of {path}")
    if cfg:
        rule_config_enums(api, cfg, E)


def tool_props(api, name):
    return req_schema(op_of(api, "/" + name) or {}).get("properties", {})


def rule_config_enums(api, cfg, E):
    tools = cfg.get("tools", {})
    close = [k for k, t in tools.items() if t.get("role") == "close"]
    oc = cfg.get("outcomes", {})
    if close:
        props = tool_props(api, close[0])
        oarg, rarg = oc.get("args", {}).get("outcome"), oc.get("args", {}).get("reason")
        outs, reasons = set(), set()
        for r in oc.get("rules", []):
            if r.get("outcome"):
                outs.add(r["outcome"])
            if isinstance(r.get("reason"), str) and r["reason"]:
                reasons.add(r["reason"])
            if isinstance(r.get("reason"), dict):
                reasons |= {v for v in r["reason"].get("map", {}).values() if v}
            for o, rs in r.get("from_note", {}).get("map", {}).items():
                outs.add(rs[0])
                if rs[1]:
                    reasons.add(rs[1])
        for o, rs in oc.get("by_hint", {}).items():
            outs.add(rs[0])
            if rs[1]:
                reasons.add(rs[1])
        if oarg not in props:
            E.append(f"R1 enums: outcomes.args.outcome={oarg!r} is not a field of {close[0]}")
        elif props[oarg].get("enum"):
            bad = sorted(o for o in outs if o and o not in props[oarg]["enum"])
            if bad:
                E.append(f"R1 enums: outcomes {bad} are not allowed by {close[0]}.{oarg} {props[oarg]['enum']}")
        if rarg and rarg in props and props[rarg].get("enum"):
            bad = sorted(r for r in reasons if r not in props[rarg]["enum"])
            if bad:
                E.append(f"R1 enums: reasons {bad} are not allowed by {close[0]}.{rarg} {props[rarg]['enum']}")
        if rarg and rarg not in props:
            E.append(f"R1 enums: outcomes.args.reason={rarg!r} is not a field of {close[0]}")
    for name, t in tools.items():
        props = tool_props(api, name)
        if t.get("role") == "note":
            ra = t["note"]["reason_arg"]
            en = props.get(ra, {}).get("enum")
            used = set()
            for r in oc.get("rules", []):
                used |= set(r.get("from_note", {}).get("map", {})) | set(r.get("from_note", {}).get("skip", []))
                if r.get("when", {}).get("notes_all"):
                    used.add(r["when"]["notes_all"])
            if en:
                bad = sorted(u for u in used if u not in en)
                if bad:
                    E.append(f"R1 enums: note reasons {bad} used in outcomes are not allowed by {name}.{ra} {en}")
        if t.get("role") == "flag" and t["flag"].get("value_arg"):
            va = t["flag"]["value_arg"]
            en = props.get(va, {}).get("enum")
            used = set()
            for r in oc.get("rules", []):
                if isinstance(r.get("reason"), dict) and r["reason"].get("from_flag") == t["flag"].get("ledger_key"):
                    used |= set(r["reason"].get("map", {}))
            if en:
                bad = sorted(u for u in used if u not in en)
                if bad:
                    E.append(f"R1 enums: {name}.{va} values {bad} used in outcomes are not in {en}")
        used_args = []
        if t.get("role") == "record":
            R = t["record"]
            used_args += [R.get("item_arg")] + [c.get("arg") for c in R.get("clamp", [])] + re.findall(r"\{(\w+)\}", R.get("confirm", ""))
        if t.get("role") == "note":
            used_args += [t["note"].get("item_arg"), t["note"].get("reason_arg")]
        if t.get("role") == "flag" and t["flag"].get("value_arg"):
            used_args.append(t["flag"]["value_arg"])
        for a_ in used_args:
            if a_ and a_ not in props:
                E.append(f"R1 enums: tools.{name} ({t.get('role')}) uses argument {a_!r}, which is not a field of {name} (fields: {', '.join(props)})")
        for f, info in (t.get("fields") or {}).items():
            if f not in props and t.get("role") not in ("fetch", "close"):
                E.append(f"R1 enums: tools.{name}.fields.{f} is not a field of {name} (fields: {', '.join(props)})")
    for nname, n in cfg.get("flow", {}).get("nodes", {}).items():
        v = n.get("verify")
        if v:
            for a_ in v.get("args", {}).values():
                if a_ and a_ not in tool_props(api, v["tool"]):
                    E.append(f"R1 enums: verify args use {a_!r}, which is not a field of {v['tool']}")
        if v and v.get("args", {}).get("field"):
            props = tool_props(api, v["tool"])
            en = props.get(v["args"]["field"], {}).get("enum")
            if en:
                bad = [q["field"] for q in v.get("questions", []) if q["field"] not in en]
                if bad:
                    E.append(f"R1 enums: identity questions {bad} are not allowed by {v['tool']}.{v['args']['field']} {en}")
        if v and not v.get("args", {}).get("field"):
            props = tool_props(api, v["tool"])
            bad = [q["field"] for q in v.get("questions", []) if q["field"] not in props]
            if bad:
                E.append(f"R1 enums: identity questions {bad} are not fields of {v['tool']}")
        for tname, ov in (n.get("tool_overrides") or {}).items():
            props = tool_props(api, tname)
            for f, info in (ov.get("fields") or {}).items():
                en = props.get(f, {}).get("enum")
                if info.get("enum") and en:
                    bad = [x for x in info["enum"] if x not in en]
                    if bad:
                        E.append(f"R1 enums: node {nname} offers {tname}.{f} values {bad}, not in {en}")
    it = cfg.get("items")
    if it and it.get("label", {}).get("templates"):
        fld = it["label"].get("field")
        for name, t in tools.items():
            item_schema = list_item_schema(resp_schema(op_of(api, "/" + name) or {}), it.get("source_path"))
            if item_schema and fld in item_schema.get("properties", {}):
                en = item_schema["properties"][fld].get("enum")
                if en:
                    bad = [k for k in it["label"]["templates"] if k not in en]
                    if bad:
                        E.append(f"R1 enums: items.label.templates keys {bad} are not values of {name}.{fld} {en}")


def list_item_schema(sch, path=None):
    """First array-of-objects schema inside a response schema (or the one at `path`)."""
    props = sch.get("properties", {})
    for k, v in props.items():
        if v.get("type") == "array" and isinstance(v.get("items"), dict) and v["items"].get("properties"):
            if not path or path.split(".")[-1] == k:
                return v["items"]
    return None


# --------------------------------------------------------------------------------------------------- rule 2

def rule_graph(wf, cfg, produced, E):
    nodes = wf.get("nodes", {})
    start = wf.get("initial_node")
    if start not in nodes:
        E.append(f"R2 graph: initial_node {start!r} is not a node")
        return
    for name, n in nodes.items():
        for t in edges(n):
            if t not in nodes and t != "__previous__":
                E.append(f"R2 graph: node {name} routes to missing node {t!r}")
    seen, todo = set(), [start]
    while todo:
        x = todo.pop()
        if x in seen or x not in nodes:
            continue
        seen.add(x)
        todo += edges(nodes[x])
    for name in nodes:
        if name not in seen:
            E.append(f"R2 graph: node {name} is not reachable from {start}")
    can_end = {k for k, n in nodes.items() if n.get("node_type") == "end_call"}
    changed = True
    while changed:
        changed = False
        for k, n in nodes.items():
            if k not in can_end and any(t in can_end for t in edges(n)):
                can_end.add(k)
                changed = True
    for k in seen:
        if k not in can_end:
            E.append(f"R2 graph: node {k} has no path to an end_call node")
    for name, n in nodes.items():
        typ = n.get("node_type")
        if n.get("passthrough"):
            tr = n.get("transitions") or []
            if not tr or tr[-1].get("condition", {}).get("operator") != "always":
                E.append(f"R2 graph: passthrough node {name} does not end with an always transition")
        if "max_node_turns" in n and not n.get("max_turn_transition"):
            E.append(f"R2 graph: node {name} sets max_node_turns without max_turn_transition")
        if n.get("tools") and typ != "conversation":
            E.append(f"R2 graph: node {name} ({typ}) has tools; only conversation nodes keep them")
        if n.get("pre_actions") and typ not in ("api_request", "code"):
            E.append(f"R2 graph: node {name} ({typ}) has pre_actions; only api_request/code nodes keep them")
        if n.get("response_mapping") and typ not in ("api_request", "code"):
            E.append(f"R2 graph: node {name} has a node-level response_mapping but is a {typ} node")
        for m in n.get("response_mapping", []) or []:
            if not str(m.get("path", "")).startswith("data."):
                E.append(f"R2 graph: node {name} maps path {m.get('path')!r}; paths must start with 'data.'")
        for t in n.get("tools", []) or []:
            for m in t.get("response_mapping", []) or []:
                if not str(m.get("path", "")).startswith("data."):
                    E.append(f"R2 graph: tool {t['function'].get('name')} in {name} maps path {m.get('path')!r}; paths must start with 'data.'")
        for x in n.get("extraction_schema", []) or []:
            if "min_confidence" not in x:
                E.append(f"R2 graph: extraction field {x.get('name')} in {name} has no min_confidence")
    for p, v in walk(wf):
        if v is None:
            E.append(f"R2 graph: null value at {p}")
    for where, code, kind in code_snippets(wf):
        if "{{" in code or "}}" in code:
            E.append(f"R2 graph: code in {where} contains '{{{{' or '}}}}'")
    for name, n in nodes.items():
        texts = [n.get("task_message", ""), n.get("loop_prompt", ""), n.get("routing_prompt", ""),
                 (n.get("on_enter") or {}).get("text", ""), (n.get("on_enter") or {}).get("prompt", "")]
        term = n.get("terminal", {}).get("function", {}).get("parameters", {}).get("properties", {})
        texts.append((term.get("spoken_message") or {}).get("default", ""))
        for ph in PH.findall(" ".join(str(t) for t in texts)):
            if not is_produced(ph, produced):
                E.append(f"R2 graph: node {name} uses {{{{{ph}}}}} but nothing produces it")
    for ph in PH.findall(wf.get("system_prompt", "")):
        if not is_produced(ph, produced):
            E.append(f"R2 graph: system_prompt uses {{{{{ph}}}}} but nothing produces it")


def is_produced(ph, produced):
    if ph in produced or ph.startswith(SYSTEM_PREFIXES):
        return True
    if re.match(r".+\.(current_turns|total_turns)$", ph):
        return True
    if re.match(r".+_(response|args)\..+", ph) or re.match(r".+_(success|failure)_count$", ph):
        return True
    return False


def static_produced(wf, cfg):
    p = set((wf.get("test_variables") or {}).keys()) | {"customer_id"}
    if cfg:
        p |= set(cfg.get("call_variables", []))
    for name, n in wf.get("nodes", {}).items():
        p |= {x.get("name") for x in n.get("extraction_schema", []) or []}
        p |= {m.get("variable") for m in n.get("response_mapping", []) or []}
        for t in n.get("tools", []) or []:
            p |= {m.get("variable") for m in t.get("response_mapping", []) or []}
    for where, code, kind in code_snippets(wf):
        p |= set(re.findall(r"vars\[\s*'([A-Za-z_]\w*)'\s*\]\s*=", code))
    return p


# --------------------------------------------------------------------------------------------------- rule 3

def sample_items(item_schema, n, offset=0):
    props = item_schema.get("properties", {})
    ints = [1, 3, 6, 9, 13, 21, 33, 41, 58]
    nums = [111.11, 2345.67, 66.6, 512.34, 87.0]
    out = []
    for i in range(n):
        it = {}
        for k, s in props.items():
            j = i + offset
            if s.get("enum"):
                it[k] = s["enum"][j % len(s["enum"])]
            elif s.get("type") == "integer":
                it[k] = ints[(j * 3) % len(ints)]
            elif s.get("type") == "number":
                it[k] = nums[j % len(nums)]
            elif s.get("type") == "boolean":
                it[k] = True
            elif k.lower().endswith("id"):
                it[k] = f"x{i + 1}"
            else:
                it[k] = str(9876 - 37 * j)[-4:]
        out.append(it)
    return out


def grid_nows(cfg):
    hol = (cfg or {}).get("calendar", {}).get("holidays") or []
    starts = []
    if hol:
        try:
            h = datetime.date.fromisoformat(hol[0])
            starts.append(h - datetime.timedelta(days=h.weekday()))
        except Exception:
            pass
    starts.append(datetime.date(2026, 10, 26))   # crosses a month end
    starts.append(datetime.date(2026, 12, 28))   # crosses a year end
    if len(starts) < 3:
        starts.append(datetime.date(2026, 10, 12))
    out = []
    for s in starts[:3]:
        for d in range(7):
            day = s + datetime.timedelta(days=d)
            for hm in ("08:00", "10:30", "18:59", "19:30"):
                for fmt in ("{d}T{t}", "{d}T{t}:00", "{d} {t}", "{d}T{t}:00Z"):
                    out.append((day, fmt.format(d=day.isoformat(), t=hm)))
    return out


def rule_code(wf, api, cfg, produced, E, quick=False):
    """Run every snippet like Freya does over a grid. Adds every variable written to `produced`."""
    nodes = wf.get("nodes", {})
    now_var = (cfg or {}).get("calendar", {}).get("now_var", "now")
    # item payloads: any mapping whose path points at an array of objects in a response schema
    payload_vars = []
    for name, n in nodes.items():
        maps = [(m, n) for m in n.get("response_mapping", []) or []]
        for t in n.get("tools", []) or []:
            maps += [(m, t) for m in t.get("response_mapping", []) or []]
        for m, owner in maps:
            fn = owner.get("pre_actions", [owner])[0] if owner is n else owner
            url = fn.get("function", {}).get("parameters", {}).get("properties", {}).get("url", {}).get("default", "")
            base = (api.get("servers") or [{}])[0].get("url", "").rstrip("/")
            op = op_of(api, url[len(base):]) if url.startswith(base) else None
            sch = resp_schema(op or {})
            key = str(m.get("path", "")).split(".", 1)[-1]
            arr = sch.get("properties", {}).get(key)
            if arr and arr.get("type") == "array" and isinstance(arr.get("items"), dict):
                payload_vars.append((m["variable"], arr["items"]))
    order, seen, todo = [], set(), [wf.get("initial_node")]
    while todo:
        x = todo.pop(0)
        if x in seen or x not in nodes:
            continue
        seen.add(x)
        order.append(x)
        todo += edges(nodes[x])
    code_nodes = [(k, nodes[k]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]) for k in order
                  if nodes[k].get("node_type") == "code"]
    ends = [k for k, c in code_nodes if any(t.get("target_node") == "farewell" for t in nodes[k].get("transitions", []))]
    try:
        compiled = dict((k, compile_wrapped(c, ["vars"])) for k, c in code_nodes)
    except SyntaxError as ex:
        E.append(f"R3 code: a code node does not compile: {ex}")
        return
    readers = set()
    for name, n in nodes.items():
        readers |= set(PH.findall(" ".join([n.get("task_message", ""), json.dumps(n.get("on_enter") or {})])))
        for t in n.get("transitions", []) or []:
            for p, v in walk(t.get("condition", {})):
                if p.endswith(".variable"):
                    readers.add(v)
    code_written = set()
    errors_seen = set()
    grid = grid_nows(cfg)
    if quick:
        grid = grid[::7]
    for day, now in grid:
        for count in (1, 2, 3):
            v = Recorder({now_var: now, "title": "Mx", "first_name": "Sam", "last_name": "Doe", "customer_id": "c_test"})
            for var, sch in payload_vars:
                v[var] = json.dumps(sample_items(sch, count))
            v.written = set()
            for k, c in code_nodes:
                if k in ends:
                    continue
                try:
                    compiled[k](v)
                except Exception as ex:
                    errors_seen.add(f"R3 code: node {k} raised {type(ex).__name__}: {ex} (now={now}, items={count})")
            for key in v.written:
                val = v.get(key)
                if isinstance(val, str) and (val.startswith("ERROR") or val == "error" or val.startswith("error ")):
                    errors_seen.add(f"R3 code: {key}={val[:120]!r} after the code nodes (now={now}, items={count})")
            if "today_iso" in v and v["today_iso"] != day.isoformat():
                errors_seen.add(f"R3 code: today_iso={v['today_iso']} but now={now}")
            code_written |= v.written
            for k in ends:
                vv = Recorder(dict(v))
                try:
                    compiled[k](vv)
                except Exception as ex:
                    errors_seen.add(f"R3 code: end node {k} raised {type(ex).__name__}: {ex}")
                    continue
                if not vv.get("closing_line"):
                    errors_seen.add(f"R3 code: end node {k} set no closing_line (now={now})")
                code_written |= vv.written
            for r in readers:
                if r in code_written and r in v.written and (v.get(r) is None or v.get(r) == ""):
                    errors_seen.add(f"R3 code: {r} is read by a prompt or condition but is empty (now={now}, items={count})")
    # hooks: run once with a plausible body and a success result, to learn what they write and that they do not raise
    for name, n in nodes.items():
        for t in n.get("tools", []) or []:
            props = t["function"]["parameters"]["properties"].get("body", {}).get("properties", {})
            body = {}
            for f, leaf in props.items():
                body[f] = (leaf.get("enum") or ["x1"])[0] if leaf.get("type") == "string" else (1 if leaf.get("type") in ("number", "integer") else True)
            for k, args in (("pre_process_code", ["vars", "config"]), ("post_process_code", ["vars", "result"])):
                if not t.get(k):
                    continue
                try:
                    fn = compile_wrapped(t[k], args)
                except SyntaxError as ex:
                    E.append(f"R3 code: hook {k} of {t['function']['name']} does not compile: {ex}")
                    continue
                v = Recorder({now_var: "2026-10-14T11:00"})
                try:
                    if k == "pre_process_code":
                        fn(v, {"body": dict(body), "url": "", "method": "POST", "headers": {}})
                    else:
                        fn(v, {"status": "success", "status_code": 200, "data": {"ok": True}})
                except Exception as ex:
                    E.append(f"R3 code: hook {k} of {t['function']['name']} raised {type(ex).__name__}: {ex}")
                code_written |= v.written
    E.extend(sorted(errors_seen)[:40])
    produced |= code_written


# --------------------------------------------------------------------------------------------------- rule 4

NUM_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
             "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
             "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "ninety": 90, "hundred": 100,
             "once": 1, "twice": 2, "thrice": 3, "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
             "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "fifteenth": 15, "twentieth": 20, "thirtieth": 30}
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]


def norm(s):
    s = PH.sub(" VAR ", str(s))
    s = re.sub(r"\{[A-Za-z_]\w*\}", " VAR ", s)
    s = re.sub(r"\[[A-Za-z_]\w*\]", " VAR ", s)
    s = s.lower().replace("’", "'").replace("“", '"').replace("”", '"')
    return " ".join(re.findall(r"[a-z0-9']+|VAR", s.replace("var", "VAR")))


def bundle_facts(text):
    t = text.lower()
    # numbers that are not values: list numbering, section numbers, rule references, digits inside dates and times
    tn = re.sub(r"(?m)^\s*(?:#+\s*)?\d{1,3}[.)]\s", " ", t)
    tn = re.sub(r"\brules?\s+\d{1,3}(?:\s*(?:,|and|or|to|-)\s*\d{1,3})*", " ", tn)
    tn = re.sub(r"\b(?:section|step|brief\s+[a-z])\s+\d{1,3}\b", " ", tn)
    tn = re.sub(r"\b\d{4}-\d{2}-\d{2}(?:t\d{2}:\d{2})?\b", " ", tn)
    tn = re.sub(r"\b\d{1,2}[:.]\d{2}\b", " ", tn)
    nums = {int(x) for x in re.findall(r"\b(\d{1,6})(?:st|nd|rd|th)?\b", tn)}
    nums |= {v for w, v in NUM_WORDS.items() if re.search(r"\b" + w + r"\b", tn)}
    for m in re.findall(r"(\d+)\s*%", tn):
        nums.add(int(m))
    dates = set(re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", t))
    for d, mo, y in re.findall(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(MONTHS) + r")\s*,?\s*(\d{4})?", t):
        for yy in ([y] if y else ["2025", "2026", "2027"]):
            dates.add(f"{yy}-{MONTHS.index(mo) + 1:02d}-{int(d):02d}")
    for mo, d, y in re.findall(r"\b(" + "|".join(MONTHS) + r")\s+(\d{1,2})(?:st|nd|rd|th)?\s*,?\s*(\d{4})?", t):
        for yy in ([y] if y else ["2025", "2026", "2027"]):
            dates.add(f"{yy}-{MONTHS.index(mo) + 1:02d}-{int(d):02d}")
    for a, b, y in re.findall(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b", t):
        dates.add(f"{y}-{int(b):02d}-{int(a):02d}")
        dates.add(f"{y}-{int(a):02d}-{int(b):02d}")
    times = {f"{int(h):02d}:{m}" for h, m in re.findall(r"\b(\d{1,2})[:.](\d{2})\b", t)}
    for h, ap in re.findall(r"\b(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)", t):
        hh = int(h) % 12 + (12 if ap.startswith("p") else 0)
        times.add(f"{hh:02d}:00")
    return nums, dates, times, norm(text)


def rule_provenance(cfg, bundle_text, E):
    nums, dates, times, ntext = bundle_facts(bundle_text)
    derived = (cfg.get("provenance") or {}).get("derived") or {}
    dnorm = {norm(k) for k in derived} | {str(k) for k in derived}

    def ok_derived(v):
        return str(v) in derived or norm(v) in dnorm

    def num_ok(x, where):
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)) and float(x).is_integer() and int(x) in nums:
            return
        if ok_derived(x) or ok_derived(f"{where}={x}"):
            return
        E.append(f"R4 provenance: {where} = {x} does not appear in the brief (add provenance.derived[\"{where}={x}\"] with its formula if it is derived)")

    low = bundle_text.lower()
    for v in cfg.get("call_variables", []):
        if v.lower() not in low and not ok_derived(v):
            E.append(f"R4 provenance: call variable {v!r} is not mentioned in the brief (a greeting or tool must not assume it exists)")
    cal = cfg.get("calendar", {})
    for h in cal.get("holidays", []):
        if h not in dates and not ok_derived(h):
            E.append(f"R4 provenance: calendar.holidays has {h}, which the brief does not mention")
    for i, w in enumerate(cfg.get("clock", {}).get("windows", [])):
        for k in ("start", "end"):
            if w.get(k) and w[k] not in times and not ok_derived(w[k]) and not ok_derived(f"clock.windows[{i}].{k}={w[k]}"):
                E.append(f"R4 provenance: clock.windows[{i}].{k} = {w[k]} does not appear in the brief")
        for d in w.get("days", []):
            m = re.match(r"business_days_after:(\d+)", str(d))
            if m:
                num_ok(int(m.group(1)), f"clock.windows[{i}].days")
    tiers = (cfg.get("items") or {}).get("tiers") or {}
    for i, t in enumerate(tiers.get("list", [])):
        for k in ("min", "max"):
            if k in t and abs(t[k]) < 100000:
                num_ok(t[k], f"items.tiers.list[{i}].{k}")
        lim = t.get("limit")
        if isinstance(lim, dict) and "n" in lim:
            num_ok(lim["n"], f"items.tiers.list[{i}].limit.n")
        for j, st in enumerate(t.get("ladder", [])):
            m = re.match(r"business_days_after:(\d+)", str(st.get("date", "")))
            if m:
                num_ok(int(m.group(1)), f"items.tiers.list[{i}].ladder[{j}].date")
        for k, v in t.items():
            if k not in ("min", "max", "limit", "ladder", "name", "values") and isinstance(v, (int, float)):
                num_ok(v, f"items.tiers.list[{i}].{k}")
    for name, n in cfg.get("flow", {}).get("nodes", {}).items():
        os_ = n.get("offer_state")
        if os_ is not None and not os_.get("hardship_triggers"):
            E.append(f"R4 provenance: flow.nodes.{name}.offer_state.hardship_triggers is missing (quote the brief's hardship list)")
        elif os_ and not quote_in(norm(os_["hardship_triggers"]), ntext) and not ok_derived(os_["hardship_triggers"]):
            E.append(f"R4 provenance: offer_state.hardship_triggers \"{os_['hardship_triggers'][:60]}\" is not quoted from the brief")
        if n.get("verify", {}).get("max_wrong") is not None:
            num_ok(n["verify"]["max_wrong"], f"flow.nodes.{name}.verify.max_wrong")
    # quoted sentences (three words or more) in any text must come from the brief
    for p, v in walk(cfg):
        if not isinstance(v, str) or p.startswith(".provenance"):
            continue
        for q in re.findall(r'"([^"\n]{3,240})"', v):
            nq = norm(q)
            if len(nq.split()) < 3 or nq.count("VAR") == len(nq.split()):
                continue
            if quote_in(nq, ntext) or ok_derived(q):
                continue
            E.append(f"R4 provenance: quoted text \"{q[:80]}\" at {p} is not in the brief (quote only the brief, or add it to provenance.derived with why)")


def quote_in(nq, ntext):
    if nq in ntext:
        return True
    parts = [x.strip() for x in nq.split("VAR") if x.strip()]
    if not parts:
        return True
    pos = 0
    for x in parts:
        i = ntext.find(x, pos)
        if i < 0:
            return False
        pos = i + len(x)
    return True


# --------------------------------------------------------------------------------------------------- rule 5

def rule_spoken(wf, cfg, E):
    words = [w.lower() for w in cfg.get("forbidden_before_verification", [])]
    if not words:
        return
    N = cfg.get("flow", {}).get("nodes", {})
    passes = set()
    for name, n in N.items():
        if n.get("verify"):
            passes.add((name, n["verify"]["on_pass"]))
    start = cfg["flow"]["start"]
    seen, todo = set(), [start]
    hints = set()
    while todo:
        x = todo.pop()
        if x in seen:
            continue
        if x.startswith("end:"):
            hints.add(x[4:])
            continue
        if x not in N:
            continue
        seen.add(x)
        n = N[x]
        tg = [r["to"] for r in n.get("routes", [])] + [n.get(k) for k in ("next", "fail", "overflow") if n.get(k)]
        if n.get("verify"):
            tg.append(n["verify"]["on_fail"])
        todo += tg
    lines = []
    for x in seen:
        e = N[x].get("enter") or {}
        if e.get("tts"):
            lines.append((f"node {x} first line", e["tts"]))
    cl = cfg.get("closing", {}).get("lines", {})
    for h in hints:
        lines.append((f"closing line for end:{h}", cl.get(h, cl.get("default", ""))))
    for where, text in lines:
        for w in words:
            if re.search(r"\b" + re.escape(w) + r"\b", text.lower()):
                E.append(f"R5 spoken: {where} says {w!r} before identity is verified: {text[:100]!r}")


# --------------------------------------------------------------------------------------------------- main

def run_checks(wf, api, cfg=None, bundle=None, quick=False):
    E = []
    if "paths" not in api:
        return ["R1 openapi: the tool API file has no 'paths'"]
    produced = static_produced(wf, cfg)
    rule_openapi(wf, api, cfg, E)
    rule_code(wf, api, cfg, produced, E, quick=quick)
    rule_graph(wf, cfg, produced, E)
    if cfg is not None and bundle is not None:
        rule_provenance(cfg, bundle, E)
    if cfg is not None:
        rule_spoken(wf, cfg, E)
    return E


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workflow"); ap.add_argument("openapi")
    ap.add_argument("--config"); ap.add_argument("--bundle"); ap.add_argument("--json", action="store_true"); ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    wf = json.load(open(a.workflow))
    wf = wf.get("workflow", wf)
    api = json.load(open(a.openapi))
    cfg = json.load(open(a.config)) if a.config else None
    bundle = open(a.bundle, encoding="utf-8", errors="replace").read() if a.bundle else None
    E = run_checks(wf, api, cfg, bundle, quick=a.quick)
    if a.json:
        print(json.dumps({"ok": not E, "errors": E}, indent=1))
    else:
        for e in E:
            print(e)
        print(f"check.py: {'OK' if not E else str(len(E)) + ' error(s)'}")
    sys.exit(1 if E else 0)


if __name__ == "__main__":
    main()
