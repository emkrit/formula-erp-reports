"""
Compare CUSTDET2_claude.csv with the sample report, customer by customer.

A value counts as matching if it is equal, or if the sample shows the start of it
(the sample cuts long text). Anything else is a difference, split by whether the customer
was edited after the sample was saved. Differences go to analysis\\compare_rows.csv.
"""

import collections
import csv
import datetime as dt
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = r"D:\Em_Project\Sample report\CUSTDET2.CSV"
OURS = os.path.join(HERE, "..", "CUSTDET2_claude.csv")
SAMPLE_SAVED = dt.datetime(2026, 10, 7, 18, 40, 48)
COLS = ["name", "sname", "address", "tel", "fax", "status", "personty", "taxid", "creddate", "idcard",
        "acchart", "percont", "addrcont", "email", "website", "remlay", "remthai", "remeng", "group",
        "saleman", "credlimit", "credterm", "broffice", "branchno", "branchnm", "vattype", "unitcost",
        "no", "building", "moo", "soi", "road", "tambon", "amphur", "prov"]


def norm_sample(c, v):
    v = v.replace("\x02", "").strip()    # the report removes this stray control character
    if c == "creddate":
        return dt.datetime.strptime(v, "%d/%m/%Y").date().isoformat()
    if c == "credlimit":
        return f"{float(v):.2f}"
    if c == "credterm":
        return str(int(v.split()[0]))
    if c == "unitcost" and v == "()":
        return ""
    return v


def norm_ours(c, v):
    v = v.strip()
    if c == "credlimit":
        return f"{float(v):.2f}"
    if c == "credterm":
        return str(int(float(v)))
    return v


txt = open(SAMPLE, "rb").read().decode("cp874", errors="backslashreplace")
samp = {r["code"]: r for r in csv.DictReader(txt.split("\r\n")[:-1]) if r["code"]}
ours = {r["code"]: r for r in csv.DictReader(open(OURS, encoding="utf-8-sig"))}

gone = sorted(set(samp) - set(ours))
new = sorted(set(ours) - set(samp))
print(f"customers: sample {len(samp):,} | report {len(ours):,} | in both {len(set(samp) & set(ours)):,}")
print(f"in sample only: {len(gone)} | in report only: {len(new)}")

recoded = {}
for g in gone:
    for n in new:
        if (ours[n]["sname"] == samp[g]["sname"].strip()
                and ours[n]["creddate"] == norm_sample("creddate", samp[g]["creddate"])):
            recoded[g] = n
print("code changed (same short name and created date):", recoded)
print("in sample only, unexplained:", [g for g in gone if g not in recoded])

later = [n for n in new if n not in recoded.values()
         and ours[n]["creddate"] > SAMPLE_SAVED.date().isoformat()]
print(f"in report only, created after the sample: {len(later)} of {len(new) - len(recoded)}")
print("in report only, unexplained:",
      [n for n in new if n not in recoded.values() and n not in later])

both = [c for c in samp if c in ours]
print("sample order kept:", [c for c in samp if c in ours] == [c for c in ours if c in samp])

out, edited_customers, unedited_customers = [], set(), set()
print(f"\n{'column':10} {'equal':>6} {'cut':>5} {'diff, edited later':>19} {'diff, not edited':>17}")
for c in COLS:
    eq = cut = dl = dn = 0
    for k in both:
        s, o = norm_sample(c, samp[k][c]), norm_ours(c, ours[k][c])
        if s == o:
            eq += 1
        elif s and o.startswith(s):
            cut += 1
        else:
            is_later = dt.datetime.fromisoformat(ours[k]["lastupd"]) > SAMPLE_SAVED
            dl += is_later
            dn += not is_later
            (edited_customers if is_later else unedited_customers).add(k)
            out.append([k, c, s, o, ours[k]["lastupd"], "edited later" if is_later else "not edited"])
    print(f"{c:10} {eq:6} {cut:5} {dl:19} {dn:17}")

print(f"\ncustomers with a difference: edited later {len(edited_customers)}, "
      f"not edited {len(unedited_customers)}")
print(f"credit limit total: sample {sum(float(samp[k]['credlimit']) for k in both):,.2f} | "
      f"report {sum(float(ours[k]['credlimit']) for k in both):,.2f}")
with open(os.path.join(HERE, "compare_rows.csv"), "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh)
    w.writerow(["code", "column", "sample", "report", "lastupd", "why"])
    w.writerows(out)
print("\nnot edited, by column:", collections.Counter(r[1] for r in out if r[5] == "not edited").most_common())
for r in [r for r in out if r[5] == "not edited"][:40]:
    print("  ", r[0], r[1], "| sample", repr(r[2][:70]), "| report", repr(r[3][:70]))
