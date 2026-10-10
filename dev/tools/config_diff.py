"""Field-by-field diff of two configs (reproducibility check).   python3 dev/tools/config_diff.py a.config.json b.config.json"""
import json, sys


def flat(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from flat(v, f"{p}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from flat(v, f"{p}[{i}]")
    else:
        yield p, o


a, b = (dict(flat(json.load(open(x)))) for x in sys.argv[1:3])
keys = sorted(set(a) | set(b))
same = [k for k in keys if a.get(k, "<missing>") == b.get(k, "<missing>")]
diff = [k for k in keys if k not in same]
groups = {}
for k in diff:
    top = k.split(".")[1].split("[")[0]
    if top in ("flow",):
        top = ".".join(k.split(".")[1:4])
    groups.setdefault(top, []).append(k)
print(f"{len(keys)} leaf fields, {len(same)} identical, {len(diff)} different")
for g, ks in sorted(groups.items(), key=lambda x: -len(x[1])):
    print(f"  {g}: {len(ks)}")
for k in diff[:int(sys.argv[3]) if len(sys.argv) > 3 else 25]:
    print(f"~ {k}\n    A: {str(a.get(k, '<missing>'))[:140]}\n    B: {str(b.get(k, '<missing>'))[:140]}")
