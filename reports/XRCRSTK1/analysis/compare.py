"""
Compare XRCRSTK1_claude.csv with the sample report, product by product.
Differences go to analysis\\compare_rows.csv.
"""

import collections
import csv
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = r"D:\Em_Project\Sample report\XRCRSTK1.CSV"
OURS = os.path.join(HERE, "..", "XRCRSTK1_claude.csv")
ROW = re.compile(r'^"(.*)","(.*)",(-?[\d.]+),"(.*)",(-?[\d.]+),(-?[\d.]+),(\d),"(.*)"$')   # names can hold a bare "

samp = {}
for line in open(SAMPLE, "rb").read().decode("cp874").split("\r\n")[1:]:
    m = ROW.match(line)
    if m and m.group(7) == "1":
        g = m.groups()
        samp[g[0].strip()] = dict(name=g[1].strip(), unit=g[3].strip(), balance=float(g[2]), cost=float(g[4]), amt=float(g[5]))
rows = list(csv.DictReader(open(OURS, encoding="utf-8-sig")))
ours = {r["prodcode"]: r for r in rows}

both = [k for k in samp if k in ours]
print(f"products: sample {len(samp):,} | report {len(ours):,} | in both {len(both):,}")
print("only in sample:", sorted(set(samp) - set(ours)))
print("only in report:", sorted(set(ours) - set(samp)))
print("order kept:", [k for k in samp if k in ours] == [k for k in ours if k in samp])
print("name equal:", sum(ours[k]["prodname"] == samp[k]["name"] for k in both),
      "| unit equal:", sum(ours[k]["unit"] == samp[k]["unit"] for k in both))

out = []
for col, tol in (("balance", 0.005), ("cost", 0.005), ("amt", 0.015)):
    same = 0
    for k in both:
        if abs(float(ours[k][col]) - samp[k][col]) < tol:
            same += 1
        else:
            out.append([k, col, samp[k][col], ours[k][col]])
    print(f"{col:8} match {same:,} of {len(both):,} ({same / len(both):.1%})")

nz = [k for k in both if samp[k]["cost"]]
print(f"cost, products where the sample shows one: {len(nz):,}, exact "
      f"{sum(abs(float(ours[k]['cost']) - samp[k]['cost']) < 0.005 for k in nz):,}, within 1% "
      f"{sum(abs(float(ours[k]['cost']) - samp[k]['cost']) <= samp[k]['cost'] * 0.01 for k in nz):,}")
s_bal, o_bal = sum(samp[k]["balance"] for k in both), sum(float(ours[k]["balance"]) for k in both)
s_amt, o_amt = sum(samp[k]["amt"] for k in both), sum(float(ours[k]["amt"]) for k in both)
print(f"total balance: sample {s_bal:,.2f} | report {o_bal:,.2f}")
print(f"total value:   sample {s_amt:,.2f} | report {o_amt:,.2f} | gap {o_amt - s_amt:,.2f} ({(o_amt - s_amt) / s_amt:.1%})")
gaps = sorted(((float(ours[k]["amt"]) - samp[k]["amt"], k) for k in both), key=lambda g: -abs(g[0]))
print("largest value gaps (gap, product, name, sample balance @ cost, report balance @ cost):")
for g, k in gaps[:12]:
    print(f"  {g:>16,.2f} {k} {samp[k]['name'][:30]} | {samp[k]['balance']:,.2f} @ {samp[k]['cost']:,.2f} | "
          f"{float(ours[k]['balance']):,.2f} @ {float(ours[k]['cost']):,.2f}")
print("value gap by product type:", [(t, round(v)) for t, v in collections.Counter(
    {t: sum(float(ours[k]["amt"]) - samp[k]["amt"] for k in both if ours[k]["prodtype"] == t)
     for t in {ours[k]["prodtype"] for k in both}}).most_common()])
with open(os.path.join(HERE, "compare_rows.csv"), "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh)
    w.writerow(["prodcode", "column", "sample", "report"])
    w.writerows(out)
