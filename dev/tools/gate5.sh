#!/usr/bin/env bash
cd "$(dirname "$0")/../.." && source env.sh
out=dev/results/gate_c8_run5.md; echo "| suite | result |" > $out; echo "|---|---|" >> $out
python3 dev/run_dev.py 9bccc985-dd48-4b90-997f-9b91353a1b29 dev/cases/v_clean.json --only VC-01,VC-03,VC-08,VC-12,VC-13,VC-17 --out dev/results/g5-vclean.json > dev/results/g5-vclean.log 2>&1
echo "| v_clean (6 failing) | $(grep -E 'passed \(' dev/results/g5-vclean.log | cut -c1-60) $(grep -E '^FAIL' dev/results/g5-vclean.log | awk '{print $2}' | tr '\n' ' ') |" >> $out
python3 dev/run_dev.py e25a7405-6eb3-4a76-95e9-88d24ab06e16 dev/cases/v_raw.json --only VR-01,VR-10 --out dev/results/g5-vraw.json > dev/results/g5-vraw.log 2>&1
echo "| v_raw VR-01,VR-10 | $(grep -E 'passed \(' dev/results/g5-vraw.log | cut -c1-60) $(grep -E '^FAIL' dev/results/g5-vraw.log | awk '{print $2}' | tr '\n' ' ') |" >> $out
python3 dev/run_dev.py 292ae78f-f433-422d-be01-9f51c98a6705 dev/cases/pub_A.json --only PUB-05 --out dev/results/g5-pub05.json > dev/results/g5-pub05.log 2>&1
echo "| plain-A PUB-05 | $(grep -E 'passed \(' dev/results/g5-pub05.log | cut -c1-60) $(grep -E '^FAIL' dev/results/g5-pub05.log | awk '{print $2}' | tr '\n' ' ') |" >> $out
python3 dev/tools/save_failed.py gate5 dev/results/g5-*.json; git add dev/results; git commit -qm "gate run 5 (targeted re-run)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"; git push -q; echo GATE5-DONE
