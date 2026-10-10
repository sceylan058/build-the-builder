"""Generate dev/cases/v_clean.json; every expected date comes from dev/oracle.py with V-CLEAN parameters."""
import datetime as dt, json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from oracle import Rules
D = dt.date
VC = {"holidays": ["2026-10-16", "2026-11-11", "2026-12-24", "2026-12-25", "2027-01-01"],
      "bands": [{"name": "standard", "min": 1, "max": 10, "deadline_n": 10, "attempts": 1}, {"name": "priority", "min": 11, "max": 45, "deadline_n": 5, "attempts": 2}],
      "attempt1": "nth_business_day:3", "callback": {"start": "09:00", "end": "17:00"}}
R = Rules(VC)
iso = lambda d: d.isoformat()
T13, M19, W21, T1222 = D(2026, 10, 13), D(2026, 10, 19), D(2026, 10, 21), D(2026, 12, 22)
P = lambda pid, amt, d: {"product_id": pid, "amount": amt, "date": iso(d)}
E = lambda o, r=None, promises=(), notes=(), callbacks=(), transfers=(): {"outcome": o, "reason": r, "promises": list(promises), "notes": list(notes), "callbacks": list(callbacks), "transfers": list(transfers)}
N = lambda pid, r: {"product_id": pid, "reason": r}
cases = [
 ("VC-01", "PUB-01", "2026-10-13T11:00", "Happy path", "Confirms he is Daniel Reyes. Last four digits 4471, date of birth 14 March 1988. Can pay the full amount today. Confirms at the read-back.",
  E("promise", promises=[P("p1", 420.0, T13)]), ["the name question uses first and last name", "the phone digits are asked before the date of birth", "after the promise the agent says 'A confirmation will be sent to you by text message.'"], "C2, E1, J4; today Tue 13 Oct is a business day."),
 ("VC-02", "PUB-08", "2026-10-13T11:00", "Dates", "Verified. Cannot pay today and gives no date or amount. Accepts the first offer made.",
  E("promise", promises=[P("p1", 180.0, R.attempt1(T13))]), ["attempt 1 proposes Monday 19 October (3rd business day; Fri 16 Oct is a holiday)", "promise recorded for the full 180.00"], "I2: 3rd business day after Tue 13 Oct = Mon 19 Oct (16 Oct holiday)."),
 ("VC-03", "PUB-07", "2026-10-13T11:00", "Dates", "Verified. Cannot pay today. Wants to pay the full amount this Friday. Accepts the next business day when told Friday is not possible.",
  E("promise", promises=[P("p1", 540.0, R.promise_date(T13, 5, D(2026, 10, 16)))]), ["the agent does not accept Friday 16 October (bank holiday)", "the agent offers Monday 19 October"], "G2: Fri 16 Oct is a V-CLEAN holiday -> next business day Mon 19 Oct, within the standard deadline."),
 ("VC-04", "PUB-04", "2026-10-19T10:30", "Dates", "Verified. Cannot pay today. Wants to pay the full amount on 30 October. Accepts the latest possible date when it is offered.",
  E("promise", promises=[P("p1", 1250.0, R.deadline(M19, 14))]), ["the agent says the latest possible date is Monday 26 October", "promise recorded for 26 October"], "Priority tier (14 days): 5th business day after Mon 19 Oct = Mon 26 Oct (26 Oct is NOT a holiday in V-CLEAN)."),
 ("VC-05", "PUB-04", "2026-10-21T15:00", "Amounts", "Verified. Says the full amount is too much right now. Accepts the minimum amount on the date the agent offers.",
  E("promise", promises=[P("p1", 625.0, R.attempt1(W21))]), ["the minimum offered is 625.00 (half the overdue amount of the car loan)", "the agent says the remainder stays overdue"], "H2: car loan minimum = half of 1250 = 625; I2 attempt 1 date = 3rd business day after Wed 21 Oct = Mon 26 Oct."),
 ("VC-06", "PUB-03", "2026-10-13T11:00", "Identity", "Confirms the name. Gives the last four digits as 6603, then as 3660. Then asks how much he owes.",
  E("not_verified", "failed"), ["the check ends after the second wrong answer", "no amount or product is mentioned", "the customer is told to use the mobile app or a branch"], "E2: two wrong answers end the check although the mock allows three."),
 ("VC-07", "PUB-09", "2026-10-19T10:30", "Human", "Verified. As soon as the debt is stated, asks to speak to a real person.",
  E("transferred", "human", transfers=[{"queue": "general"}]), ["transfer_to_agent called with queue general", "the agent does not first ask whether it can help"], "K4: transfer at once, no attempt to help first; no notes."),
 ("VC-08", "PUB-05", "2026-10-19T10:30", "Hardship", "Verified. Says he lost his job last month and cannot pay anything. Does not name a date or amount.",
  E("no_promise", "hardship", notes=[N("p1", "hardship")]), ["one sentence of sympathy", "no persuasion attempt", "no transfer to a support team is offered"], "I4: no support offer; L: note hardship even for one product; M: no_promise/hardship."),
 ("VC-09", "PUB-02", "2026-10-19T11:00", "Third party", "The person who answers is her husband. Asks what it is about. Says Maria can be reached tomorrow at six in the evening; when told that is not possible, says tomorrow at half past four in the afternoon.",
  E("not_reached", "callback", callbacks=[{"date": "2026-10-20", "time": "16:30"}]), ["the agent gives no reason for the call", "18:00 is refused as outside 09:00-17:00", "callback booked for 20 October at 16:30"], "D2/D3: window 09:00-17:00, next business day Tue 20 Oct."),
 ("VC-10", "PUB-02", "2026-10-13T11:00", "Third party", "The person who answers is her husband. Says Maria can be reached tomorrow at eight in the morning; when told that is not possible, says Friday at noon.",
  E("not_reached", "no_callback"), ["no callback is booked", "the window is explained once and a second time is asked for"], "D3: 08:00 is before 09:00; Friday 16 Oct is a holiday and not the next business day (Wed 14 Oct)."),
 ("VC-11", "PUB-02", "2026-10-21T15:00", "Third party", "The person who answers says that Maria passed away last month.",
  E("not_reached", "deceased"), ["the agent says 'Please accept our condolences.'", "the agent asks nothing else"], "D5."),
 ("VC-12", "PUB-06", "2026-10-19T10:30", "Persuasion", "Verified. Cannot pay today. Refuses the first offer without giving a reason. Accepts the second offer.",
  E("promise", promises=[P("p1", 637.5, R.deadline(M19, 12))]), ["two persuasion attempts (priority tier)", "the second offer is the minimum 637.50 on Monday 26 October"], "Priority tier: attempt 1 full on Thu 22 Oct; attempt 2 minimum 637.50 on the deadline Mon 26 Oct."),
 ("VC-13", "PUB-07", "2026-10-21T15:00", "Persuasion", "Verified. Cannot pay today. Refuses every offer without giving a reason.",
  E("no_promise", "refused", notes=[N("p1", "refused")]), ["exactly one persuasion attempt (standard tier)", "no promise recorded"], "Standard tier: 1 attempt; L: note refused for the single product."),
 ("VC-14", "PUB-12", "2026-10-13T11:00", "Multi-product", "Gives the phone digits 4410 and the date of birth correctly. Says the credit card was already paid this morning, says he never had the personal loan, and flatly refuses to pay the car loan whatever is offered.",
  E("no_promise", "refused", notes=[N("p1", "paid"), N("p2", "dispute"), N("p3", "refused")]), ["all three products stated before any ask", "one note per product", "no promise recorded"], "M: the close reason is the LAST non-paid note in get_account order = p3 refused (A+B would give dispute)."),
 ("VC-15", "PUB-13", "2026-10-19T10:30", "Multi-product", "Verified. Cannot pay today. Wants to pay both on 30 October. Accepts when told the loan has an earlier latest date.",
  E("promise", promises=[P("p1", 300.0, R.promise_date(M19, 4, D(2026, 10, 30))), P("p2", 900.0, R.promise_date(M19, 20, D(2026, 10, 30)))]), ["the credit card is recorded on 30 October", "the loan is recorded on its own deadline, 26 October", "one read-back names both dates"], "Standard deadline Mon 2 Nov; priority deadline Mon 26 Oct."),
 ("VC-16", "PUB-10", "2026-10-21T15:00", "Tool failure", "Verified. Cannot pay today. Accepts the first offer made and confirms.",
  E("promise", promises=[P("p1", 365.0, R.attempt1(W21))]), ["exactly one promise after the retry", "the agent does not say it is recorded before a successful call"], "Fault: first create_promise fails; attempt 1 date Mon 26 Oct."),
 ("VC-17", "PUB-01", "2026-12-22T10:00", "Dates", "Verified. Cannot pay today and gives no reason. Accepts the first offer made.",
  E("promise", promises=[P("p1", 420.0, R.attempt1(T1222))]), ["attempt 1 proposes Tuesday 29 December", "promise recorded for 420.00"], "3rd business day after Tue 22 Dec: Wed 23, Mon 28, Tue 29 (24 and 25 Dec are holidays)."),
]
out = []
for cid, sess, now, fam, script, exp, checks, why in cases:
    out.append({"id": cid, "brief": "V-CLEAN", "family": fam, "level": "medium", "title": script.split(".")[0][:60], "session_case": sess, "now": now,
                "third_party": fam == "Third party", "script": script, "expected": exp, "checks": checks, "why": why})
json.dump(out, open(pathlib.Path(__file__).with_name("v_clean.json"), "w"), indent=1)
print(len(out), "cases;", [(c["id"], [p["date"] for p in c["expected"]["promises"]]) for c in out if c["expected"]["promises"]])
