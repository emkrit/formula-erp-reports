"""
Compare PBUYORD_claude.csv with the sample report at document, line and delivery level.
Differences go to analysis\\compare_rows.csv.
"""

import collections
import csv
import datetime as dt
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = r"D:\Em_Project\Sample report\PBUYORD.CSV"
OURS = os.path.join(HERE, "..", "PBUYORD_claude.csv")
FIELD = re.compile(r'(?:^|,)("(?:.*?)"(?=,|$)|[^,"]*)')   # names can hold a bare "


def split(line):
    return [f[1:-1] if f.startswith('"') and len(f) > 1 else f for f in FIELD.findall(line)]


def iso(s):
    s = s.strip()
    return "" if s in ("/  /", "") else dt.datetime.strptime(s, "%d/%m/%Y").date().isoformat()


def num(s):
    return float(s.replace(",", "")) if s not in ("", None) else 0.0


lines = open(SAMPLE, "rb").read().decode("cp874").split("\r\n")
head = split(lines[0])
rows, bad = [], 0
for ln in lines[1:]:
    if ln:
        f = split(ln)
        if len(f) == len(head):
            rows.append(dict(zip(head, f)))
        else:
            bad += 1
print(f"sample rows {len(rows):,}, not parsed {bad}")

# ---- sample by level
s_docs, s_lines, s_inv, s_back = {}, {}, collections.defaultdict(list), {}
for r in rows:
    if r["no"] == "0":
        continue
    d = (r["refno"].strip(), iso(r["date"]))
    if r["subhdlevel"] == "1":
        s_docs[d] = r
    elif r["subhdlevel"] == "2":
        s_lines[d + (int(r["run"]),)] = r
    elif r["subhdlevel"] == "3":
        k = d + (int(r["run"]),)
        if r["invrefno"].strip():
            s_inv[k].append(r)
        else:
            s_back[k] = r

# ---- report by level
ours = list(csv.DictReader(open(OURS, encoding="utf-8-sig")))
o_docs, o_lines, o_inv = {}, {}, collections.defaultdict(list)
for r in ours:
    d = (r["refno"], r["date"])
    o_docs.setdefault(d, r)
    if r["run"]:
        k = d + (int(float(r["run"])),)
        o_lines.setdefault(k, r)
        if r["invrefno"]:
            o_inv[k].append(r)

out = []


def diff(level, key, col, a, b):
    out.append([level, *key, col, a, b])


print(f"report rows {len(ours):,} | documents {len(o_docs):,} | lines {len(o_lines):,} | deliveries {sum(map(len, o_inv.values())):,}")
print(f"sample        documents {len(s_docs):,} | lines {len(s_lines):,} | deliveries {sum(map(len, s_inv.values())):,}")
print("documents only in sample:", sorted(set(s_docs) - set(o_docs)))
print("documents only in report:", sorted(set(o_docs) - set(s_docs)))
both = [k for k in s_docs if k in o_docs]
print("document order kept:", [k for k in s_docs if k in o_docs] == [k for k in o_docs if k in s_docs])

TEXT = ("ab", "coorcode", "sectcode2", "depcode")
NUMS = ("no", "amt", "discamt", "amtbfvat", "vat", "totamt", "depamt")
for c in TEXT + NUMS + ("coorname", "sectname"):
    same = 0
    for k in both:
        a, b = s_docs[k][c].strip(), o_docs[k][c].strip()
        if c in NUMS:
            ok = abs(num(a) - num(b)) < 0.006
        elif c in ("coorname", "sectname"):
            ok = b.startswith(a)
        else:
            ok = a == b
        same += ok
        if not ok:
            diff("doc", k, c, a, b)
    print(f"  doc  {c:10} {same:,} of {len(both):,}")
kept = [k for k in both if "C" not in s_docs[k]["ab"]]
for c in ("amt", "amtbfvat", "vat", "totamt"):
    print(f"  total excl. cancelled {c:9} sample {sum(num(s_docs[k][c]) for k in kept):,.2f} | report {sum(num(o_docs[k][c]) for k in kept):,.2f}")

lk = [k for k in s_lines if k in o_lines]
print("lines only in sample:", len(set(s_lines) - set(o_lines)), sorted(set(s_lines) - set(o_lines))[:5])
in_scope = {k for k in o_lines if k[:2] in s_docs}
print("lines only in report:", len(in_scope - set(s_lines)), sorted(in_scope - set(s_lines))[:5])
for c, kind in (("prodtype", "t"), ("prodcode", "t"), ("prodname", "p"), ("prodprice", "n"), ("itemdisc", "t"),
                ("qty", "n"), ("unit", "t"), ("stdqty", "n"), ("stdunit", "t"), ("amtitem", "n"), ("duedate2", "d")):
    same = 0
    for k in lk:
        a, b = s_lines[k][c].strip(), o_lines[k][c].strip()
        ok = (abs(num(a) - num(b)) < 0.006 if kind == "n" else iso(a) == b if kind == "d"
              else b.startswith(a) if kind == "p" else a == b)
        same += ok
        if not ok:
            diff("line", k, c, a, b)
    print(f"  line {c:10} {same:,} of {len(lk):,}")

# ---- outstanding: bracket rows against bakmsg / bakstd
same = 0
bk = [k for k in s_back if k in o_lines]
for k in bk:
    a = s_back[k]["invunit"].strip("[] "), s_back[k]["invstdunit"].strip("[] ")
    b = o_lines[k]["bakmsg"], o_lines[k]["bakstd"]
    ok = abs(num(a[0]) - num(b[0])) < 0.006 and abs(num(a[1]) - num(b[1])) < 0.006
    same += ok
    if not ok:
        diff("outstanding", k, "bak", "|".join(a), "|".join(b))
print(f"  outstanding rows match bakmsg/bakstd: {same:,} of {len(bk):,}")

# ---- deliveries: same documents in the same order on each line
DELIV = (("invrefno", "t"), ("invdate", "d"), ("invprice", "n"), ("invqty", "n"), ("invunit", "t"), ("invqtystd", "n"), ("invdisc", "x"))
same_set = same_order = extra = missing = 0
tally = collections.Counter()
for k in lk:
    a, b = s_inv.get(k, []), o_inv.get(k, [])
    if [r["invrefno"].strip() for r in a] == [r["invrefno"] for r in b]:
        same_order += 1
    sa, sb = collections.Counter(r["invrefno"].strip() for r in a), collections.Counter(r["invrefno"] for r in b)
    if sa == sb:
        same_set += 1
    else:
        missing += sum((sa - sb).values())
        extra += sum((sb - sa).values())
        diff("delivery", k, "invrefno", "|".join(sorted(sa.elements())), "|".join(sorted(sb.elements())))
    pool = collections.defaultdict(list)
    for r in b:
        pool[r["invrefno"]].append(r)
    for r in a:
        ref = r["invrefno"].strip()
        if not pool[ref]:
            continue
        same_qty = [p for p in pool[ref] if abs(num(p["invqty"]) - num(r["invqty"])) < 0.006]
        o = same_qty[0] if same_qty else pool[ref][0]
        pool[ref].remove(o)
        tally["pairs"] += 1
        for c, kind in DELIV:
            x, y = r[c].strip(), o[c].strip()
            ok = (abs(num(x) - num(y)) < 0.006 if kind == "n" else iso(x) == y if kind == "d"
                  else y in x if kind == "x" else x == y)
            tally[c] += ok
            if not ok:
                diff("delivery", k + (ref,), c, x, y)
print(f"  lines with the same delivery documents {same_set:,} of {len(lk):,}, also in the same order {same_order:,}")
print(f"  delivery rows only in sample {missing:,}, only in report {extra:,}")
print(f"  delivery pairs {tally['pairs']:,}:", {c: tally[c] for c, _ in DELIV})

with open(os.path.join(HERE, "compare_rows.csv"), "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh)
    w.writerow(["level", "key", "column", "sample", "report"])
    w.writerows([[r[0], " ".join(map(str, r[1:-3])), *r[-3:]] for r in out])
print("differences by level and column:", collections.Counter((r[0], r[-3]) for r in out).most_common(30))
shown = collections.Counter()
for r in out:
    shown[(r[0], r[-3])] += 1
    if shown[(r[0], r[-3])] <= 6:
        print("  ", r)
