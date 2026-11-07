#!/usr/bin/env python3
"""
Compare Sample report\\XRBUYOR1.CSV with db_q1_lines.csv. Reads local files only.

- Re-parses the sample: Formula leaves the " inch mark unescaped inside text
  fields, so a normal CSV reader misreads those rows. The layout is fixed, so a
  regex with the known field types splits every row safely.
- Writes sample_XRBUYOR1_cleaned.csv and compare_rows.csv (one row per sample
  row and per unmatched db row), and prints the summary used in differences.md.
"""

import csv
import os
import re
import sys
from collections import Counter, defaultdict

HERE   = os.path.dirname(os.path.abspath(__file__))
SAMPLE = r"D:\Em_Project\Sample report\XRBUYOR1.CSV"
DBQ1   = os.path.join(HERE, "db_q1_lines.csv")
DBQ2   = os.path.join(HERE, "db_q2_receipts.csv")
SAMPLE_SAVED = "2026-09-01 14:26:50"

COLS = ["date", "refno", "code", "coorcode", "prodcode", "prodname", "prodprice",
        "itemdisc", "qty", "unit", "totamt", "refnogb", "qtygb", "unreceiqty",
        "unreceiamt", "duedate2", "sectcode", "sectname", "subhdlevel", "subheadmsg"]
D = r"(\d\d/\d\d/\d{4}|/  /)"
N = r"(-?[\d.]+)"
Q = r'"(.*?)"'
ROW = re.compile("^" + ",".join([D, Q, Q, Q, Q, r'"(.*)"', N, Q, N, Q, N, Q, N, N, N, D,
                                  Q, r'"(.*)"', r"(\d+)", r'"(.*)"']) + "$")


def iso(d):
    return "" if d.startswith("/") else f"{d[6:10]}-{d[3:5]}-{d[0:2]}"


def num(s):
    return round(float(s or 0), 2)


def load_sample():
    rows = []
    with open(SAMPLE, encoding="cp874") as fh:
        next(fh)
        for ln, line in enumerate(fh, 2):
            m = ROW.match(line.rstrip("\r\n"))
            if not m:
                sys.exit(f"sample line {ln} did not parse:\n{line}")
            r = dict(zip(COLS, m.groups()))
            if r["subhdlevel"] != "1":
                continue
            r["date"], r["duedate2"] = iso(r["date"]), iso(r["duedate2"])
            r["line"] = ln
            rows.append(r)
    with open(os.path.join(HERE, "sample_XRBUYOR1_cleaned.csv"), "w", newline="",
              encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["line"] + COLS[:-2])
        w.writeheader()
        w.writerows({k: r[k] for k in ["line"] + COLS[:-2]} for r in rows)
    return rows


def load_db():
    with open(DBQ1, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def key(r):
    return (r["prodcode"].strip(), num(r["qty"]), num(r["prodprice"]))


def match(sample, db):
    """Pair sample rows with db lines of the same PO. Returns (pairs, s_only, d_only)."""
    s_by = defaultdict(list)
    for r in sample:
        s_by[r["code"].strip()].append(r)
    d_by = defaultdict(list)
    for r in db:
        d_by[r["code"].strip()].append(r)

    pairs, s_only, d_only = [], [], []
    for code in sorted(set(s_by) | set(d_by)):
        srows, drows = list(s_by.get(code, [])), list(d_by.get(code, []))
        # 1) exact (product, qty, price) in order  2) leftovers by position
        for s in list(srows):
            for d in drows:
                if key(d) == key(s):
                    pairs.append((s, d, "exact")); srows.remove(s); drows.remove(d)
                    break
        while srows and drows:
            pairs.append((srows.pop(0), drows.pop(0), "changed"))
        s_only += srows
        d_only += drows
    return pairs, s_only, d_only


def main():
    sample, db = load_sample(), load_db()
    print(f"sample rows: {len(sample):,}   db rows: {len(db):,} "
          f"(cancelled {sum(r['FCSTAT'] == 'C' for r in db)})")
    pairs, s_only, d_only = match(sample, db)

    print(f"matched: {len(pairs):,} (exact {sum(p[2] == 'exact' for p in pairs):,}, "
          f"same PO but product/qty/price changed {sum(p[2] == 'changed' for p in pairs):,})")
    print(f"sample only: {len(s_only):,}   db only: {len(d_only):,}")

    # PO lines with a receiving document dated, or linked, after the sample was saved
    late_rec = set()
    with open(DBQ2, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["rec_date"] > SAMPLE_SAVED[:10] or r["linked"] > SAMPLE_SAVED:
                late_rec.add((r["code"], r["po_seq"]))

    def late(d):
        """Line edited, or received, after the sample was saved."""
        return (max(d["h_lastupd"], d["i_lastupd"]) > SAMPLE_SAVED
                or (d["code"], d["FCSEQ"]) in late_rec)

    # --- report column = db column? -------------------------------------------
    checks = {
        "date":       lambda s, d: s["date"] == d["date"],
        "refno":      lambda s, d: s["refno"].strip() == d["refno"],
        "coorcode":   lambda s, d: s["coorcode"].strip() == d["coorcode"],
        "prodname":   lambda s, d: s["prodname"].strip() == d["prodname"],
        "itemdisc":   lambda s, d: s["itemdisc"].strip() == d["itemdisc"],
        "unit":       lambda s, d: s["unit"].strip() == d["unit"],
        "totamt":     lambda s, d: num(s["totamt"]) == num(d["totamt"]),
        "refnogb":    lambda s, d: s["refnogb"].strip() == d["refnogb"],
        "qtygb":      lambda s, d: num(s["qtygb"]) == num(d["qtygb"]),
        "unreceiqty": lambda s, d: num(s["unreceiqty"]) == num(d["unreceiqty"]),
        "unreceiamt": lambda s, d: num(s["unreceiamt"]) == num(d["unreceiamt"]),
        "duedate2":   lambda s, d: s["duedate2"] == d["duedate2"],
        "sectcode":   lambda s, d: s["sectcode"].strip() == d["sectcode"],
        "sectname":   lambda s, d: s["sectname"].strip() == d["sectname"],
    }
    exact = [(s, d) for s, d, k in pairs if k == "exact"]
    print(f"\nfield agreement on {len(exact):,} exact matches "
          f"(differences split: changed after the sample / not explained):")
    unexplained = {}
    for f, ok in checks.items():
        bad = [(s, d) for s, d in exact if not ok(s, d)]
        unexplained[f] = [(s, d) for s, d in bad if not late(d)]
        print(f"  {f:11} {len(exact) - len(bad):6,} same   {len(bad) - len(unexplained[f]):5,} later   "
              f"{len(unexplained[f]):5,} unexplained")

    for f, rows in unexplained.items():
        for s, d in rows[:5]:
            print(f"    {f}: PO {d['code']} line {d['FCSEQ']}  sample={s[f].strip()!r}  db={d[f]!r}")

    print(f"\ncancelled PO lines in the sample: {sum(d['FCSTAT'] == 'C' for s, d, k in pairs):,}")
    print(f"db-only rows: dated after 01/09/2026 {sum(r['date'] > '2026-09-01' for r in d_only):,}, "
          f"edited after sample {sum(late(r) for r in d_only):,}, other {sum(not late(r) for r in d_only):,}")
    for r in [r for r in d_only if not late(r)][:10]:
        print(f"    db only: PO {r['code']} {r['refno']} line {r['FCSEQ']} {r['date']} {r['prodcode']}")
    for s in s_only:
        print(f"    sample only: line {s['line']} PO {s['code']} {s['refno']} {s['prodcode']} qty {s['qty']}")

    # --- detail file ------------------------------------------------------------
    out = os.path.join(HERE, "compare_rows.csv")
    with open(out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["status", "sample_line", "code", "refno", "date", "prodcode_sample", "prodcode_db",
                    "qty_sample", "qty_db", "price_sample", "price_db", "totamt_sample", "totamt_db",
                    "refnogb_sample", "refnogb_db", "qtygb_sample", "qtygb_db",
                    "unreceiqty_sample", "unreceiqty_db", "fcstat_db", "changed_after_sample", "diff_fields"])
        for s, d, k in pairs:
            diffs = [f for f, ok in checks.items() if not ok(s, d)]
            w.writerow([k, s["line"], d["code"], d["refno"], d["date"], s["prodcode"], d["prodcode"],
                        s["qty"], d["qty"], s["prodprice"], d["prodprice"], s["totamt"], d["totamt"],
                        s["refnogb"], d["refnogb"], s["qtygb"], d["qtygb"],
                        s["unreceiqty"], d["unreceiqty"], d["FCSTAT"], late(d), " ".join(diffs)])
        for s in s_only:
            w.writerow(["sample_only", s["line"], s["code"], s["refno"], s["date"], s["prodcode"], "",
                        s["qty"], "", s["prodprice"], "", s["totamt"], "", s["refnogb"], "", s["qtygb"], "",
                        s["unreceiqty"], "", "", "", ""])
        for d in d_only:
            w.writerow(["db_only", "", d["code"], d["refno"], d["date"], "", d["prodcode"],
                        "", d["qty"], "", d["prodprice"], "", d["totamt"], "", d["refnogb"], "", d["qtygb"],
                        "", d["unreceiqty"], d["FCSTAT"], late(d), ""])
    print(f"\ndetail -> {out}")


if __name__ == "__main__":
    main()
