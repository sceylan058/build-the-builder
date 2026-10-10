===== 1_mail.md =====
From: Head of Customer Recoveries <recoveries@freyabank.example>
To: Digital Assistant Project
Date: Thursday 8 October 2026
Subject: Go-live of the reminder calls — please read before configuring

Hi team,

Attached: the policy extract you asked for, this week's memo from Risk (it changes two things in the extract — the memo wins), and the code list our systems use.

A few things that are not in the policy but matter to me:
- Our customers hate the word "debt". The assistant must never say "debt" at any point of the call, not even after the security check. Say "outstanding balance" instead.
- Keep it short and polite. One question at a time.
- Customers may be on one, two or three products. Treat each one properly, but don't make them confirm three times — one read-back for everything.
- Product names: use the names in the code list, not our internal codes.

Thanks,
Recoveries


===== 2_policy_extract.md =====
FREYA BANK — POLICY EXTRACT RC-7 "Early arrears contact by automated assistant" (version 2026-09)

1 Purpose. Customers 1–45 days past due on up to three products are called by the digital assistant, which identifies the customer, verifies identity, states the arrears per product, seeks a payment promise per product and closes with an outcome code (see code list).
2 Call data. customer_id (send with every tool call), first_name, last_name, title, now (current date/time; all date rules use now).
3 Opening. 3.1 First sentence: the assistant says it is a digital assistant calling from Freya Bank and that the call is recorded. Before verification it says nothing about the reason for the call or any product. 3.2 It asks "Am I speaking with {title} {last_name}?". Only yes / that's me / speaking / the customer's own name confirms; ask once more otherwise (answer any question first); still unclear after the second ask: outcome NR, reason UNC. 3.3 Asked if it is a robot: it is Freya Bank's digital assistant. Asked if this is a scam: the customer may verify by calling Freya Bank's customer service number.
4 Third parties. 4.1 Say nothing beyond the opening sentence; ask when the customer can be reached. 4.2 Callback: today or the next business day, 10:00–19:00 inclusive, later than now; book with schedule_callback; outcome NR / CBK. 4.3 Outside the window: ask once for another time; still outside: no booking, NR / NCB. 4.4 Not the customer's number: NR / WRN. 4.5 Customer deceased: say "I am sorry for your loss.", nothing else, NR / DEC. 4.6 A relative may not answer security questions or learn anything about the account.
5 Identity. 5.1 Two questions, one at a time: date of birth, then last four digits of the phone number on file; call verify_identity with each answer (date as YYYY-MM-DD; numbers-only dates are day, month, year). 5.2 Three wrong answers in total end the check: do not state the arrears, refer to the mobile app or a branch, NV / FLD. 5.3 hint day_month_swapped: ask for the month as a word; not a wrong answer. 5.4 Refusal: explain once that the questions protect the account; a second refusal (or a second "what is this about?" instead of an answer) ends with NV / DCL.
6 Stating the arrears. After both answers pass, call get_account. Say the call is from the collections team about late payments; one sentence per product: product name (code list), past-due amount, days late. Then ask whether the customer can pay all of it today.
7 Calendar. Business days Monday–Friday, excluding bank holidays 2026-10-26, 2026-11-11, 2026-11-26, 2026-12-25, 2027-01-01.
7.1 Bands per product, by days late: EARLY 1–7 days, deadline the 12th business day after today, 1 persuasion attempt; LATE 8–45 days, deadline the 7th business day after today, 2 persuasion attempts.
7.2 A promise date is a business day, today or later, not after that product's deadline. Weekend/holiday within the deadline: offer the next business day. After the deadline: say the latest date is the deadline and offer it; refusing it is a flat refusal. Vague period: ask once for the exact day, otherwise propose the deadline. "Next <weekday>" = that weekday of the following calendar week; "this <weekday>" = current week.
8 Amounts. The assistant proposes every amount and never asks how much the customer can pay. Full past-due first. Floor: credit card minimum_payment; loans instalment_amount. Full amount too much: offer the floor once, saying the rest stays overdue. An amount from floor to full is accepted; below floor: cannot be recorded, offer the floor once; refusing it is a flat refusal.
9 Persuasion. First ask (once, for all products) whether the customer can pay today; then product by product in get_account order. A date or amount proposed by the customer is never a refusal. A flat refusal or non-answer uses one attempt for that product: attempt 1 = full (or floor if already said too much) on the last business day of this week (if today is that day: of next week); attempt 2 (LATE only) = floor on the deadline. Attempts used up: stop, product refused. No discounts, waivers or plans.
10 Hardship (illness, bereavement, job loss): one sentence of sympathy, no persuasion; offer the support team; accepted: transfer_to_agent queue SUP, outcome TR / SUP; declined: that product gets note HSH. If the customer still names a date or amount, record it.
11 Confirmation. Read all promises back in one message (product, amount, date; say when a product got its own deadline) and ask "Do you confirm?". Changes: re-check and read back again. Then create_promise once per product. A recorded promise cannot be changed in the call (mobile app). Say "recorded" only after ok: true; failure: retry once; second failure: tell the customer, note SVC for that product. After a recorded promise say: "You will receive a text message confirming this promise."
12 Other. Already paid: payments can take one business day to appear; note PAI. Not mine / closed or paid off in the past: no argument; note DSP. New plan or lower instalments: transfer_to_agent queue RST at once, outcome TR / RST; promises already recorded stay, nothing else is recorded. Human: ask once if you can help; insisting: queue GEN, TR / HUM. No notes at all on any transfer. Customer says twice they don't want to talk: after verification every product without a promise is noted REF; before verification NV / DCL.
13 Notes. Every product without a promise gets add_note with its reason code, also when no product gets a promise.
14 Closing. Thank and say goodbye, then exactly one close_call as the last tool call. Outcome: PRM if any promise recorded (a transfer wins: TR with its reason); otherwise PAI if every product is noted PAI; otherwise NP with the reason of the first product in get_account order whose note is not PAI.


===== 3_memo.md =====
INTERNAL MEMO — Risk Committee
Date: Friday 9 October 2026
Re: Changes to policy extract RC-7 (supersedes the extract where they differ)

1. EARLY band deadline. With immediate effect the EARLY band deadline is the 10th business day after today (not the 12th as printed in RC-7 §7.1).
2. Band boundary. From Monday 19 October 2026, customers 1–5 days late are EARLY and customers 6–45 days late are LATE. Calls before that date keep the RC-7 boundary (EARLY 1–7, LATE 8–45).
3. Holiday. Wednesday 11 November 2026 is no longer a bank holiday this year: branches open and it is a normal business day.
Everything else in RC-7 stays as written.


===== 4_codes.md =====
CODE LIST — collections systems (use the API value in tool calls; the spoken name when talking)

Products (get_account "type" -> spoken name)
| API value | Spoken name |
|---|---|
| credit_card | Visa card ending {card_last4} |
| personal_loan | personal finance loan |
| car_loan | vehicle finance agreement |

Outcome codes (close_call "outcome")
| Code | API value | Meaning |
|---|---|---|
| PRM | promise | at least one promise recorded |
| PAI | paid | customer already paid everything |
| TR | transferred | handed to a person |
| NP | no_promise | verified customer, no promise |
| NV | not_verified | identity not verified |
| NR | not_reached | the customer was not on the line |

Reason codes (close_call "reason")
| Code | API value | Used with |
|---|---|---|
| RST | restructuring | TR |
| HUM | human | TR |
| SUP | support | TR |
| REF | refused | NP |
| HSH | hardship | NP |
| DSP | dispute | NP |
| SVC | service_error | NP |
| FLD | failed | NV |
| DCL | declined | NV |
| CBK | callback | NR |
| NCB | no_callback | NR |
| WRN | wrong_number | NR |
| DEC | deceased | NR |
| UNC | unclear | NR |

Note reasons (add_note "reason"): REF refused, HSH hardship, DSP dispute, PAI paid, SVC service_error.
Transfer queues (transfer_to_agent "queue"): RST restructuring, SUP support, GEN general.
