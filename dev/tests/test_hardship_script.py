"""Scripted hardship step and the stage-based safety-net hint.   python3 -m unittest dev/tests/test_hardship_script.py"""
import copy, json, pathlib, sys, textwrap, unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "builder" / "skill")); sys.path.insert(0, str(ROOT / "builder"))
import gen, check  # noqa: E402

API = json.load(open(ROOT / "tools/openapi.json"))
BASE = json.load(open(ROOT / "dev/out/brief-b.config.json")); BASE["openapi"] = str(ROOT / "tools/openapi.json")


def build(script):
    c = copy.deepcopy(BASE)
    c["flow"]["nodes"]["negotiate"]["offer_state"]["hardship_script"] = script
    return c, gen.Gen(c, API).build()


class Scripted(unittest.TestCase):
    def test_nodes_and_routes(self):
        c, w = build({"say": "Fixed line. Do you want the team?", "accept_queue": "support", "decline_to": "negotiate", "volunteer_to": "negotiate"})
        h = w["nodes"]["negotiate_hardship"]
        self.assertEqual(h["on_enter"], {"type": "tts", "text": "Fixed line. Do you want the team?"}); self.assertEqual(h["tools"], [])
        routes = {t["condition"]["conditions"][0]["operand"]: t["target_node"] for t in h["transitions"] if t["condition"].get("conditions")}
        self.assertEqual(routes, {"accept": "negotiate_hs_transfer", "names_date_or_amount": "negotiate", "decline": "negotiate", "other": "negotiate"})
        self.assertEqual(h["transitions"][-1]["condition"], {"operator": "always"})
        body = w["nodes"]["negotiate_hs_transfer"]["pre_actions"][0]["function"]["parameters"]["properties"]["body"]["properties"]
        self.assertEqual(body["queue"]["default"], "support")
        self.assertEqual(check.run_checks(w, API, c, (ROOT / "briefs/brief-a.md").read_text() + (ROOT / "briefs/brief-b.md").read_text(), quick=True), [])

    def test_no_offer_means_no_accept_path(self):
        c, w = build({"say": "Sympathy only.", "accept_queue": "", "decline_to": "end:hardship", "volunteer_to": "negotiate"})
        self.assertNotIn("negotiate_hs_transfer", w["nodes"])
        kinds = [t["condition"]["conditions"][0]["operand"] for t in w["nodes"]["negotiate_hardship"]["transitions"] if t["condition"].get("conditions")]
        self.assertNotIn("accept", kinds)

    def test_unknown_queue_is_caught(self):
        c, w = build({"say": "x.", "accept_queue": "vip", "decline_to": "negotiate", "volunteer_to": "negotiate"})
        E = check.run_checks(w, API, c, "", quick=True)
        self.assertTrue(any("'vip'" in e for e in E), E[:3])

    def test_mark_sets_ledger_and_queue(self):
        c, w = build({"say": "x.", "accept_queue": "support", "decline_to": "negotiate", "volunteer_to": "negotiate"})
        code = w["nodes"]["negotiate_hs_mark"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]
        v = {}; g = {}
        exec("def __run(vars):\n" + textwrap.indent(code, "    ") + "\n", g); g["__run"](v)
        self.assertEqual(json.loads(v["ledger_json"])["flags"]["transfer"], "support"); self.assertEqual(v["transfer_queue"], "support")


class SafetyStage(unittest.TestCase):
    def hook(self, v):
        c, w = build({"say": "x.", "accept_queue": "support", "decline_to": "negotiate", "volunteer_to": "negotiate"})
        t = w["tools"][0]; cfg = {"url": "u", "body": {"customer_id": "c", "outcome": "pending"}}
        g = {}; exec("def __run(vars, config):\n" + textwrap.indent(t["pre_process_code"], "    ") + "\n", g); g["__run"](dict({"now": "2026-10-14T11:00", "item_ids": "[]"}, **v), cfg)
        return cfg["body"].get("outcome"), cfg["body"].get("reason")

    def test_stage_outcomes(self):
        self.assertEqual(self.hook({"opening.total_turns": "1"}), ("not_reached", "unclear"))
        self.assertEqual(self.hook({"opening.total_turns": "1", "identity.total_turns": "1"}), ("not_verified", "declined"))
        self.assertEqual(self.hook({"opening.total_turns": "1", "identity.total_turns": "2", "id_state": "verified", "negotiate.total_turns": "1"})[0], "no_promise")


if __name__ == "__main__":
    unittest.main()
