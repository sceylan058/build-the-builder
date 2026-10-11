"""Run our own case files on borrowed practice sessions.

    python3 dev/run_dev.py <agent_id> <cases.json> [--reps N] [--style S] [--only IDS] [--out PATH] [--concurrency 5]

A case borrows a practice customer (`session_case`: identity, products, faults) and brings its own script, `now` and expected
ledger. Scoring = the kit's score_ledger() + the judge, exactly as tools/run_cases.py.
"""
import argparse, datetime, hashlib, json, pathlib, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
import freya  # noqa: E402
from score import http, score_ledger  # noqa: E402
from run_cases import persona_for, STYLES  # noqa: E402

STORE = ROOT / ".personas-dev.json"


def load(path, pub):
    cases = json.load(open(path))
    for c in cases:
        b = pub[c["session_case"]]
        c["variables"] = dict(b["variables"])
        if c.get("now"):
            c["variables"]["now"] = c["now"]
        c["identity"] = b["identity"]
        c["products"] = b["products"]
        c.setdefault("checks", [])
    return cases


def transient(ex):
    s = str(ex)
    return any(k in s for k in ("-> 5", "-> 429", "timed out", "Timeout", "Connection", "URLError", "reset by peer"))


def call(fn, what, tries=6):
    for i in range(tries):
        try:
            return fn()
        except Exception as ex:
            if not transient(ex) or i == tries - 1:
                raise
            print(f"  {what}: transient error ({str(ex)[:90]}), retry {i + 1}", flush=True)
            time.sleep(min(15 * 2 ** i, 120))


def busy(ws):
    r = call(lambda: freya.api("GET", "/api/v2/simulations", workspaceId=ws, status="running", limit=20), "list simulations")
    return r.get("simulations", [])


def simulate(agent, name, var_map, concurrency, limit_s):
    ws = freya.workspace_id()
    t_wait = time.time()
    while busy(ws):
        if time.time() - t_wait > 600:
            sys.exit("run_dev: another simulation has been running for 10+ minutes; not starting")
        print("  another simulation is running; waiting 30 s", flush=True)
        time.sleep(30)
    body = {"agentId": agent, "name": name, "mode": "chat", "selectedPersonaIds": list(var_map), "customerVariablesMap": var_map,
            "maxConcurrentCalls": concurrency, "runsPerPersona": 1, "maxCallDurationSeconds": 420,
            "assistantLlmOverride": freya.AGENT_LLM, "routingLlmOverride": freya.AGENT_LLM, "extractionLlmOverride": freya.AGENT_LLM,
            "personaLlmOverride": freya.SIM_LLM, "analysisLlmOverride": freya.SIM_LLM}
    started = datetime.datetime.now(datetime.timezone.utc)
    try:
        sim = freya.api("POST", "/api/v2/simulations", body)
    except Exception as ex:
        # a create that timed out may still have started a simulation: adopt it instead of starting a second one
        if not transient(ex):
            raise
        time.sleep(20)
        mine = [s for s in busy(ws) if s.get("agentId") == agent and s.get("name") == name]
        if not mine:
            sim = call(lambda: freya.api("POST", "/api/v2/simulations", body), "create simulation")
        else:
            sim = {"simulation": mine[0]}
    sid = (sim.get("simulation") or sim)["id"]
    t0 = time.time()
    while True:
        time.sleep(10)
        try:
            s = freya.api("GET", f"/api/v2/simulations/{sid}"); s = s.get("simulation") or s
        except Exception as ex:
            if not transient(ex):
                raise
            continue
        if s.get("status") in ("completed", "failed", "paused"):
            break
        if time.time() - t0 > limit_s:
            call(lambda: freya.api("PUT", f"/api/v2/simulations/{sid}", {"status": "completed"}), "close simulation")
            print(f"  TIMEOUT after {limit_s / 60:.0f} min: closed simulation {sid}", flush=True)
            break
    its = call(lambda: freya.api("GET", f"/api/v2/simulations/{sid}/iterations"), "iterations")
    its = its.get("iterations") or its.get("items") or its
    return sid, its[0]["id"], s.get("status"), time.time() - t0


def slowest(call_id):
    try:
        c = freya.get_call(call_id)
    except Exception:
        return None, None
    last, worst = None, 0.0
    for m in c.get("messages", []):
        t = m.get("secondsFromStart")
        if t is None:
            continue
        if m.get("role") == "user":
            last = t
        elif last is not None:
            worst = max(worst, t - last)
            last = None if m.get("role") == "assistant" else last
    return worst, c.get("endedReason")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("agent_id"); ap.add_argument("cases")
    ap.add_argument("--reps", type=int, default=1); ap.add_argument("--style", choices=sorted(STYLES)); ap.add_argument("--only")
    ap.add_argument("--out"); ap.add_argument("--concurrency", type=int, default=5)
    a = ap.parse_args()
    pub = {c["id"]: c for c in json.load(open(ROOT / "public-test-set.json"))}
    cases = load(a.cases, pub)
    if a.only:
        keep = a.only.split(","); cases = [c for c in cases if c["id"] in keep]
    ident = {c["id"]: {"identity": c["identity"]} for c in cases}
    store = json.load(open(STORE)) if STORE.exists() else {}
    spec = {c["id"]: persona_for(c, ident[c["id"]], a.style) for c in cases}
    key = {i: i + ":" + hashlib.sha1(json.dumps(p, sort_keys=True).encode()).hexdigest()[:10] for i, p in spec.items()}
    new = [c for c in cases if key[c["id"]] not in store]
    if new:
        made = call(lambda: freya.create_personas([spec[c["id"]] for c in new]), "create personas")["personas"]
        store.update({key[c["id"]]: p["id"] for c, p in zip(new, made)}); json.dump(store, open(STORE, "w"), indent=1)
    pids = {c["id"]: store[key[c["id"]]] for c in cases}
    limit_s = max(20, 40 * len(cases) / 10) * 60   # judging can lag far behind the calls
    reps, waits = [], []
    for rep in range(a.reps):
        sessions = {}
        for c in cases:
            v = call(lambda: http("/v1/practice/sessions", {"case": c["session_case"]}), "session")["variables"]
            if c.get("now"):
                v["now"] = c["now"]
            sessions[c["id"]] = v
        sid, it_id, status, took = simulate(a.agent_id, f"dev {pathlib.Path(a.cases).stem} {time.strftime('%H:%M:%S')}",
                                            {pids[c["id"]]: sessions[c["id"]] for c in cases}, a.concurrency, limit_s)
        judge = {r["personaId"]: r for r in call(lambda: freya.get_iteration(sid, it_id), "iteration")["runs"]}
        rows = []
        for c in cases:
            led = call(lambda: http("/v1/practice/ledger/" + sessions[c["id"]]["customer_id"]), "ledger")
            r = score_ledger(c, led)
            j = judge.get(pids[c["id"]], {})
            if j.get("outcome") != "pass":
                r["failed"].append("conversation: " + " ".join(str(j.get("reason") or "no verdict").split())[:400])
            w, ended = slowest(j.get("callId")) if j.get("callId") else (None, None)
            if w is not None:
                waits.append(w)
            rows.append({"id": c["id"], "family": c["family"], "now": c["variables"]["now"], "pass": not r["failed"], "failed": r["failed"],
                         "call_id": j.get("callId"), "tools": [x["tool"] for x in led["calls"]], "ended": ended})
            print(("PASS" if not r["failed"] else "FAIL"), c["id"], f"{c['family']:<16}", c["variables"]["now"], "|",
                  " > ".join(x["tool"].replace("verify_identity", "verify").replace("create_promise", "promise") for x in led["calls"]) or "(no tool calls)",
                  "| call", j.get("callId"), flush=True)
            for f in r["failed"]:
                print("       -", f[:260], flush=True)
        reps.append(rows)
        print(f"-- rep {rep + 1}/{a.reps}: {sum(r['pass'] for r in rows)}/{len(rows)} passed, simulation {sid} {status}, {took:.0f}s\n", flush=True)
    final = []
    for k, c in enumerate(cases):
        final.append({"id": c["id"], "family": c["family"], "passes": sum(r[k]["pass"] for r in reps), "runs": a.reps,
                      "pass": all(r[k]["pass"] for r in reps), "reason": next((f for r in reps for f in r[k]["failed"]), "")})
    fam = {}
    for f in final:
        fam.setdefault(f["family"], [0, 0]); fam[f["family"]][0] += f["pass"]; fam[f["family"]][1] += 1
    print("per family:", ", ".join(f"{k} {v[0]}/{v[1]}" for k, v in sorted(fam.items())))
    waits.sort()
    med = waits[len(waits) // 2] if waits else 0
    n = sum(f["pass"] for f in final)
    print(f"{n} / {len(final)} passed (every rep must pass). median slowest turn {med:.0f}s, worst {(waits[-1] if waits else 0):.0f}s")
    (ROOT / "dev" / "results").mkdir(parents=True, exist_ok=True)
    with open(ROOT / "dev" / "results" / "log.jsonl", "a") as f:
        f.write(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "agent": a.agent_id, "cases": a.cases, "style": a.style, "reps": a.reps,
                            "passed": n, "total": len(final), "failed": [x["id"] for x in final if not x["pass"]], "median_slowest_s": round(med, 1)}) + "\n")
    if a.out:
        pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        json.dump({"final": final, "rows": reps}, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
