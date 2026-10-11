#!/usr/bin/env bash
cd "$(dirname "$0")/../.." && source env.sh
A=292ae78f-f433-422d-be01-9f51c98a6705; B=71c4002e-5545-4d8d-8426-0e7b7cfe86ca; RAW=e25a7405-6eb3-4a76-95e9-88d24ab06e16
out=dev/results/gate_c8_run3.md
line() { echo "$1" >> $out; echo "$1"; git add $out >/dev/null 2>&1; git commit -qm "gate run 3: $2" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" >/dev/null 2>&1 && git push -q >/dev/null 2>&1; }
summ() { f=$1; r=$(grep -E "passed \(" $f | tail -1 | grep -oE "^[0-9]+ / [0-9]+"); t=$(grep -oE "median slowest turn [0-9]+s, worst [0-9]+s" $f | tail -1); fl=$(grep -E "^FAIL" $f | awk '{print $2}' | sort -u | tr '\n' ' '); echo "${r:-did not complete} | $t | $fl"; }
rd() { python3 dev/run_dev.py $1 $2 ${3:+--only $3} ${4:+--style $4} --out dev/results/g3-$5.json > dev/results/g3-$5.log 2>&1; line "| $5 | $(summ dev/results/g3-$5.log) |" "$5"; }
echo "| suite | passed | slowest turn | failed |" > $out; echo "|---|---|---|---|" >> $out
rd $A dev/cases/pub_A.json "" "" plain-A
rd $B dev/cases/pub_B.json "" "" plain-B
rd $A dev/cases/ab_extended.json X01,X02,X03,X04,X05,X06,X07,X09,X10,X11,X12,X13,X14,X15,X16,X17,X18,X19,X20 "" abx-A
rd $B dev/cases/ab_extended.json X08,X21,X22,X23,X24 "" abx-B
rd $RAW dev/cases/v_raw.json "" "" v_raw
for st in pieces corrects talkative; do rd $A dev/cases/pub_A.json "" $st style-A-$st; done
python3 dev/run_dev.py $A dev/cases/ab_extended.json --only X20 --reps 3 --out dev/results/g3-x20-rep.json > dev/results/g3-x20-rep.log 2>&1; line "| x20-rep (reps 3) | $(summ dev/results/g3-x20-rep.log) |" x20
python3 dev/tools/save_failed.py gate3 dev/results/g3-*.json; git add dev/results; git commit -qm "gate run 3 transcripts" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"; git push -q; echo GATE3-DONE
