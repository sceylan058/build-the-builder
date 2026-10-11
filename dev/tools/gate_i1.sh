#!/usr/bin/env bash
# improve-1 gate, reps 1, priority order; every finished suite is committed to the branch.
cd "$(dirname "$0")/../.." && source env.sh
A=292ae78f-f433-422d-be01-9f51c98a6705; B=71c4002e-5545-4d8d-8426-0e7b7cfe86ca; CLEAN=9bccc985-dd48-4b90-997f-9b91353a1b29; RAW=e25a7405-6eb3-4a76-95e9-88d24ab06e16
out=dev/results/gate_improve1.md
ABXA=X01,X02,X03,X04,X05,X06,X07,X09,X10,X11,X12,X13,X14,X15,X16,X17,X18,X19,X20; ABXB=X08,X21,X22,X23,X24
summ() { f=$1; r=$(grep -E "passed \(" $f | tail -1 | grep -oE "^[0-9]+ / [0-9]+"); t=$(grep -oE "median slowest turn [0-9]+s, worst [0-9]+s" $f | tail -1); fl=$(grep -E "^FAIL" $f | awk '{print $2}' | sort -u | tr '\n' ' '); echo "${r:-did not complete} | $t | $fl"; }
rd() { python3 dev/run_dev.py $1 $2 ${3:+--only $3} ${4:+--style $4} --out dev/results/i1-$5.json > dev/results/i1-$5.log 2>&1
  echo "| $5 | $(summ dev/results/i1-$5.log) |" >> $out
  python3 dev/tools/save_failed.py improve1 dev/results/i1-$5.json >/dev/null 2>&1
  git add dev/results >/dev/null 2>&1; git commit -qm "improve-1 gate: $5" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" >/dev/null 2>&1; }
echo "| suite | passed | slowest turn | failed |" > $out; echo "|---|---|---|---|" >> $out
rd $A dev/cases/pub_A.json "" "" plain-A
rd $B dev/cases/pub_B.json "" "" plain-B
rd $A dev/cases/ab_extended.json $ABXA "" abx-A
rd $B dev/cases/ab_extended.json $ABXB "" abx-B
rd $RAW dev/cases/v_raw.json "" "" v_raw
rd $A dev/cases/pub_A.json "" talkative style-A-talkative
rd $A dev/cases/pub_A.json "" corrects style-A-corrects
rd $CLEAN dev/cases/v_clean.json "" "" v_clean
echo I1-GATE-DONE
