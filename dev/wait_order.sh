#!/usr/bin/env bash
# Block until ops/ARCHITECT_ORDERS.md changes (or 25 minutes pass). Prints the file when it changes.
f="$(dirname "$0")/../ops/ARCHITECT_ORDERS.md"
start=$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f")
for i in $(seq 1 100); do
  sleep 15
  now=$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f")
  if [ "$now" != "$start" ]; then echo "ORDERS CHANGED"; cat "$f"; exit 0; fi
done
echo "NO NEW ORDERS (25 min). Log a heartbeat entry and wait again."
