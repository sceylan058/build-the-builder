# Architect report: Phase B (generalisation bench + honest baseline)

## Most important findings
1. **The builder generalises.** Both unseen briefs were built untouched, with no repair rounds:
   - V-CLEAN: 245 s, 12/17 cases.
   - V-RAW, from the directory: 94 s, 14/15 cases.
   - The lazy-copy check found the builder applied every changed rule it could express, including the V-RAW memo override, the effective-dated band switch, the cancelled holiday and the spoken names from the code list.
2. **Defect A — "today" when recording** (2 failures: PUB-01 in the runner check, VC-01). When the customer pays "today", the model moved to the record step, used the real clock (Sat 10 Oct), and the clamp moved that to Mon 12 Oct, a past date. The record step's prompt has no `{{today_facts}}`, and the record clamp has no minimum date. Generic fix in gen.py:
   - a `min: today` clamp for date arguments;
   - today's facts in every step that writes.
3. **Defect B — schema gap** (VC-14): `from_note` can only take the FIRST non-paid note. A brief with "last" (or any other order) cannot be expressed, and nothing warns about it. Fix: `from_note.order: first|last`, plus a check.py rule.
4. **Harness** (VC-10, VC-11): third-party calls kept the simulation open. The hard timeout (34 min) closed it before the judge ran, so these two have correct bank records but no verdict and are counted as FAIL. Fix: run third-party cases in a separate simulation, or wait for the judge after closing.
5. **Judge/agent strictness** (VR-02, VC-08): one extra offer counted because "can you pay today?" was asked again; one judge text says "all criteria met" with a fail verdict.

## Results (reps 1, untouched agents)
| Suite | Agent | Result |
|---|---|---|
| runner validation (PUB-01..03, kit scripts) | practice-a v16 | 2/3 (PUB-01: Defect A; PUB-02/03 match run_cases) |
| ab_extended (24 of the ~35 planned) | practice-a (19) / practice-b (5) | **24/24** |
| v_clean (17) | dev-clean, built by the rehearsal | 12/17 |
| v_raw (15) | dev-raw, built by the rehearsal | 14/15 |

Failures classified:
- VC-01: (b) generator — the "today" defect.
- VC-14: (b) schema cannot express the brief's rule (first-copied value).
- VC-08: (c) judge inconsistency.
- VC-10, VC-11: (d) harness timeout before judging; bank records were correct.
- VR-02: (c) agent re-asked "today" and the judge counted an extra offer.
- PUB-01 (runner validation): (b) Defect A.

## Build times (rehearsals)
| | prepare | write (model) | compile+check | dry-run | save | export | total | repair rounds |
|---|---|---|---|---|---|---|---|---|
| V-CLEAN | 0 s | 239 s | 0.5 s | 0.6 s | 3.8 s | 0.4 s | **245 s** | 0 |
| V-RAW (directory) | 0 s | 89.5 s | 0.5 s | 0.9 s | 2.3 s | 0.5 s | **94 s** | 0 |

## Top root causes and recommended generic fixes
1. A date argument can be in the past, and the record step does not know today (2 cases). Fix: `clamp.min = "today"` in RECORD_PRE, and `{{today_facts}}` in the record prompt.
2. Outcome rules cannot express "last" / any order (1 case). Fix: `from_note.order`.
3. A slow third-party simulation blocks judging (2 unjudged). Fix: in the harness, split those cases or wait for the judge.
4. The model re-asks "pay today?" for one product (1 case). Fix: a prompt rule exists; make the summary line the only "today" ask.
5. Judge inconsistency (1 case): use `--reps 3`.

## What was built
- `dev/run_dev.py`: case runner on borrowed sessions; retries, adoption of a timed-out create, hard timeout, per-family summary, `dev/results/log.jsonl`.
- `dev/oracle.py`: independent rules, 12/12 anchors including the four given ones.
- Case files: `dev/cases/ab_extended.json` (24), `v_clean.json` (17), `v_raw.json` (15), each made by a generator script with oracle dates and a `why` for each case.
- `dev/briefs/v-clean/` (14 rule changes) and `dev/briefs/v-raw/` (mail, policy, memo, codes; 5 changes).
- `dev/lazy_copy.py` with results in `dev/results/lazy_copy.md`.

## Not done (budget)
- The independent subagent cross-check of the expected ledgers.
- About 11 ab_extended cases: below-floor variants, a vague period twice, a change after recording, scam + robot questions, illness naming a date, a dispute on a closed card, not wanting to talk twice, a create_promise fault on another day, an angry caller, a spouse demanding the balance, a discount threat.
- `--reps` > 1, and Phase B+ (styles).
