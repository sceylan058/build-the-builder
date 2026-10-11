# Worker <-> architect file protocol

- ops/ARCHITECT_ORDERS.md : architect -> worker. Read-only for the worker.
- ops/WORKER_LOG.md       : worker -> architect. Append-only for the worker.

Worker rules:
1. After EVERY step (each commit, each finished test run, each build), append an entry to ops/WORKER_LOG.md:
   `## <HH:MM Istanbul> <step>` then: what you did, result numbers, commit hash, what is next, blockers. Keep it short. Then commit and push (ops/ files included).
2. After every log entry, read ops/ARCHITECT_ORDERS.md. If it contains an order number higher than the last one you acknowledged: write `ACK ORDER n` in the log and execute it (orders override your plan).
3. Never end your turn. When you have nothing left to do, run `bash dev/wait_order.sh` (blocks until ops/ARCHITECT_ORDERS.md changes, max 25 min) and loop: log, read orders, act. Keep looping until an order says STOP.
4. During a long test run, check the orders file between runs (not during one).
5. Failed-case transcripts go to dev/results/transcripts/<run>-<case>.txt after every gate run (the architect cannot reach Freya).
6. Messages typed directly by the human (Selim) in your terminal outrank the orders file.
