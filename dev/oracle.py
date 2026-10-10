"""Independent date/amount oracle (imports nothing from builder/). Parameters come from a JSON dict.
    python3 dev/oracle.py --test        # anchor tests under Brief A
"""
import datetime as dt, json, sys

D = dt.date
WD = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class Rules:
    def __init__(self, p):
        self.p = p
        self.hol = {D.fromisoformat(h) for h in p["holidays"]}
        self.work = set(p.get("workdays", [0, 1, 2, 3, 4]))

    def biz(self, d):
        return d.weekday() in self.work and d not in self.hol

    def next_biz(self, d, inclusive=False):
        d = d if inclusive else d + dt.timedelta(1)
        while not self.biz(d):
            d += dt.timedelta(1)
        return d

    def nth_biz_after(self, today, n):
        d = today
        for _ in range(n):
            d = self.next_biz(d)
        return d

    def band(self, days_late):
        for b in self.p["bands"]:
            if b["min"] <= days_late <= b["max"]:
                return b
        raise ValueError(f"no band for {days_late}")

    def deadline(self, today, days_late):
        return self.nth_biz_after(today, self.band(days_late)["deadline_n"])

    def last_biz_of_week(self, d):
        mon = d - dt.timedelta(d.weekday())
        days = [mon + dt.timedelta(i) for i in range(7) if self.biz(mon + dt.timedelta(i))]
        return days[-1] if days else None

    def attempt1(self, today):
        r = self.p.get("attempt1", "last_business_day_of_week")
        if r == "last_business_day_of_week":
            x = self.last_biz_of_week(today)
            if x is None or x <= today:
                x = self.last_biz_of_week(today + dt.timedelta(7))
            return x
        if r.startswith("nth_business_day:"):
            return self.nth_biz_after(today, int(r.split(":")[1]))
        raise ValueError(r)

    @staticmethod
    def weekday(today, name, which):
        k = WD.index(name.lower())
        mon = today - dt.timedelta(today.weekday())
        return mon + dt.timedelta(k + (7 if which == "next" else 0))

    def promise_date(self, today, days_late, asked):
        """Date to record when the customer names `asked` (rules: weekend/holiday -> next business day; after deadline -> deadline)."""
        dl = self.deadline(today, days_late)
        if asked > dl:
            return dl
        if not self.biz(asked):
            n = self.next_biz(asked)
            return n if n <= dl else dl
        return asked

    def callback_ok(self, now, day, hhmm):
        s, e = self.p["callback"]["start"], self.p["callback"]["end"]
        allowed = {now.date()} if self.biz(now.date()) else set()
        allowed.add(self.next_biz(now.date()))
        return day in allowed and s <= hhmm <= e and dt.datetime.combine(day, dt.time.fromisoformat(hhmm)) > now

    def floor(self, product):
        f = self.p["floor"][product["type"]]
        if isinstance(f, str) and f.startswith("ratio:"):
            return round(product["past_due"] * float(f.split(":")[1]), 2)
        return product[f]


BRIEF_A = {"holidays": ["2026-10-26", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01"],
           "bands": [{"name": "early", "min": 1, "max": 7, "deadline_n": 12, "attempts": 1},
                     {"name": "late", "min": 8, "max": 45, "deadline_n": 7, "attempts": 2}],
           "attempt1": "last_business_day_of_week", "callback": {"start": "10:00", "end": "19:00"},
           "floor": {"credit_card": "minimum_payment", "personal_loan": "instalment_amount", "car_loan": "instalment_amount"}}


def test():
    R = Rules(BRIEF_A)
    chk = [
        (R.deadline(D(2026, 10, 14), 10), D(2026, 10, 23)), (R.deadline(D(2026, 10, 14), 3), D(2026, 11, 2)),
        (R.last_biz_of_week(D(2026, 10, 14)), D(2026, 10, 16)),
        (R.deadline(D(2026, 10, 16), 10), D(2026, 10, 28)), (R.deadline(D(2026, 10, 16), 3), D(2026, 11, 4)), (R.attempt1(D(2026, 10, 16)), D(2026, 10, 23)),
        (R.next_biz(D(2026, 10, 23)), D(2026, 10, 27)), (R.next_biz(D(2026, 10, 24)), D(2026, 10, 27)),
        (R.attempt1(D(2026, 12, 24)), D(2026, 12, 31)), (R.deadline(D(2026, 12, 24), 10), D(2027, 1, 6)), (R.deadline(D(2026, 12, 24), 3), D(2027, 1, 13)),
        (R.weekday(D(2026, 10, 16), "friday", "next"), D(2026, 10, 23)),
    ]
    bad = [(i, got, want) for i, (got, want) in enumerate(chk) if got != want]
    for i, got, want in bad:
        print(f"ANCHOR {i} FAILED: got {got}, want {want}")
    print(f"oracle anchors: {len(chk) - len(bad)}/{len(chk)} pass")
    return not bad


if __name__ == "__main__":
    sys.exit(0 if test() else 1)
