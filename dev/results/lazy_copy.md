# Lazy-copy detector (B5.4)

V-CLEAN rehearsal (`dev/lazy_copy.py work/dev-clean/final.config.json clean`): 9/10 values match the brief.
- Correct: holidays incl. 16 Oct and without 26 Oct; tiers 1–10/10th/1 and 11–45/5th/2; attempt 1 on the 3rd business day; callback 09:00–17:00; phone question first; two wrong answers end the check; car loan floor = half; new after-promise sentence; name question with first and last name.
- Not correct: the close reason from the LAST non-paid note. The schema cannot express "last" (`from_note` always takes the first), so the value comes from the example by necessity. This is a schema gap, not a misreading.

V-RAW rehearsal (directory input), checked by hand:
- All correct: the effective-dated band switch (tier expression using `today >= 2026-10-19`); the memo's early deadline n=10 overrides the policy's 12; the cancelled 11 Nov holiday is dropped; spoken product names from the code list; callback 10:00–19:00; "debt" is in `forbidden_before_verification`.
- Limit: check.py's spoken lint covers only fixed lines before verification. The mail's ban "never say debt at any point" relies on the prompts.
