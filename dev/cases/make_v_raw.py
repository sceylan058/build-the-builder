"""Generate dev/cases/v_raw.json; dates from dev/oracle.py with V-RAW parameters (memo applied, band boundary by date)."""
import datetime as dt, json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from oracle import Rules
D = dt.date
HOL = ["2026-10-26", "2026-11-26", "2026-12-25", "2027-01-01"]          # 11 Nov cancelled by the memo
BEFORE = {"holidays": HOL, "bands": [{"min": 1, "max": 7, "deadline_n": 10, "attempts": 1}, {"min": 8, "max": 45, "deadline_n": 7, "attempts": 2}],
          "attempt1": "last_business_day_of_week", "callback": {"start": "10:00", "end": "19:00"}}
AFTER = dict(BEFORE, bands=[{"min": 1, "max": 5, "deadline_n": 10, "attempts": 1}, {"min": 6, "max": 45, "deadline_n": 7, "attempts": 2}])
R = lambda today: Rules(AFTER if today >= D(2026, 10, 19) else BEFORE)
iso = lambda d: d.isoformat()
P = lambda pid, amt, d: {"product_id": pid, "amount": amt, "date": iso(d)}
N = lambda pid, r: {"product_id": pid, "reason": r}
E = lambda o, r=None, promises=(), notes=(), callbacks=(), transfers=(): {"outcome": o, "reason": r, "promises": list(promises), "notes": list(notes), "callbacks": list(callbacks), "transfers": list(transfers)}
W14, T15, M19, T20, W21, F23, M1109 = D(2026, 10, 14), D(2026, 10, 15), D(2026, 10, 19), D(2026, 10, 20), D(2026, 10, 21), D(2026, 10, 23), D(2026, 11, 9)
r20 = R(T20)
cases = [
 ("VR-01", "PUB-01", W14, "11:00", "Effective date", "Verified. Cannot pay today and gives no reason. Refuses every offer without a reason.",
  E("no_promise", "refused", notes=[N("p1", "refused")]), ["exactly one persuasion attempt (6 days late is EARLY before 19 October)", "the word 'debt' is never said"], "Before 19 Oct: 6 days = EARLY, 1 attempt; note REF; NP/REF."),
 ("VR-02", "PUB-01", T20, "11:00", "Effective date", "Verified. Cannot pay today. Refuses the first offer without a reason. Accepts the second offer.",
  E("promise", promises=[P("p1", 126.0, r20.deadline(T20, 6))]), ["two persuasion attempts (6 days late is LATE from 19 October)", "the second offer is the minimum 126.00 on Friday 30 October"], "From 19 Oct: 6 days = LATE; attempt 2 = floor on the 7th business day (26 Oct holiday) = Fri 30 Oct."),
 ("VR-03", "PUB-08", T20, "11:00", "Memo override", "Verified. Cannot pay today. Wants to pay the full amount on 10 November. Accepts the latest possible date when offered.",
  E("promise", promises=[P("p1", 180.0, r20.deadline(T20, 5))]), ["the latest date offered is Wednesday 4 November", "promise recorded for 4 November"], "Memo §1: EARLY deadline = 10th business day = Wed 4 Nov (the extract's 12th would be Fri 6 Nov)."),
 ("VR-04", "PUB-07", W14, "11:00", "Memo override", "Verified. Cannot pay today. Wants to pay the full amount on 5 November. Accepts the latest possible date when offered.",
  E("promise", promises=[P("p1", 540.0, R(W14).deadline(W14, 5))]), ["the latest date offered is Thursday 29 October", "promise recorded for 29 October"], "Memo §1: 10th business day after Wed 14 Oct = Thu 29 Oct (26 Oct holiday)."),
 ("VR-05", "PUB-04", M1109, "10:30", "Cancelled holiday", "Verified. Cannot pay today. Wants to pay the full amount on Wednesday 11 November. Confirms at the read-back.",
  E("promise", promises=[P("p1", 1250.0, D(2026, 11, 11))]), ["11 November is accepted as a business day", "promise recorded for 11 November"], "Memo §3: 11 Nov is a normal business day; within the LATE deadline (Wed 18 Nov)."),
 ("VR-06", "PUB-08", T15, "11:00", "Wording", "Verified. Can pay the full amount today. Confirms at the read-back.",
  E("promise", promises=[P("p1", 180.0, T15)]), ["the word 'debt' is never said", "the card is named 'Visa card ending 5512'"], "Mail: never say debt; code list: spoken product names."),
 ("VR-07", "PUB-06", T20, "11:00", "Code list", "Verified. Says the full amount is too much. Accepts the minimum payment on the date the agent offers.",
  E("promise", promises=[P("p1", 637.5, r20.attempt1(T20))]), ["the card is named 'Visa card ending 1903'", "minimum offered once, with the note that the rest stays overdue"], "Attempt 1 with floor on the last business day of this week = Fri 23 Oct."),
 ("VR-08", "PUB-02", W21, "11:00", "Third party", "The person who answers is her husband. Asks what the call is about. Says Maria can be reached tomorrow at eleven in the morning.",
  E("not_reached", "callback", callbacks=[{"date": "2026-10-22", "time": "11:00"}]), ["the agent gives no reason for the call", "callback booked for 22 October at 11:00"], "§4.2."),
 ("VR-09", "PUB-03", T20, "11:00", "Identity", "Confirms the name. Gives date of birth 12 July 1991, then 21 August 1992, then 21 July 1990.",
  E("not_verified", "failed"), ["the check ends after the third wrong answer", "no amount or product disclosed"], "§5.2."),
 ("VR-10", "PUB-05", W21, "11:00", "Hardship", "Verified. Says he lost his job and cannot pay anything. Does not want to be transferred.",
  E("no_promise", "hardship", notes=[N("p1", "hardship")]), ["one sentence of sympathy", "support team offered once", "no persuasion attempt"], "§10 + §13: note HSH, NP/HSH."),
 ("VR-11", "PUB-09", W21, "11:00", "Restructuring", "Verified. Says he cannot pay this amount and wants lower instalments.",
  E("transferred", "restructuring", transfers=[{"queue": "restructuring"}]), ["transfer_to_agent called with queue restructuring", "no notes are written"], "§12."),
 ("VR-12", "PUB-12", T20, "11:00", "Multi-product", "Gives the date of birth correctly and the phone digits 4410. Will pay the credit card tomorrow. Flatly refuses to pay the personal loan or the car loan, whatever is offered.",
  E("promise", promises=[P("p1", 510.0, D(2026, 10, 21))], notes=[N("p2", "refused"), N("p3", "refused")]), ["two persuasion attempts on the car loan (7 days late is LATE from 19 October)", "one 'refused' note each for the loan and the car"], "From 19 Oct the 7-day car loan is LATE (2 attempts)."),
 ("VR-13", "PUB-11", W14, "11:00", "Multi-product", "Verified. Cannot pay today. Agrees to pay all three this Friday. Confirms once.",
  E("promise", promises=[P("p1", 220.0, D(2026, 10, 16)), P("p2", 640.0, D(2026, 10, 16)), P("p3", 75.0, D(2026, 10, 16))]), ["the vehicle finance agreement is named with its code-list name", "one read-back for all three"], "All within their deadlines."),
 ("VR-14", "PUB-13", M19, "10:30", "Multi-product", "Verified. Cannot pay today. Wants to pay both on 30 October. Accepts when told the loan has an earlier latest date.",
  E("promise", promises=[P("p1", 300.0, D(2026, 10, 30)), P("p2", 900.0, R(M19).deadline(M19, 20))]), ["the Visa card is recorded on 30 October", "the personal finance loan is recorded on its deadline, 29 October"], "Card EARLY deadline Tue 3 Nov; loan LATE deadline = 7th business day after Mon 19 Oct = Thu 29 Oct."),
 ("VR-15", "PUB-10", F23, "10:00", "Tool failure", "Verified. Cannot pay today. Accepts the first offer and confirms.",
  E("promise", promises=[P("p1", 365.0, R(F23).attempt1(F23))]), ["exactly one promise after the retry", "attempt 1 proposes Friday 30 October (today is the last business day of this week)"], "§9 attempt 1 on a Friday moves to next week."),
]
out = [{"id": i, "brief": "V-RAW", "family": f, "level": "medium", "title": s.split(".")[0][:60], "session_case": sess, "now": f"{d.isoformat()}T{t}",
        "third_party": f == "Third party", "script": s, "expected": e, "checks": ch, "why": w} for i, sess, d, t, f, s, e, ch, w in cases]
json.dump(out, open(pathlib.Path(__file__).with_name("v_raw.json"), "w"), indent=1)
print(len(out), "cases;", [(c["id"], [p["date"] for p in c["expected"]["promises"]]) for c in out if c["expected"]["promises"]])
