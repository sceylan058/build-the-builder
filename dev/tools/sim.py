"""Run tools/run_cases.py safely: refuse to start while a simulation is active, enforce a hard wall-clock timeout,
and close our simulation if the run is killed.

    python3 dev/tools/sim.py <agent_id> --brief A [--out results/x.json] [--minutes-per-10 20] [run_cases args...]

Exit codes: 0 finished, 3 another simulation is active, 4 timed out (killed and closed), other = run_cases exit code.
"""
import datetime, json, pathlib, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import freya  # noqa: E402


def active(ws):
    try:
        r = freya.api("GET", "/api/v2/simulations", workspaceId=ws, status="running", limit=50)
        return r.get("simulations", [])
    except Exception as ex:
        print(f"sim.py: cannot list simulations ({str(ex)[:120]}); treating as busy", flush=True)
        return [{"id": "unknown"}]


def main():
    args = sys.argv[1:]
    mins = 20.0
    if "--minutes-per-10" in args:
        i = args.index("--minutes-per-10"); mins = float(args[i + 1]); del args[i:i + 2]
    agent = args[0]
    brief = args[args.index("--brief") + 1] if "--brief" in args else None
    cases = [c for c in json.load(open(ROOT / "public-test-set.json")) if not brief or c["brief"] == brief]
    if "--only" in args:
        only = args[args.index("--only") + 1].split(","); cases = [c for c in cases if c["id"] in only]
    reps = int(args[args.index("--reps") + 1]) if "--reps" in args else 1
    limit = max(8.0, mins * len(cases) / 10.0) * 60 * reps
    ws = freya.workspace_id()
    busy = active(ws)
    if busy:
        print(f"sim.py: {len(busy)} simulation(s) still running ({[s['id'] for s in busy]}); not starting", flush=True)
        sys.exit(3)
    start = datetime.datetime.now(datetime.timezone.utc)
    print(f"sim.py: starting {len(cases)} case(s) x {reps}, hard timeout {limit / 60:.0f} min, at {start.isoformat(timespec='seconds')}", flush=True)
    p = subprocess.Popen([sys.executable, str(ROOT / "tools" / "run_cases.py")] + args, cwd=ROOT)
    try:
        rc = p.wait(timeout=limit)
        print(f"sim.py: run_cases exit {rc} after {(datetime.datetime.now(datetime.timezone.utc) - start).total_seconds():.0f}s", flush=True)
        sys.exit(rc)
    except subprocess.TimeoutExpired:
        p.kill()
        print(f"sim.py: TIMEOUT after {limit / 60:.0f} min; killed run_cases", flush=True)
        for s in active(ws):
            try:
                c = datetime.datetime.fromisoformat(s["createdAt"].replace("Z", "+00:00"))
            except Exception:
                continue
            if s.get("agentId") == agent and c >= start - datetime.timedelta(seconds=5):
                freya.api("PUT", f"/api/v2/simulations/{s['id']}", {"status": "completed"})
                print(f"sim.py: closed our simulation {s['id']} (documented PUT status=completed)", flush=True)
        sys.exit(4)


if __name__ == "__main__":
    main()
