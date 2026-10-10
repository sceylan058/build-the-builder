#!/usr/bin/env bash
# Wait (foreground) for a process, at most $2 seconds (default 540). Prints the tail of $3 when given.
pid=$1; max=${2:-540}; log=$3; t=0
while kill -0 "$pid" 2>/dev/null && [ $t -lt $max ]; do sleep 15; t=$((t+15)); done
if kill -0 "$pid" 2>/dev/null; then echo "STILL RUNNING after ${t}s (pid $pid)"; else echo "FINISHED (pid $pid) after ~${t}s"; fi
[ -n "$log" ] && tail -25 "$log" | cut -c1-260
