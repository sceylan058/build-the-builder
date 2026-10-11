#!/usr/bin/env bash
# C8 gate: plain + style runs, one simulation at a time; each line: suite, result, median/worst slowest turn.
cd "$(dirname "$0")/../.." && source env.sh
A=292ae78f-f433-422d-be01-9f51c98a6705; B=71c4002e-5545-4d8d-8426-0e7b7cfe86ca; RAW=e25a7405-6eb3-4a76-95e9-88d24ab06e16
out=dev/results/gate_c8.md
line() { echo "$1" >> $out; echo "$1"; }
summ() { f=$1; r=$(grep -E "passed \(" $f | tail -1 | grep -oE "^[0-9]+ / [0-9]+"); t=$(grep -oE "median [0-9]+ s, worst [0-9]+ s|median slowest turn [0-9]+s, worst [0-9]+s" $f | tail -1); fl=$(grep -E "^FAIL" $f | awk '{print $2}' | sort -u | tr '\n' ' '); echo "$r | $t | $fl"; }
run_kit() { python3 dev/tools/sim.py $1 --brief $2 ${3:+--style $3} --out results/gate-$4.json > results/gate-$4.log 2>&1; line "| $4 | $(summ results/gate-$4.log) |"; }
run_dev() { python3 dev/run_dev.py $1 $2 ${3:+--only $3} --out dev/results/gate-$4.json > dev/results/gate-$4.log 2>&1; line "| $4 | $(summ dev/results/gate-$4.log) |"; }
line "| suite | passed | slowest turn | failed |"; line "|---|---|---|---|"
run_kit $A A "" plain-A
run_kit $B B "" plain-B
run_dev $A dev/cases/ab_extended.json X01,X02,X03,X04,X05,X06,X07,X09,X10,X11,X12,X13,X14,X15,X16,X17,X18,X19,X20 abx-A
run_dev $B dev/cases/ab_extended.json X08,X21,X22,X23,X24 abx-B
run_dev $RAW dev/cases/v_raw.json "" v_raw
for st in pieces corrects talkative asks_back in_words; do run_kit $A A $st style-A-$st; done
for st in pieces corrects talkative; do run_kit $B B $st style-B-$st; done
git add dev/results/gate_c8.md dev/results/gate-*.log 2>/dev/null; git commit -qm "C8 gate results" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && git push -q && echo GATE-DONE
