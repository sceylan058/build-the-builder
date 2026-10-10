"""Talk to a saved workflow turn by turn against a fresh practice session, then print the bank ledger.

    python3 tools/chat.py <workflow_id> <case_id> "first message" "second message" ...
"""
import json, os, sys, time, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
import freya
from score import http

def main():
    wid, case, msgs = sys.argv[1], sys.argv[2], sys.argv[3:]
    v = http("/v1/practice/sessions", {"case": case})["variables"]
    call_id = None
    for m in msgs:
        body = {"workflowId": wid, "message": m, "customerVariables": v}
        if call_id: body["callId"] = call_id
        try: r = freya.api("POST", "/api/v2/chat/message", body)
        except RuntimeError as e: print("ERR", str(e)[:400]); break
        call_id = r.get("callId") or call_id
        print("USER :", m); print("AGENT:", r.get("response")); print()
    if call_id:
        try: freya.api("POST", "/api/v2/chat/end", {"callId": call_id})
        except RuntimeError as e: print("end ERR", str(e)[:200])
    time.sleep(4)
    led = http("/v1/practice/ledger/" + v["customer_id"])
    print("OUTCOME", led.get("outcome"), led.get("reason"))
    for c in led["calls"]: print(" ", c["tool"], json.dumps(c["args"])[:1500], "->", json.dumps(c["result"])[:200])
    print("call_id", call_id)

if __name__ == "__main__": main()
