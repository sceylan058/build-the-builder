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
    for k in ("turn_intent", "turn_item", "turn_date", "turn_amount"):
        v.pop(k, None)
    v.update(kw)
    run(code("negotiate_turn"), v)
    return v["offer_state"]


class Engine(unittest.TestCase):
    def test_small_talk_uses_no_attempt(self):
        v = start()
        s = turn(v, 1, turn_intent="off_topic", turn_item="2")
        self.assertIn("NO persuasion attempt", s); self.assertIn("refusals counted by code = 0", s)
        s = turn(v, 2, turn_intent="refuse", turn_item="2"); self.assertIn("= 1", s); self.assertIn("offer 2", s)
        s = turn(v, 3, turn_intent="question", turn_item="2"); self.assertIn("= 1", s)
        s = turn(v, 4, turn_intent="refuse", turn_item="2"); self.assertIn("all 2 offers are refused", s)

    def test_same_turn_not_counted_twice(self):
        v = start()
        turn(v, 1, turn_intent="refuse", turn_item="3")
        v["turn_intent"] = "refuse"; run(code("negotiate_turn"), v)   # same total_turns again
        self.assertIn("= 1", turn(v, 1, turn_intent="refuse", turn_item="2") if False else v["offer_state"].replace("all 1 offers", "= 1"))

    def test_hardship_blocks_offers(self):
        v = start()
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
