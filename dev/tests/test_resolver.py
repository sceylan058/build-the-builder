"""Unit tests for gen.py's date resolver and amount normaliser.   python3 -m unittest dev/tests/test_resolver.py"""
import datetime as dt, json, pathlib, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "builder" / "skill"))
import gen  # noqa: E402

CFG = {"calendar": {"workdays": [0, 1, 2, 3, 4], "holidays": ["2026-10-26", "2026-12-25", "2027-01-01"]}}
L = {"vars": {}}
exec(gen.date_lib(CFG), L)
R, W = L["resolve_date"], L["words_to_number"]
D = dt.date


class Resolver(unittest.TestCase):
    def test_relative_words_over_grid(self):
        start = D(2026, 10, 12)
        days = [start + dt.timedelta(i) for i in range(21)] + [D(2026, 10, 30), D(2026, 10, 31), D(2026, 12, 30), D(2026, 12, 31)]
        for today in days:
            self.assertEqual(R("today", today), today)
            self.assertEqual(R("I can pay tomorrow", today), today + dt.timedelta(1))
            self.assertEqual(R("the day after tomorrow", today), today + dt.timedelta(2))
            mon = today - dt.timedelta(today.weekday())
            self.assertEqual(R("next Friday", today), mon + dt.timedelta(11))
            self.assertEqual(R("this Friday", today), mon + dt.timedelta(4))
            self.assertEqual(R("next week", today), "vague")
            self.assertEqual(R("when my salary comes", today), "vague")

    def test_day_numbers_and_words(self):
        t = D(2026, 10, 14)
        self.assertEqual(R("the 30th", t), D(2026, 10, 30))
        self.assertEqual(R("30 October", t), D(2026, 10, 30))
        self.assertEqual(R("October 30", t), D(2026, 10, 30))
        self.assertEqual(R("the thirtieth of October", t), D(2026, 10, 30))
        self.assertEqual(R("the twenty third", t), D(2026, 10, 23))
        self.assertEqual(R("the fifth", t), D(2026, 11, 5))           # past day of this month -> next month
        self.assertEqual(R("2026-10-23", t), D(2026, 10, 23))
        self.assertEqual(R("on the 2nd of January", D(2026, 12, 24)), D(2027, 1, 2))
        self.assertEqual(R("Monday the 26th", t), D(2026, 10, 26))
        self.assertEqual(R("Friday the thirtieth", t), D(2026, 10, 30))
        self.assertIsNone(R("whenever", t))


class Amounts(unittest.TestCase):
    def test_words(self):
        cases = {"five hundred and ten": 510, "two thousand one hundred twenty-five point one": 2125.1, "four hundred fifty five": 455,
                 "six hundred thirty seven euros and fifty cents": 637.5, "1,250": 1250, "730.00": 730, "seventy five point five": 75.5,
                 "one thousand two hundred and fifty": 1250, "a hundred": 100, "nine hundred": 900}
        for s, want in cases.items():
            self.assertEqual(W(s), want, s)
        self.assertIsNone(W("no idea"))


if __name__ == "__main__":
    unittest.main()
