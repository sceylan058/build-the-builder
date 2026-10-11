"""Identity normalisers and close-rule selectors.   python3 -m unittest dev/tests/test_identity_close.py"""
import json, pathlib, sys, textwrap, unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "builder" / "skill"))
import gen  # noqa: E402
CFG = {"calendar": {"workdays": [0, 1, 2, 3, 4], "holidays": []}}
L = {"vars": {}}
exec(gen.date_lib(CFG) + "\nORDER = 'dmy'\n" + gen.NORM_DATE, L)


class Normalisers(unittest.TestCase):
    def test_digits(self):
        for s, want in {"seven three one zero": "7310", "double seven one oh": "7710", "7 3, 1 0": "7310", "seventy three ten": "7310",
                        "nine two oh five": "9205", "triple three seven": "3337"}.items():
            self.assertEqual(L["spoken_digits"](s), want, s)

    def test_years(self):
        for s, want in {"nineteen eighty three": "1983", "nineteen ninety-one": "1991", "two thousand and four": "2004", "1979": "1979",
                        "one nine eight eight": "1988", "twenty twelve": "2012"}.items():
            self.assertEqual(L["spoken_year"](s), want, s)

    def test_codes(self):
        for s, want in {"S W one A one A A": "SW1A1AA", "E C two A double one B B": "EC2A11BB", "m one 1 a e": "M11AE"}.items():
            self.assertEqual(L["spoken_code"](s), want, s)

    def test_dates(self):
        for s, want in {"the ninth of February 1985": "1985-02-09", "09/02/1985": "1985-02-09", "17 June 1979": "1979-06-17", "1979-06-17": "1979-06-17"}.items():
            self.assertEqual(L["norm_date"](s), want, s)


def close(rules, ledger, ids, hint="done", by_hint=None):
    v = {"ledger_json": json.dumps(ledger), "item_ids": json.dumps(ids), "now": "2026-10-14T11:00"}
    head = (gen.date_lib(CFG) + "\nRULES = " + gen.lit(rules) + "\nBY_HINT = " + gen.lit(by_hint or {"done": ["no_promise", "refused"]}) +
            "\nNO_REASON = " + gen.lit(["promise", "paid"]) + "\nCLOSING = " + gen.lit({"lines": {"default": "Bye."}}) + "\nHINT = " + repr(hint) + "\n")
    g = {}
    exec("def __run(vars):\n" + textwrap.indent(head + gen.FINAL_CODE, "    ") + "\n", g)
    g["__run"](v)
    return v["close_outcome"], v.get("close_reason")


MAP = {r: ["no_promise", r] for r in ("refused", "hardship", "dispute", "service_error")}
MAP["paid"] = ["paid", ""]


class CloseRules(unittest.TestCase):
    def test_first_last_priority_over_1_to_3_items(self):
        notes3 = [["p1", "paid"], ["p2", "dispute"], ["p3", "refused"]]
        for order, want in (("first", "dispute"), ("last", "refused")):
            r = [{"when": {"notes_any": True}, "from_note": {"order": order, "skip": ["paid"], "map": MAP}}]
            self.assertEqual(close(r, {"notes": notes3}, ["p1", "p2", "p3"]), ("no_promise", want))
        r = [{"when": {"notes_any": True}, "from_note": {"priority": ["hardship", "refused", "dispute"], "skip": ["paid"], "map": MAP}}]
        self.assertEqual(close(r, {"notes": notes3}, ["p1", "p2", "p3"]), ("no_promise", "refused"))
        self.assertEqual(close(r, {"notes": [["p1", "dispute"]]}, ["p1"]), ("no_promise", "dispute"))
        self.assertEqual(close(r, {"notes": [["p1", "dispute"], ["p2", "hardship"]]}, ["p1", "p2"]), ("no_promise", "hardship"))

    def test_any_all_none_count(self):
        allpaid = {"notes": [["p1", "paid"], ["p2", "paid"]]}
        r = [{"when": {"notes_all": "paid"}, "outcome": "paid", "reason": ""}, {"when": {"notes_any": True}, "from_note": {"skip": ["paid"], "map": MAP}}]
        self.assertEqual(close(r, allpaid, ["p1", "p2"]), ("paid", None))
        r2 = [{"when": {"notes_none": "dispute", "notes_with": "refused"}, "outcome": "no_promise", "reason": "refused"}]
        self.assertEqual(close(r2, {"notes": [["p1", "refused"]]}, ["p1"]), ("no_promise", "refused"))
        self.assertEqual(close(r2, {"notes": [["p1", "refused"], ["p2", "dispute"]]}, ["p1", "p2"], by_hint={"done": ["no_promise", "x"]}), ("no_promise", "x"))
        r3 = [{"when": {"count": {"of": "records", "op": ">=", "n": 2}}, "outcome": "promise"}]
        self.assertEqual(close(r3, {"records": ["p1", "p2"]}, ["p1", "p2", "p3"])[0], "promise")
        self.assertEqual(close(r3, {"records": ["p1"]}, ["p1", "p2", "p3"])[0], "no_promise")

    def test_brief_b_and_v_clean_rules(self):
        bB = [{"when": {"flag": "transfer"}, "outcome": "transferred", "reason": {"from_flag": "transfer", "map": {"restructuring": "restructuring"}}},
              {"when": {"records": True}, "outcome": "promise"}, {"when": {"notes_all": "paid"}, "outcome": "paid", "reason": ""},
              {"when": {"notes_any": True}, "from_note": {"order": "first", "skip": ["paid"], "map": MAP}}]
        vc = [dict(r) for r in bB]; vc[3] = {"when": {"notes_any": True}, "from_note": {"order": "last", "skip": ["paid"], "map": MAP}}
        notes = {"notes": [["p1", "paid"], ["p2", "dispute"], ["p3", "refused"]]}
        self.assertEqual(close(bB, notes, ["p1", "p2", "p3"]), ("no_promise", "dispute"))
        self.assertEqual(close(vc, notes, ["p1", "p2", "p3"]), ("no_promise", "refused"))
        self.assertEqual(close(bB, dict(notes, records=["p1"]), ["p1", "p2", "p3"]), ("promise", None))
        self.assertEqual(close(bB, dict(notes, flags={"transfer": "restructuring"}, records=["p1"]), ["p1", "p2", "p3"]), ("transferred", "restructuring"))


if __name__ == "__main__":
    unittest.main()
