# Style runs (reps 3; a case counts only at 3/3)

| style | brief | passed | failed (passes) : first reason | median slowest turn |
|---|---|---|---|---|
| pieces | A | 6/10 | PUB-04 (0/3): promises [('p1', 400.0, '2026-10-23')], expected [('p1', 1250.0, '2026-10-23')]; PUB-05 (2/3): outcome ('no_promise', 'refused'), expected ('no_promise', 'hardship'); PUB-06 (2/3): conversation: - The agent offered the minimum payment amount twice (Message 12 and Message 14), violating the success criterion that it be offered only once. - ; PUB-07 (2/3): conversation: The agent failed to meet the first criterion as it asked for the payment date twice (Message 14 and Message 16). While the user provided 'Monday'  | 7 s |
| pieces | B | 1/3 | PUB-12 (2/3): promises [('p1', 500.0, '2026-10-15')], expected [('p1', 510.0, '2026-10-15')]; PUB-13 (2/3): promises [('p1', 300.0, '2026-10-27'), ('p2', 900.0, '2026-10-23')], expected [('p1', 300.0, '2026-10-30'), ('p2', 900.0, '2026-10-23')] | 9 s |
