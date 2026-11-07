"""
Compare PDISITM1_claude.csv with the sample report.

Checks ledger lines, debit and credit, running balance, descriptions, bank documents and
each account's period totals. Differences go to analysis\\compare_rows.csv.
"""

import collections
import csv
import datetime as dt
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = r"D:\Em_Project\Sample report\PDISITM1.CSV"
OURS = os.path.join(HERE, "..", "PDISITM1_claude.csv")
SUMMARY = ("ยอดยกไป", "ยอดประจำงวด", "ยอดรวม")
norm = lambda s: re.sub(r"\s+", "", s or "")


def iso(d):
    return dt.datetime.strptime(d, "%d/%m/%Y").date().isoformat() if d.strip() != "/  /" else ""


# ---- sample
txt = open(SAMPLE, "rb").read().decode("cp874")
s_lines, s_docs, s_period, s_bank_totals, cur = [], [], {}, 0, None
for r in csv.DictReader(txt.split("\r\n")[:-1]):
    if r["subhdlevel"] != "1":
        continue
    d = r["desc"].strip()
    if r["code"]:
        cur = {"acct": r["gacchart"], "code": r["code"], "date": iso(r["date"]), "dr": float(r["dramt"]),
               "cr": float(r["cramt"]), "bal": float(r["balamt"]), "post": r["poststep"], "desc": [r["desc"]]}
        s_lines.append(cur)
    elif r["gchqno"].strip().startswith("->"):
        s_bank_totals += 1
    elif r["gbankdoc"].strip():
        s_docs.append((r["gacchart"], cur["code"], r["gbankdoc"].strip(), r["gchqno"].strip(),
                       r["gchqstat"].strip(), iso(r["gchqdate"]), round(float(r["gchqamt"]), 2)))
    elif d == "ยอดประจำงวด":
        s_period[r["gacchart"]] = (float(r["dramt"]), float(r["cramt"]), float(r["balamt"]))
    elif d and d not in SUMMARY:
        cur["desc"].append(r["desc"])

# ---- report
ours = list(csv.DictReader(open(OURS, encoding="utf-8-sig")))
o_lines = [r for r in ours if r["rowtype"] == "LINE"]
o_docs = [r for r in ours if r["rowtype"] == "BANK"]
print(f"rows: report {len(ours):,} = {len(o_lines):,} ledger lines + {len(o_docs):,} bank rows")

key_s = lambda l: (l["acct"], l["code"], round(l["dr"] - l["cr"], 2))
key_o = lambda r: (r["gacchart"], r["code"], round(float(r["dramt"]) - float(r["cramt"]), 2))
S, O = collections.Counter(map(key_s, s_lines)), collections.Counter(map(key_o, o_lines))
print(f"\nLEDGER LINES  sample {sum(S.values()):,} | report {sum(O.values()):,} | match {sum((S & O).values()):,}")
print(f"documents     sample {len({l['code'] for l in s_lines}):,} | report {len({r['code'] for r in o_lines}):,}")
print(f"accounts      sample {len({l['acct'] for l in s_lines})} | report {len({r['gacchart'] for r in o_lines})}")
print("only in sample:", sorted((S - O).elements()))
print("only in report:", sorted((O - S).elements()))
print(f"debit   sample {sum(l['dr'] for l in s_lines):,.2f} | report {sum(float(r['dramt']) for r in o_lines):,.2f}")
print(f"credit  sample {sum(l['cr'] for l in s_lines):,.2f} | report {sum(float(r['cramt']) for r in o_lines):,.2f}")

# ---- line by line, in order: date, posting step, description, running balance
same_docs = {k[1] for k in (S & O)} - {k[1] for k in (S - O)} - {k[1] for k in (O - S)}
o_by = collections.defaultdict(list)
for r in o_lines:
    o_by[key_o(r)].append(r)
counts, out = collections.Counter(), []
for l in s_lines:
    m = o_by.get(key_s(l))
    if not m:
        continue
    r = m.pop(0)
    counts["compared"] += 1
    counts["date ok"] += r["date"] == l["date"]
    counts["poststep ok"] += r["poststep"] == l["post"]
    pos, ok = 0, True                 # the sample wraps and cuts long text, so look for each printed piece in turn
    full = norm(r["desc"])
    for piece in l["desc"]:
        at = full.find(norm(piece), pos)
        ok = ok and at >= 0
        pos = at + len(norm(piece)) if at >= 0 else pos
    counts["desc ok"] += ok
    counts["desc identical"] += norm("".join(l["desc"])) == full
    if not ok:
        out.append([l["acct"], l["code"], "desc", " / ".join(l["desc"]), r["desc"]])
    if abs(float(r["balamt"]) - l["bal"]) < 0.005:
        counts["balance ok"] += 1
    else:
        out.append([l["acct"], l["code"], "balance", l["bal"], r["balamt"]])
print("\nLINE DETAIL", dict(counts))
changed = {k[0] for k in (S - O)} | {k[0] for k in (O - S)}
bal_diff = [x for x in out if x[2] == "balance"]
print(f"balance differences: {len(bal_diff)}, in accounts changed since the sample: "
      f"{sum(x[0] in changed for x in bal_diff)}, elsewhere: {sum(x[0] not in changed for x in bal_diff)}")
print("  elsewhere:", [x for x in bal_diff if x[0] not in changed][:8])

# ---- bank documents
SD = collections.Counter(s_docs)
OD = collections.Counter((r["gacchart"], r["code"], r["gbankdoc"], r["gchqno"], r["gchqstat"], r["gchqdate"],
                          round(float(r["gchqamt"]), 2)) for r in o_docs)
print(f"\nBANK ROWS  sample {sum(SD.values()):,} | report {sum(OD.values()):,} | match {sum((SD & OD).values()):,}")
print(f"bank total rows in the sample, not kept: {s_bank_totals}")
only_s, only_o = list((SD - OD).elements()), list((OD - SD).elements())
print("only in sample:", len(only_s), only_s[:12])
print("only in report:", len(only_o), only_o[:12])
print("only in sample, by type", collections.Counter(x[2] for x in only_s).most_common())
print("only in report, by type", collections.Counter(x[2] for x in only_o).most_common())

# ---- each account's totals
dr, cr = collections.Counter(), collections.Counter()
for r in o_lines:
    dr[r["gacchart"]] += float(r["dramt"])
    cr[r["gacchart"]] += float(r["cramt"])
ok = [a for a, v in s_period.items() if abs(dr[a] - v[0]) < 0.005 and abs(cr[a] - v[1]) < 0.005]
print(f"\nACCOUNT TOTALS  sample {len(s_period)} accounts | match {len(ok)}")
print("different:", [(a, s_period[a][:2], (round(dr[a], 2), round(cr[a], 2))) for a in s_period if a not in ok])

with open(os.path.join(HERE, "compare_rows.csv"), "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh)
    w.writerow(["account", "code", "column", "sample", "report"])
    w.writerows(out)
    w.writerows([list(x[:2]) + ["bank, only in sample", str(x[2:]), ""] for x in only_s])
    w.writerows([list(x[:2]) + ["bank, only in report", "", str(x[2:])] for x in only_o])
print("\nother differences:", [x for x in out if x[2] != "balance"][:8])
