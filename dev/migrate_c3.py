"""Mechanical migration for the improve-1 gate: add offer_state.hardship_script to the model-written configs (cfg2-*) so the
scripted hardship step is exercised on the SAME configs as the freeze gate. The sentence is ours, not the model's; a fresh build
makes the model write it from the brief (SKILL.md).   python3 dev/migrate_c3.py"""
import json, pathlib
R = pathlib.Path(__file__).resolve().parents[1] / "results"
SAY_SUPPORT = "I am very sorry to hear that. Would you like me to connect you with our customer support team?"
SAY_PLAIN = "I am very sorry to hear that."
for slot, support in (("practice-a", True), ("practice-b", True), ("dev-clean", False), ("dev-raw", True)):
    c = json.load(open(R / f"cfg2-{slot}.json"))
    neg = c["flow"]["nodes"]["negotiate"]
    ends = [r["to"] for r in neg.get("routes", [])]
    neg["offer_state"]["hardship_script"] = {
        "say": SAY_SUPPORT if support else SAY_PLAIN,
        "accept_queue": "support" if support else "",
        "decline_to": "end:hardship" if "end:hardship" in ends else "negotiate",
        "volunteer_to": "negotiate"}
    if not support:
        neg["offer_state"]["hardship_offer"] = ""
    json.dump(c, open(R / f"cfg3-{slot}.json", "w"), indent=1)
    print(slot, neg["offer_state"]["hardship_script"])
