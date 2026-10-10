"""Print a call's dialogue and tool calls: python3 tools/transcript.py <results.json> <case_id>  (or a call id)"""
import json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import freya
a = sys.argv[1]
if a.endswith(".json"):
    rows = json.load(open(a))["rows"]; cid = [r for r in rows if r["id"] == sys.argv[2]][0]["call_id"]
else: cid = a
c = freya.get_call(cid)
for m in c["messages"]:
    r = m.get("role")
    if r in ("user", "assistant"): print(f"[{m.get('nodeId')}] {r.upper()}: {m.get('message')}")
    elif r == "system":
        try: e = json.loads(m["message"])
        except Exception: continue
        ev = e.get("event")
        if ev == "function_call_start" and e.get("function") != "code_exec": print("   CALL", e.get("function"), json.dumps(e.get("args"))[:300])
        elif ev == "function_call_complete" and e.get("function") != "code_exec": print("   RES ", json.dumps(e.get("result"))[:300])
        elif ev == "node_enter": print("   -> node", e.get("node"))
    elif r in ("tool_calls", "tool_call_result", "function"): print("  ", r, json.dumps(m)[:300])
print("endedReason", c.get("endedReason"))
