# Architect report: Phase C (status at the 12:30 Istanbul deadline)

## Most important
- **`safe-2` is NOT tagged.** Two cases that passed in Phase B still fail in the final targeted re-run:
  - **VR-10** (persuasion in the record step after a declined hardship offer);
  - **X03** (third party asked twice for another time; 2 of 3 failed).
- **Plain cases hold:** A 10/10 (PUB-05 fixed in run 5), B 3/3, extended B 5/5, extended A 18/19 (X03 only).
- **Fixed and verified live:** today-dates, routing after a transfer, the X20 injection (3/3 on the bank record), the record-step persuasion VR-01, PUB-05, and the four v_clean cases that hung in the record step. Styles at reps 1 are clearly better than the Phase B+ baseline (A pieces 9–10/10, corrects 6–7/10, talkative 5/10).
- **Open (new, from the final runs):**
  - **VC-08:** the generated hardship step invites a support offer even when the brief (V-CLEAN) offers none, which is a genericity bug in my step text.
  - **VR-10:** the model-written record entry prompt outweighs the appended record-only rule.
  - **VR-12 safety net** (close_call on hang-up/silence): designed, not built — needs an end-of-call hook that the kit marks unverified.
- **Latency:** the per-turn code step costs a median 0.21 s (worst 1.3 s) — it is not the bottleneck. The slow turns are the record step (median 10.7 s, worst 44.7 s: one model round trip per tool call) and the closing chain. Run medians ranged 3–11 s; the final runs were 16–28 s under platform load. Target (< 8 s median, < 20 s worst) **not met** in every run. Recommended cut: record every confirmed agreement in one engine step from a code-held agreement store, instead of one model call per item.
- **The builder's API key ran out of credit.** build.py now falls back to the Claude login automatically (live: `credentials: api_key -> claude_login (Credit balance is too low)`). `--reuse-config` recompiles a model-written config with the current generator without a model call (configs are never hand-edited).

## Fixes (root cause → fix → evidence); details in CHANGELOG.md
| Fix | Root cause | Evidence |
|---|---|---|
| C1 dates on `now` | record step had no today; clamp had no lower bound | resolver tests (21 days, month/year ends, words); PUB-01/VC-01 no longer record past dates |
| C2 offer engine | the "non-answer" prompt rule escalated offers on small talk; the model counted attempts itself | engine tests; live probe: the code state reaches the model in the SAME turn |
| C2 routing twin | no routing after a tool result in a re-entered step (PUB-09 never closed) | PUB-09 passes in all later runs |
| C2 last value wins | corrections were summed (600.87) | amount/date correction tests; PUB-06 |
| C3 hardship route | hardship lost by the model | live: routed in the same turn to `<step>_hardship` (no offer list); PUB-05 passes in run 5 |
| C4 identity | only date/digits; partial answers burned attempts | normaliser tests; offline drift proof (postcode/birth_year) passes check.py |
| C5 open calls | the calls had ended; judging lagged behind our dev timeout | dev timeout raised |
| C6 close rules | `from_note` could only take the first | close-rule tests incl. Brief B (first) and V-CLEAN (last) |
| record-only rule | the record step asked for date/amount (VR-01) | VR-01 passes in run 5; VR-10 still fails (see above) |
| X10/X13 checks | the judge counted the "today?" question as attempt 1 (agent correct per brief) | check wording fixed (harness); X13 replay test; both pass |
| audit fixes | leftover SKILL bullet; Brief A hardship words as a default; practice values in fixtures | hardship_triggers required/quoted; neutral fixtures; leak scan clean over builder/ and dev/tests |

## Gate runs (reps 1)
| Suite | Phase B | run 1 | run 2 | run 3 | run 4 | run 5 (targeted) |
|---|---|---|---|---|---|---|
| plain A | 10/10 | 10/10 | 10/10 | 9/10 | 9/10 | PUB-05 pass |
| plain B | 3/3 | 3/3 | 3/3 | 3/3 | – | – |
| ab_extended A (19) | 19/19 | 18/19 | 17/19 | 17/19 | 18/19 (X03) | – |
| ab_extended B (5) | 5/5 | 4/5 | 5/5 | 5/5 | – | – |
| v_raw (15) | 14/15 | 13/15 | 13/15 | 14/15 | 13/15 | VR-01 pass, VR-10 fail |
| v_clean (17) | 12/17 | – (blocked: key credit) | – | – | 11/17 | 4/6 of the failing pass; VC-01, VC-08 fail (also failed in B) |
| style A pieces | 6/10 (reps 3) | – | 10/10 | 9/10 | – | – |
| style A corrects | 4/10 (reps 3) | – | 7/10 | 6/10 | – | – |
| style A talkative | 4/10 (reps 3) | – | – | 5/10 | – | – |
| X20 ×3 | – | – | – | 2/3 judged pass (+1 no verdict; ledger 3/3) | – | – |

Not run in the final state: styles asks_back/in_words; B styles; v_clean in full on the latest agent.

## Remaining failures, classified
- X03: (c) agent behaviour in the model-written third-party step. Fix: code-count callback proposals.
- VR-10: (b) the record step entry prompt invites a payment question after a declined hardship offer. Fix: a fixed (code) entry for record-only steps, and a direct ending after a declined hardship.
- VC-08: (b) the generic hardship step implies a support offer. Fix: generate its text from the brief's hardship rule only ("if the rule offers nothing, offer nothing").
- VC-01: (b)/(c) the record step hangs after confirmation on dev-clean (silent turn after the tool-call transition from a re-entered step). Fix: the code agreement store plus engine-run recording.
- Styles corrects/talkative PUB-04/06/10: (c) mixed; not re-examined after the last fixes.

## Build times
| Build | Time | Notes |
|---|---|---|
| practice-a / practice-b / dev-raw (model, api_key) | 81 / 74 / 106 s | 0 repair rounds |
| dev-clean (model, login fallback) | 224 s | 0 repair rounds |
| `--reuse-config` rebuilds | 5–6 s each | no model stage |

## Commits
safe-1 = a8de9f0 (tag pushed). Phase C commits 37b8008 … (see `git log`); the final commit follows this report.


---
# FREEZE PHASE (final state)

**`freeze-1` tagged.** Decision rule met: plain A 10/10 (9/10 first pass; the single miss was an environment failure and passed on its one allowed re-run), plain B 3/3, and no wrong ledger on any call that completed normally. The code is commit `c46de85`; the agents were built from exactly that tree (verified: the live practice-a hooks and prompts equal the committed generator output; the only differences are `task_message` None vs "" that the platform fills in).

## Gate table (reps 1) vs safe-1 (a8de9f0 / Phase B baseline)
| Suite | safe-1 | freeze-1 | Notes |
|---|---|---|---|
| plain A | 10/10 | 10/10 | PUB-05 failed once (customer hung up during a 27 s turn, ended=customer-ended-call), passed on re-run |
| plain B | 3/3 | 3/3 | median slowest turn 21 s, worst 42 s (Freya slow) |
| abx A (19) | 19/19 | 18/19 | X01: ledger correct, judge verdict never arrived (no-verdict) |
| abx B (5) | 5/5 | 0/5 as run | 4 × customer-ended-call after 36-44 s turns (ENVIRONMENT); X24 ledger correct, judge: persuaded the loan after the job loss (behaviour defect, see open items). **Not re-run: out of time.** |
| v_raw (15) | 14/15 | not completed | run closed at the deadline (Freya latency) |
| v_clean (17) | 12/17 | not run | out of time |
| styles A (pieces, corrects, talkative, asks_back, in_words) | n/a (Phase B+: 6/4/4/9/8 of 10, reps 3) | not run | out of time |
| S1/S2 safety (reps 3) | n/a | rep 1 2/2 pass; rep 2 ledgers correct, judge verdict missing; rep 3 not completed | |

Honest summary: the gate that matters for the decision (plain A/B) holds. The Brief B extended suite and everything after it did NOT get a clean run, because Freya was 3-5x slower than normal (median slowest turn 21-61 s), so I cannot claim "at least as good as safe-1" for abx B, v_raw, v_clean or the styles. Those need a quiet-platform re-run.

## Safety net evidence
- Offline hook test: normal path sends nothing; hang-up with nothing recorded → no_promise/refused; after a promise → promise; after notes → the note rule.
- Live: PUB-05's customer hung up before verification finished and the ledger still got exactly one close (no_promise/refused). Limit: the net uses hint "done", so a hang-up BEFORE verification is closed as no_promise/refused rather than not_verified.

## Open items (not fixed in the freeze)
1. X24 / multi-product hardship: after the customer names a hardship for one product, the hardship step handled the other products with offers (and repeated the support offer). Ledger was right; the judge fails it. Fix: restrict the hardship step to the affected item and return to the offer engine for the others.
2. Safety net hint: choose the hint from the ledger/state (identity not verified → not_verified).
3. In-flight tool after end of call (X21: add_note after close_call when the customer hung up): needs the engine to stop queued writes after the end-of-call close.
4. Deterministic recording rewrite: cancelled by the architect.
5. Builder key out of credit: the login fallback works; repair rounds after a fallback session returned "Credit balance is too low" once (dev-raw at 09:26), which a clean rebuild avoided. Root cause not found.
