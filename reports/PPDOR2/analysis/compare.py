"""
Compare analysis\\PPDOR2_claude.csv (run with --sample-range) with the sample report, line by line.
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
SAMPLE = r"D:\Em_Project\Sample report\PPDOR2.CSV"
OURS = os.path.join(HERE, "PPDOR2_claude.csv")
FIELD = re.compile(r'(?:^|,)("(?:.*?)"(?=,|$)|[^,"]*)')   # names can hold a bare "


def split(line):
    return [f[1:-1] if f.startswith('"') and len(f) > 1 else f for f in FIELD.findall(line)]


def iso(s):
    s = s.strip()
    return "" if s in ("/  /", "") else dt.datetime.strptime(s, "%d/%m/%Y").date().isoformat()


def num(s):
    return float(s.replace(",", "")) if s else 0.0


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

s_rows = [r for r in rows if r["subhdlevel"] == "1" and r["refno"].strip()]
s_subs = [r for r in rows if r["subhdlevel"] == "1" and not r["refno"].strip()]
print("sample lines", len(s_rows), "| product subtotals", len(s_subs), "| distinct products", len({r["gprod"] for r in s_rows}),
      "| documents", len({r["refno"] for r in s_rows}))
print("unused values:", collections.Counter(r["unused"].strip() for r in rows).most_common(4))
print("code prefix:", collections.Counter(r["code"][:7] for r in s_rows).most_common(5))
print("required dates:", min(iso(r["recedate"]) for r in s_rows), max(iso(r["recedate"]) for r in s_rows))
print("sample total back qty %.2f, amount %.2f; subtotals amount %.2f" % (
    sum(num(r["backqty"]) for r in s_rows), sum(num(r["inamt"]) for r in s_rows), sum(num(r["inamt"]) for r in s_subs)))

ours = list(csv.DictReader(open(OURS, encoding="utf-8-sig")))
print("report lines", len(ours), "| documents", len({r["refno"] for r in ours}), "| amount %.2f" % sum(num(r["inamt"]) for r in ours))


def key(prod, ref, date, qty, price):
    return (prod.strip(), ref.strip(), date, round(num(qty), 2), round(num(price), 4))


A = collections.defaultdict(list)
for r in s_rows:
    A[(r["gprod"].strip(), r["refno"].strip(), iso(r["recedate"]), round(num(r["orderqty"]), 2))].append(r)
B = collections.defaultdict(list)
for r in ours:
    B[(r["gprod"], r["refno"], r["recedate"], round(num(r["orderqty"]), 2))].append(r)

only_s = [k for k in A if len(A[k]) > len(B.get(k, []))]
only_o = [k for k in B if len(B[k]) > len(A.get(k, []))]
print("line keys only in sample:", len(only_s), only_s[:15])
print("line keys only in report:", len(only_o))
print("  report-only by line step / doc step:", collections.Counter((B[k][0]["linestep"], B[k][0]["docstep"]) for k in only_o).most_common(8))
print("  examples:", [(k, B[k][0]["backqty"], B[k][0]["docdate"], B[k][0]["qcsect"]) for k in only_o[:12]])

out = []
cols = (("code", "t"), ("coorname", "p"), ("qcsect", "t"), ("backqty", "n"), ("umname", "t"), ("inprice", "n"), ("inamt", "n"))
tally = collections.Counter()
n_pairs = 0
for k in A:
    for a, b in zip(sorted(A[k], key=lambda r: num(r["backqty"])), sorted(B.get(k, []), key=lambda r: num(r["backqty"]))):
        n_pairs += 1
        for c, kind in cols:
            x, y = a[c].strip(), b[c].strip()
            ok = abs(num(x) - num(y)) < 0.006 if kind == "n" else y.startswith(x) if kind == "p" else x == y
            tally[c] += ok
            if not ok:
                out.append([*map(str, k), c, x, y])
print(f"paired lines {n_pairs:,}:", {c: tally[c] for c, _ in cols})
keys_s = [(r["gprod"].strip(), r["refno"].strip()) for r in s_rows]
keys_o = [(r["gprod"], r["refno"]) for r in ours if (r["gprod"], r["refno"]) in set(keys_s)]
print("row order kept:", keys_s == keys_o)
print("name equals sample's product heading checked separately; differences by column:", collections.Counter(r[-3] for r in out).most_common())
shown = collections.Counter()
for r in out:
    shown[r[-3]] += 1
    if shown[r[-3]] <= 8:
        print("  ", r)
with open(os.path.join(HERE, "compare_rows.csv"), "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh)
    w.writerow(["prodcode", "refno", "required_date", "orderqty", "column", "sample", "report"])
    w.writerows(out)
