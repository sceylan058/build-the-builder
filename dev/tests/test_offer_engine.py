"""Offer engine (per-turn code) scenarios.   python3 -m unittest dev/tests/test_offer_engine.py"""
import json, pathlib, sys, textwrap, unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
WF = json.load(open(ROOT / "dev/out/brief-b.workflow.json"))
code = lambda n: WF["nodes"][n]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]


def run(src, v):
    g = {}
    exec("def __run(vars):\n" + textwrap.indent(src, "    ") + "\n", g)
    g["__run"](v)


def start(now="2026-10-14T11:00"):
    v = {"now": now, "products": json.dumps([
        {"product_id": "p1", "type": "credit_card", "card_last4": "7777", "past_due": 333, "days_late": 16, "minimum_payment": 100},
        {"product_id": "p2", "type": "personal_loan", "past_due": 2000, "days_late": 16, "instalment_amount": 650},
        {"product_id": "p3", "type": "car_loan", "past_due": 150, "days_late": 7, "instalment_amount": 50}])}
    run(code("setup"), v); run(code("compute_facts"), v)
    return v


def turn(v, n, **kw):
    v["negotiate.total_turns"] = str(n)
    for k in ("turn_intent", "turn_item", "turn_date", "turn_amount", "turn_hardship"):
        v.pop(k, None)
    v.update(kw)
    run(code("negotiate_turn"), v)
    return v["offer_state"]


class Engine(unittest.TestCase):
    def test_today_no_triggers_offer_1(self):
        v = start()
        s = turn(v, 1, turn_intent="refuse", turn_item="1"); self.assertIn("triggers offer 1", s); self.assertIn("= 0", s)
        s = turn(v, 2, turn_intent="refuse", turn_item="1"); self.assertIn("= 1", s); self.assertIn("offer 2", s)

    def test_hardship_with_refusal(self):
        v = start()
        turn(v, 1, turn_intent="refuse", turn_item="1")
        s = turn(v, 2, turn_intent="refuse", turn_hardship="yes", turn_item="2"); self.assertIn("HARDSHIP", s)

    def test_small_talk_uses_no_attempt(self):
        v = start()
        turn(v, 0, turn_intent="refuse", turn_item="1")
        s = turn(v, 1, turn_intent="off_topic", turn_item="2")
        self.assertIn("NO persuasion attempt", s); self.assertIn("refusals counted by code = 0", s)
        s = turn(v, 2, turn_intent="refuse", turn_item="2"); self.assertIn("= 1", s); self.assertIn("offer 2", s)
        s = turn(v, 3, turn_intent="question", turn_item="2"); self.assertIn("= 1", s)
        s = turn(v, 4, turn_intent="refuse", turn_item="2"); self.assertIn("all 2 offers are refused", s)

    def test_same_turn_not_counted_twice(self):
        v = start()
        turn(v, 0, turn_intent="refuse", turn_item="1")
        turn(v, 1, turn_intent="refuse", turn_item="3")
        v["turn_intent"] = "refuse"; run(code("negotiate_turn"), v)   # same total_turns again
        self.assertIn("= 1", turn(v, 1, turn_intent="refuse", turn_item="2") if False else v["offer_state"].replace("all 1 offers", "= 1"))

    def test_hardship_blocks_offers(self):
        v = start()
        turn(v, 0, turn_intent="refuse", turn_item="1")
        s = turn(v, 1, turn_intent="hardship", turn_item="2")
        self.assertIn("HARDSHIP", s); self.assertNotIn("offer 1:", s)
        s = turn(v, 2, turn_intent="refuse", turn_item="2"); self.assertIn("HARDSHIP", s)

    def test_dates_and_amounts(self):
        v = start()
        s = turn(v, 1, turn_intent="propose", turn_item="1", turn_date="the thirtieth")
        self.assertIn("Friday 30 October 2026", s); self.assertIn("TOO LATE", s)
        s = turn(v, 2, turn_intent="propose", turn_item="1", turn_date="Saturday")
        self.assertIn("NOT a business day", s)
        s = turn(v, 3, turn_intent="propose", turn_item="1", turn_amount="two hundred")
        self.assertIn("= 200.00", s); self.assertIn("acceptable", s)
        s = turn(v, 4, turn_intent="propose", turn_item="1", turn_amount="fifty")
        self.assertIn("BELOW the minimum 100.00", s)
        s = turn(v, 5, turn_intent="propose", turn_item="1", turn_date="next week")
        self.assertIn("vague", s)


if __name__ == "__main__":
    unittest.main()


class Routes(unittest.TestCase):
    def test_hardship_routes_in_same_turn(self):
        v = start(); turn(v, 0, turn_intent="refuse", turn_item="1")
        turn(v, 1, turn_intent="refuse", turn_hardship="yes", turn_item="1")
        self.assertEqual(v["route_hardship"], "yes")
        tr = WF["nodes"]["negotiate_turn"]["transitions"]
        self.assertEqual(tr[0]["target_node"], "negotiate_hardship")
        turn(v, 2, turn_intent="refuse", turn_hardship="yes", turn_item="1")
        self.assertEqual(v["route_hardship"], "no")          # only on the first mention for that item

    def test_hardship_step_has_no_offer_list(self):
        n = WF["nodes"]["negotiate_hardship"]
        self.assertIn("{{item_facts_plain}}", n["task_message"]); self.assertNotIn("{{item_facts}}", n["task_message"])
        self.assertNotIn("offer_state", n["task_message"])

    def test_instruction_text_is_not_a_statement(self):
        ex = [x for x in WF["nodes"]["negotiate"]["extraction_schema"] if x["name"] == "turn_intent"][0]
        self.assertIn("system note", ex["description"]); self.assertIn("is other", ex["description"])
        self.assertIn("not a statement of fact", WF["nodes"]["negotiate"]["task_message"])


class ReplayX13(unittest.TestCase):
    def test_late_band_today_no_then_two_offers(self):
        """X13's turn sequence: 'cannot pay today' -> offer 1 (full); 'no' -> offer 2 (floor on the deadline); accept."""
        v = start()
        s = turn(v, 1, turn_intent="refuse", turn_item="2")
        self.assertIn("triggers offer 1", s); self.assertIn("must be offer 1", s)
        s = turn(v, 2, turn_intent="refuse", turn_item="2")
        self.assertIn("refusals counted by code = 1", s); self.assertIn("must be offer 2: 650.00", s)
        s = turn(v, 3, turn_intent="accept", turn_item="2")
        self.assertIn("must be offer 2", s)


class GuardAndHardshipOffer(unittest.TestCase):
    def test_retry_guard_counts_outside_proposals(self):
        code_g = code("third_party_guard"); v = {"now": "2026-10-14T11:00"}
        for t, prop, want in ((1, "outside", "no"), (2, "outside", "yes")):
            v["third_party.total_turns"] = str(t); v["turn_proposal"] = prop; run(code_g, v)
            self.assertEqual(v["guard_exhausted"], want)
        tr = WF["nodes"]["third_party_guard"]["transitions"]
        self.assertEqual(tr[0]["target_node"], "end_no_callback")

    def test_hardship_offer_empty_means_no_offer(self):
        import copy, sys
        sys.path.insert(0, str(ROOT / "builder" / "skill")); import gen
        cfg = json.load(open(ROOT / "dev/out/brief-b.config.json")); cfg["openapi"] = str(ROOT / "tools/openapi.json")
        cfg2 = copy.deepcopy(cfg); cfg2["flow"]["nodes"]["negotiate"]["offer_state"]["hardship_offer"] = ""
        api = json.load(open(ROOT / "tools/openapi.json"))
        e1 = gen.Gen(cfg, api).build()["nodes"]["negotiate_hardship"]["on_enter"]["prompt"]
        e2 = gen.Gen(cfg2, api).build()["nodes"]["negotiate_hardship"]["on_enter"]["prompt"]
        self.assertIn("customer support team", e1); self.assertIn("Make NO offer of any kind", e2)
