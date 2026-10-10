#!/usr/bin/env bash
# One style: A (practice-a) then B (practice-b), reps 3, via the safe wrapper; append to dev/results/styles.md and commit.
st=$1; cd "$(dirname "$0")/../.." && source env.sh
for pair in "A 292ae78f-f433-422d-be01-9f51c98a6705" "B 71c4002e-5545-4d8d-8426-0e7b7cfe86ca"; do
  set -- $pair; b=$1; agent=$2
  python3 dev/tools/sim.py $agent --brief $b --reps 3 --style $st --rerun-if-slow 1 --out results/style-$b-$st.json > results/style-$b-$st.log 2>&1
  python3 - "$st" "$b" <<'PY'
import json, sys, re
st, b = sys.argv[1], sys.argv[2]
log = open(f"results/style-{b}-{st}.log").read()
try:
    d = json.load(open(f"results/style-{b}-{st}.json"))
    fails = [f for f in d["final"] if not f["pass"]]
    reasons = {}
    for rows in d.get("all_rows", []):
        for r in rows:
            if not r["pass"] and r["id"] not in reasons:
                reasons[r["id"]] = (r["failed"][0] if r["failed"] else "")[:160].replace("\n", " ")
    med = re.findall(r"median (\d+) s", log)
    line = f"| {st} | {b} | {d['passed']}/{d['total']} | " + "; ".join(f"{f['id']} ({f['passes']}/3): {reasons.get(f['id'], '')}" for f in fails) + f" | {med[-1] if med else '?'} s |"
except Exception as ex:
    line = f"| {st} | {b} | run did not complete ({ex}); log tail: {log.strip().splitlines()[-1][:120] if log.strip() else 'empty'} | | |"
open("dev/results/styles.md", "a").write(line + "\n")
print(line)
PY
done
git add dev/results/styles.md && git commit -qm "styles: $st" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && echo "committed $st"
