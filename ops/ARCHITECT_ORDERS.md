# Architect orders

Written ONLY by the architect. The worker never edits this file (it may commit it as-is).
Each order has a number. Execute orders in number order. Acknowledge each in ops/WORKER_LOG.md before starting it.
An order overrides your current plan unless it says otherwise.

## ORDER 1 (11:00 Istanbul)
Acknowledge the file protocol (see ops/PROTOCOL.md). Then, in ops/WORKER_LOG.md, report:
- which items of the 10:42 audit (X20 injection, VR-12 missing close_call, hardship route, latency, X10/PUB-06, transcripts to dev/results/transcripts/) are done, in progress, or not started;
- what is running right now and its ETA.
Then continue with the audit items in that priority order.
