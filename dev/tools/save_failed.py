"""Save the full transcript of every FAILED case of a run_dev result file.
    python3 dev/tools/save_failed.py <run-name> <result.json> [...]"""
import json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import freya
run = sys.argv[1]
out = ROOT / "dev" / "results" / "transcripts"; out.mkdir(parents=True, exist_ok=True)
n = 0
for f in sys.argv[2:]:
    d = json.load(open(f))
    for rows in d.get("rows", []):
        for r in rows:
            if r["pass"] or not r.get("call_id"):
                continue
            c = freya.get_call(r["call_id"])
            lines = [f"case {r['id']}  call {r['call_id']}  now {r.get('now')}  ended {c.get('endedReason')}", "FAILED: " + " || ".join(r["failed"]), ""]
            for m in c.get("messages", []):
                role = m.get("role")
                if role in ("user", "assistant"):
                    lines.append(f"[{m.get('nodeId')}] {role.upper()}: {m.get('message')}")
                elif role == "system":
                    try:
                        e = json.loads(m["message"])
                    except Exception:
                        continue
                    ev = e.get("event")
                    if ev == "node_enter":
                        lines.append(f"   -> node {e.get('node')}  (t={m.get('secondsFromStart', 0):.1f}s)")
                    elif ev == "function_call_start" and e.get("function") != "code_exec":
                        lines.append(f"   CALL {e.get('function')} {json.dumps((e.get('args') or {}).get('body', e.get('args')))[:400]}")
                    elif ev == "function_call_complete" and e.get("function") != "code_exec":
                        lines.append(f"   RESULT {json.dumps((e.get('result') or {}).get('data', e.get('result')))[:400]}")
                    elif ev in ("error",):
                        lines.append(f"   ERROR {e.get('message')}")
                    elif ev == "variable_extracted":
                        lines.append(f"   extracted {e.get('name')}")
            (out / f"{run}-{r['id']}.txt").write_text("\n".join(lines))
            n += 1
print(f"saved {n} transcripts to {out.relative_to(ROOT)}")
