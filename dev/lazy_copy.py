"""Lazy-copy detector: compare a rehearsal config with the variant's true parameters and with the example config.
    python3 dev/lazy_copy.py <config.json> <variant: clean|raw>"""
import json, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
cfg = json.load(open(sys.argv[1])); var = sys.argv[2]
ex = json.load(open(ROOT / "builder/skill/example.config.json"))
TRUTH = {
 "clean": {"holidays": ["2026-10-16", "2026-11-11", "2026-12-24", "2026-12-25", "2027-01-01"], "tiers": [(1, 10, 10, 1), (11, 45, 5, 2)],
           "attempt1": "business_days_after:3", "callback": ("09:00", "17:00"), "first_question": "phone_last4", "max_wrong": 2,
           "floor_car": "half", "after_promise": "A confirmation will be sent to you by text message.", "note_order": "last",
           "name_question": "{{first_name}} {{last_name}}"},
 "raw": {"holidays": ["2026-10-26", "2026-11-26", "2026-12-25", "2027-01-01"], "tiers_before": [(1, 7, 10, 1), (8, 45, 7, 2)], "tiers_after": [(1, 5, 10, 1), (6, 45, 7, 2)],
         "attempt1": "last_business_day_of_week", "callback": ("10:00", "19:00"), "banned": "debt",
         "labels": {"credit_card": "Visa card ending {card_last4}", "personal_loan": "personal finance loan", "car_loan": "vehicle finance agreement"}},
}[var]
rows = []
def row(name, want, got, exv):
    rows.append((name, "OK" if want == got else ("COPIED FROM EXAMPLE" if got == exv and got != want else "WRONG"), want, got))
tiers = lambda c: [(t["min"], t["max"], t["limit"].get("n"), len(t.get("ladder", []))) for t in c["items"]["tiers"]["list"]]
row("holidays", sorted(TRUTH["holidays"]), sorted(cfg["calendar"]["holidays"]), sorted(ex["calendar"]["holidays"]))
if var == "clean":
    row("tiers", TRUTH["tiers"], tiers(cfg), tiers(ex))
    a1 = sorted({st.get("date") for t in cfg["items"]["tiers"]["list"] for st in t.get("ladder", [])[:1]})
    row("attempt-1 date rule", [TRUTH["attempt1"]], a1, sorted({st.get("date") for t in ex["items"]["tiers"]["list"] for st in t.get("ladder", [])[:1]}))
    w = cfg["clock"]["windows"][0]; row("callback window", TRUTH["callback"], (w["start"], w["end"]), (ex["clock"]["windows"][0]["start"], ex["clock"]["windows"][0]["end"]))
    v = next(n["verify"] for n in cfg["flow"]["nodes"].values() if n.get("verify"))
    row("first identity question", TRUTH["first_question"], v["questions"][0]["field"], "date_of_birth")
    row("wrong answers that end the check", TRUTH["max_wrong"], v.get("max_wrong", "API counter (3)"), "API counter (3)")
    row("car loan floor is half the past due", True, "0.5" in json.dumps(cfg["items"]["fields"]) or "/ 2" in json.dumps(cfg["items"]["fields"]), False)
    row("sentence after a promise", TRUTH["after_promise"], (cfg["closing"].get("after_records") or {}).get("prefix"), (ex["closing"].get("after_records") or {}).get("prefix"))
    fn = next((r["from_note"] for r in cfg["outcomes"]["rules"] if "from_note" in r), {})
    row("close reason from LAST non-paid note", "last", fn.get("order", "first (schema cannot say last)"), "first (schema cannot say last)")
    row("name question uses first and last name", True, "{{first_name}} {{last_name}}" in cfg["flow"]["nodes"][cfg["flow"]["start"]].get("enter", {}).get("tts", ""), False)
else:
    row("tiers (one set; the brief has two by date)", "two sets switching on 2026-10-19", tiers(cfg), tiers(ex))
    w = cfg["clock"]["windows"][0]; row("callback window", TRUTH["callback"], (w["start"], w["end"]), (ex["clock"]["windows"][0]["start"], ex["clock"]["windows"][0]["end"]))
    row("spoken product names", TRUTH["labels"], cfg["items"]["label"]["templates"], ex["items"]["label"]["templates"])
    row("'debt' banned in every spoken text", True, "debt" not in json.dumps({k: v for k, v in cfg.items() if k not in ("forbidden_before_verification", "provenance")}).lower().replace("never say \"debt\"", ""), False)
    row("'debt' in forbidden words", True, "debt" in cfg.get("forbidden_before_verification", []), "debt" in ex.get("forbidden_before_verification", []))
for r in rows:
    print(f"{r[1]:<22} {r[0]:<40} want={str(r[2])[:70]} got={str(r[3])[:70]}")
print(f"{sum(r[1] == 'OK' for r in rows)}/{len(rows)} OK, {sum(r[1] == 'COPIED FROM EXAMPLE' for r in rows)} copied from the example")
