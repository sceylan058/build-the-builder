"""Fail if practice-case specifics (names, birth dates, phone digits, amounts, card digits, script phrases) appear in builder/.
    python3 dev/tests/practice_leak_scan.py"""
import json, pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
cases = json.load(open(ROOT / "public-test-set.json"))
brief_text = " ".join(p.read_text() for p in (ROOT / "briefs").glob("brief-*.md")).lower()
needles = set()
for c in cases:
    v = c["variables"]
    needles |= {v["first_name"], v["last_name"]}
    for k, x in c["identity"].items():
        needles.add(str(x))
    for p in c["products"]:
        for k in ("past_due", "minimum_payment", "instalment_amount"):
            if k in p:
                needles |= {f"{p[k]:.2f}", f"{p[k]:,.2f}"}
        if p.get("card_last4"):
            needles.add(p["card_last4"])
    for q in re.findall(r"'([^']{6,})'", c["script"]):
        needles.add(q)
# values the briefs themselves contain are allowed (they reach the builder through the brief at run time)
needles = {n for n in needles if n.lower() not in brief_text and len(n) >= 4}
hits = []
for f in sorted((ROOT / "builder").rglob("*")):
    if f.is_file() and f.suffix in (".py", ".md", ".json", ".txt"):
        t = f.read_text(errors="replace")
        for n in needles:
            if re.search(r"(?<![\w.])" + re.escape(n) + r"(?![\w])", t):
                hits.append(f"{f.relative_to(ROOT)}: {n!r}")
print("\n".join(hits) or f"practice leak scan: clean ({len(needles)} needles)")
sys.exit(1 if hits else 0)
