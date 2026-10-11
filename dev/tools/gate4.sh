#!/usr/bin/env bash
cd "$(dirname "$0")/../.." && source env.sh
A=292ae78f-f433-422d-be01-9f51c98a6705; RAW=e25a7405-6eb3-4a76-95e9-88d24ab06e16; CLEAN=9bccc985-dd48-4b90-997f-9b91353a1b29
out=dev/results/gate_c8_run4.md
line() { echo "$1" >> $out; git add $out >/dev/null 2>&1; git commit -qm "gate run 4: $2" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" >/dev/null 2>&1 && git push -q >/dev/null 2>&1; }
summ() { f=$1; r=$(grep -E "passed \(" $f | tail -1 | grep -oE "^[0-9]+ / [0-9]+"); t=$(grep -oE "median slowest turn [0-9]+s, worst [0-9]+s" $f | tail -1); fl=$(grep -E "^FAIL" $f | awk '{print $2}' | sort | uniq -c | awk '{print $2"x"$1}' | tr '\n' ' '); echo "${r:-did not complete} | $t | $fl"; }
rd() { python3 dev/run_dev.py $1 $2 $3 --out dev/results/g4-$4.json > dev/results/g4-$4.log 2>&1; line "| $4 | $(summ dev/results/g4-$4.log) |" "$4"; }
echo "| suite | passed | slowest turn | failed |" > $out; echo "|---|---|---|---|" >> $out
rd $A dev/cases/ab_extended.json "--only X01,X02,X03,X04,X05,X06,X07,X09,X10,X11,X12,X13,X14,X15,X16,X17,X18,X19,X20" abx-A
rd $RAW dev/cases/v_raw.json "" v_raw
rd $A dev/cases/pub_A.json "" plain-A
rd $A dev/cases/ab_extended.json "--only X03 --reps 3" x03-rep3
rd $CLEAN dev/cases/v_clean.json "" v_clean
python3 dev/tools/save_failed.py gate4 dev/results/g4-*.json; git add dev/results; git commit -qm "gate run 4 transcripts" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"; git push -q; echo GATE4-DONE
