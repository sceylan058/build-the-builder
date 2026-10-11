# Architect report: styles (Phase B+, data only, reps 3; a case counts only at 3/3)

Agents: practice-a v16 and practice-b v18, both built by build.py from scratch (Phase A). Nothing was changed for these runs.

## Most important
The model-built practice agents are **much weaker on human speaking styles** than on plain scripts (plain: A 10/10, B 3/3).

| Style | A at 3/3 | B at 3/3 |
|---|---|---|
| pieces | 6/10 | 1/3 |
| corrects | 4/10 | 2/3 |
| talkative | 4/10 | 1/3 |
| asks_back | 9/10 | 1/3 |
| in_words | 8/10 | 3/3 |

The final scores at 3/3, so this is the main quality gap.

## Per style
| style | brief | passed | failed (passes): first reason | median slowest turn |
|---|---|---|---|---|
| pieces | A | 6/10 | PUB-04 (0/3): promises [('p1', 400.0, '2026-10-23')], expected [('p1', 1250.0, '2026-10-23')]; PUB-05 (2/3): outcome ('no_promise', 'refused'), expected ('no_promise', 'hardship'); PUB-06 (2/3): conversation: - The agent offered the minimum payment amount twice (Message 12 and Message 14), violating the success criterion that it be offered only once. - ; PUB-07 (2/3): conversation: The agent failed to meet the first criterion as it asked for the payment date twice (Message 14 and Message 16). While the user provided 'Monday'  | 7 s |
| pieces | B | 1/3 | PUB-12 (2/3): promises [('p1', 500.0, '2026-10-15')], expected [('p1', 510.0, '2026-10-15')]; PUB-13 (2/3): promises [('p1', 300.0, '2026-10-27'), ('p2', 900.0, '2026-10-23')], expected [('p1', 300.0, '2026-10-30'), ('p2', 900.0, '2026-10-23')] | 9 s |
| corrects | A | 4/10 | PUB-01 (2/3): promises [('p1', 420.0, '2026-10-16')], expected [('p1', 420.0, '2026-10-14')]; PUB-02 (2/3): conversation: no verdict; PUB-03 (2/3): conversation: no verdict; PUB-04 (2/3): promises [('p1', 400.0, '2026-10-23')], expected [('p1', 1250.0, '2026-10-23')]; PUB-07 (2/3): promises [('p1', 500.0, '2026-10-27')], expected [('p1', 540.0, '2026-10-27')]; PUB-09 (2/3): outcome ('no_promise', 'refused'), expected ('transferred', 'restructuring') | 3 s |
| corrects | B | 2/3 | PUB-13 (2/3): promises [('p1', 300.0, '2026-10-30'), ('p2', 800.0, '2026-10-23')], expected [('p1', 300.0, '2026-10-30'), ('p2', 900.0, '2026-10-23')] | 5 s |
| talkative | A | 4/10 | PUB-03 (2/3): outcome (None, None), expected ('not_verified', 'failed'); PUB-04 (0/3): promises [('p1', 400.0, '2026-10-23')], expected [('p1', 1250.0, '2026-10-23')]; PUB-05 (0/3): conversation: The agent failed two criteria: the support team was offered twice rather than once, and there were two sentences of sympathy provided rather than ; PUB-07 (2/3): conversation: The agent failed to meet the success criteria because it asked for the exact payment day twice (Message 12 and Message 14), violating the 'asks on; PUB-09 (1/3): outcome ('no_promise', 'refused'), expected ('transferred', 'restructuring'); PUB-10 (1/3): outcome ('not_verified', 'declined'), expected ('promise', None) | 2 s |
| talkative | B | 1/3 | PUB-12 (2/3): outcome ('no_promise', 'refused'), expected ('promise', None); PUB-13 (2/3): promises [('p1', 300.0, '2026-10-30')], expected [('p1', 300.0, '2026-10-30'), ('p2', 900.0, '2026-10-23')] | 9 s |
| asks_back | A | 9/10 | PUB-06 (1/3): promises [('p1', 637.5, '2026-10-23')], expected [('p1', 637.5, '2026-10-16')] | 8 s |
| asks_back | B | 1/3 | PUB-12 (1/3): conversation: The conversation failed to meet the security question criteria: the date of birth question was repeated in [Message 4] despite the requirement tha; PUB-13 (2/3): promises [('p1', 300.0, '2026-10-23'), ('p2', 900.0, '2026-10-23')], expected [('p1', 300.0, '2026-10-30'), ('p2', 900.0, '2026-10-23')] | 7 s |
| in_words | A | 8/10 | PUB-04 (2/3): promises [('p1', 1000.0, '2026-10-23')], expected [('p1', 1250.0, '2026-10-23')]; PUB-05 (1/3): outcome ('no_promise', 'refused'), expected ('no_promise', 'hardship') | 4 s |
| in_words | B | 3/3 |  | 5 s |

## Root causes (grouped, cases affected)
1. **Small talk or a non-answer is treated as a refusal, so the floor is offered too early.**
   - Cases: PUB-04 in pieces, talkative and corrects (0/3 twice); PUB-12/13 attempts.
   - The prompt rule "small talk … is a non-answer: go to the next step" (our own lesson from Phase 1) escalates the ladder when the customer was only chatting. The deadline offer then comes with the floor (400) instead of the full amount (1250).
   - Fix: a reply that ignores the offer gets the SAME offer once more; only a refusal or silence uses an attempt.
2. **Dates and amounts are misheard or reasoned wrongly when given in pieces, corrected, or in words.**
   - Cases: PUB-13 ("thirty" → 27 Oct "as the 30th is a business day"; 800 instead of 900), PUB-12 (500 instead of 510), PUB-06 (23 instead of 16 Oct).
   - Fix: make the read-back the only source of truth, with no clamp on date or amount except limits; code-check any date the model proposes against the calendar and refuse to record a date the model invented.
3. **"Today" is refused or recorded wrongly** (PUB-01, corrects: "I cannot record a payment for today"). Same root cause as Defect A in ARCHITECT_REPORT_B.
   - Fix: today's facts in every step, and a `min today` clamp.
4. **Hardship: persuasion after the decline** (PUB-05 in pieces, talkative, in_words).
   - Fix: a code route — an extracted `hardship` flag leads to a no-persuasion path, instead of a prompt rule.
5. **No judge verdict** (PUB-02/03 in corrects; PUB-03 outcome None in talkative): calls the simulator left unfinished. These are harness or simulator effects, but they count as fails at 3/3.

## Excerpts (≤6 lines each)
```
== talkative A PUB-04 (call a4ae0a7f-2f56-41c7-98ea-659417185343): promises [('p1', 400.0, '2026-10-23')], expected [('p1', 1250.0, '2026-10-23')]
   USER: It has been such a long day and I still have so
   ASSISTANT: I understand. Would you be able to pay 400.00 on Friday 23 October, though the rest would stay overdue?
   USER: I have been so busy with work that I can barely keep track of the days. Yes, I can do that on the twenty third of October.
   ASSISTANT: For your car loan, that would be 400.00 on Friday 23 October. Do you confirm?
   USER: The weather has been so gloomy today and it makes the commute
   ASSISTANT: I understand. To make sure we have this set, do you confirm the payment of 400.00 for your car loan on Friday 23 October?
== pieces B PUB-13 (call 987d1b49-90bc-4317-bf3b-e47414565c57): promises [('p1', 300.0, '2026-10-27'), ('p2', 900.0, '2026-10-23')], expected [('p1', 300.0, '2026-10-30'), ('p2', 900.0, '2026-10-23')]
   USER: I can't pay today.
   ASSISTANT: For your credit card ending 6604, can you pay 300.00 on Friday 16 October 2026?
   USER: I want to pay both on thirty.
   ASSISTANT: I can record that date. For the credit card ending 6604, I can record a payment of 300.00 on Tuesday 27 October 2026, as the 30th is a business day.
 For the personal loa
   USER: Okay, I will pay on those dates.
   ASSISTANT: To confirm: for the credit card ending 6604, the amount is 300.00 on Tuesday 27 October 2026, and for the personal loan, the amount is 900.00 on Friday 23 October 2026. D
== in_words A PUB-05 (call e49f6fc3-e0e8-4e5d-8e29-26dcf14e5830): outcome ('no_promise', 'refused'), expected ('no_promise', 'hardship')
   ASSISTANT: I am very sorry to hear about your job loss. I cannot offer a discount, but I can connect you with our customer support team for help. Would you like to speak with them?
   USER: No, I do not want to be transferred. I just need a discount because I have no money.
   ASSISTANT: As I mentioned, I cannot offer any discounts. Since you've declined the support team, I cannot help you further with this request.
   USER: I really can't pay anything right now.
   ASSISTANT: I understand. In that case, could you pay 780.00 on Friday 16 October 2026?
   USER: No, I cannot pay that.
== corrects A PUB-01 (call 85f63f5c-f456-4555-94ff-4b9fe0bc175e): promises [('p1', 420.0, '2026-10-16')], expected [('p1', 420.0, '2026-10-14')]
   USER: I can pay 410, sorry,
   ASSISTANT: That is acceptable. On what date will you make this payment?
   USER: I can pay the full amount today.
   ASSISTANT: I'm sorry, but I cannot record a payment for today. Would you be able to pay 420.00 on Friday 16 October 2026 instead?
   USER: Yes, that works.
   ASSISTANT: For your credit card ending 4821, you would be paying 420.00 on Friday 16 October 2026. Do you confirm?
== pieces B PUB-12 (call 896f3c04-3267-4ce7-bd39-37a56983d37a): promises [('p1', 500.0, '2026-10-15')], expected [('p1', 510.0, '2026-10-15')]
   USER: No, I'm not paying that.
   ASSISTANT: I understand. For your personal loan, could you pay 440.00 on Friday 23 October, with the rest staying overdue?
   USER: No, I won't pay that.
   ASSISTANT: Regarding your car loan, can you pay 140.00 on Friday 16 October?
   USER: I'm not paying the car loan.
   ASSISTANT: To confirm: for your credit card ending 9015, you will pay 500.00 on Thursday 15 October. Do you confirm?
```
