#!/usr/bin/env python3
"""
Daily XRCRSTK1 (stock balance by product, all warehouses of the head office, as of today).

1. Runs Q1, Q2 and Q3 of xrcrstk1.sql (SELECT only, READ UNCOMMITTED).
2. Writes  D:\\Em_Project\\reports\\XRCRSTK1\\XRCRSTK1_claude.csv, replacing the previous file.
3. Uploads the file to Google Drive with rclone, replacing the previous file, if it is
   set up (UPLOAD_REMOTE below); otherwise the upload is skipped and logged.

Exit code 0 = OK, 1 = failed (Task Scheduler shows it as "Last Run Result").
Usage:  python daily_xrcrstk1.py              (normal daily run)
        python daily_xrcrstk1.py --no-upload  (local only, e.g. for testing)
"""

import collections
import csv
import datetime as dt
import decimal
import logging
import os
import re
import subprocess
import sys

import pyodbc

sys.path.insert(0, r"D:\Em_Project\reports\common")
from formula_db import CONN_STR, FORBIDDEN, fix_text

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HERE          = os.path.dirname(os.path.abspath(__file__))
SQL_PATH      = os.path.join(HERE, "xrcrstk1.sql")
OUT_ROOT      = HERE
CSV_NAME      = "XRCRSTK1_claude.csv"    # same name every run, so the new file replaces the old one
RCLONE        = r"D:\Em_Project\tools\rclone\rclone.exe"
UPLOAD_REMOTE = "gdrive:Formula Reports/XRCRSTK1"   # rclone remote:path; "" disables upload

# Report columns (Formula's names), then extras that make the file usable on its own.
# Left out: subhdlevel and subheadmsg (print layout).
REPORT_COLS = ["prodcode", "prodname", "balance", "unit", "cost", "amt"]
EXTRA_COLS  = ["prodtype", "prodtypename", "asofdate"]


def queries():
    """Q1, Q2 and Q3 from xrcrstk1.sql with the date turned into a parameter."""
    sql = open(SQL_PATH, encoding="utf-8").read()
    code = re.sub(r"--[^\n]*", "", re.sub(r"/\*.*?\*/", "", sql, flags=re.S))
    bad = FORBIDDEN.search(code)
    if bad:
        raise SystemExit(f"Refusing to run: found '{bad.group(0)}' in {SQL_PATH}")
    parts = re.split(r"/\* ---------- Q\d\..*?\*/", sql, flags=re.S)[1:]
    return ["SET NOCOUNT ON;\nDECLARE @d date = ?;\n" + q for q in parts]


def value(v):
    """SQL value -> Python value for CSV."""
    if isinstance(v, str):
        return fix_text(v).strip()
    if isinstance(v, decimal.Decimal):
        return float(v)
    return v


def fetch(as_of):
    cnxn = pyodbc.connect(CONN_STR, readonly=True, autocommit=True, timeout=30)
    cnxn.timeout = 900
    cnxn.setdecoding(pyodbc.SQL_CHAR,  encoding="latin-1")
    cnxn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16le")
    try:
        cur = cnxn.cursor()
        cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;")
        cur.execute("SET LOCK_TIMEOUT 15000;")
        results = []
        for q in queries():
            cur.execute(q, as_of)
            while cur.description is None and cur.nextset():
                pass
            names = [c[0] for c in cur.description]
            results.append([dict(zip(names, map(value, r))) for r in cur.fetchall()])
        return results
    finally:
        cnxn.close()


def balance_and_cost(moves, docs):
    """Balance and moving average cost of one product. Closest method found, not Formula's own.

    Events run in date order, with stock coming in before stock going out on the same day.
    Transfers between warehouses don't change the total. An in adds its cost value; an out
    takes the current average. An in that arrives when the quantity is zero or below values
    what's left at its own unit cost. The cost is 0 unless the balance is above zero.
    """
    events = [(m["date"], m["io"] != "I", m["entered"], m["io"] == "I", m["qty"], m["costamt"])
              for m in moves if m["reftype"] != "TR"]
    events += [(d["date"], d["reftype"] != "GB", d["entered"], d["reftype"] == "GB", d["qty"],
                d["qty"] * d["price"]) for d in docs]
    events.sort(key=lambda e: (e[0], e[1], e[2] or dt.datetime.min))

    qty = val = 0.0
    for _, _, _, is_in, q, amt in events:
        if is_in and qty <= 0:
            unit = amt / q if q else 0.0
            qty += q
            val = max(qty, 0.0) * unit
        elif is_in:
            qty += q
            val += amt
        else:
            avg = val / qty if qty > 0 else 0.0
            qty -= q
            val = val - q * avg if qty > 0 else 0.0

    balance = round(qty, 2)
    cost = round(val / qty, 2) if qty > 0 and balance > 0 else 0.0
    return balance, cost


def report_rows(prods, moves, docs, as_of):
    by_move, by_doc = collections.defaultdict(list), collections.defaultdict(list)
    for m in moves:
        by_move[m["prodcode"]].append(m)
    for d in docs:
        by_doc[d["prodcode"]].append(d)
    rows = []
    for p in prods:
        balance, cost = balance_and_cost(by_move[p["prodcode"]], by_doc[p["prodcode"]])
        rows.append({**p, "balance": balance, "cost": cost, "amt": round(balance * cost, 2),
                     "asofdate": as_of.isoformat()})
    return rows


def write_csv(rows, path):
    cols = REPORT_COLS + EXTRA_COLS
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow(["" if r.get(c) is None else f"{r[c]:.2f}" if isinstance(r[c], float) else r[c]
                        for c in cols])


def upload(csv_path):
    """Copy the CSV to Google Drive via rclone, replacing the previous file."""
    if not UPLOAD_REMOTE:
        return "disabled"
    if not os.path.exists(RCLONE):
        return f"skipped: {RCLONE} not found"
    p = subprocess.run([RCLONE, "copyto", csv_path, f"{UPLOAD_REMOTE}/{CSV_NAME}",
                        "--retries", "3", "--log-level", "NOTICE"],
                       capture_output=True, text=True, timeout=900)
    if p.returncode != 0:
        raise RuntimeError(f"rclone failed ({p.returncode}): {p.stderr.strip()[-500:]}")
    return "ok"


def main():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
    try:
        as_of = dt.date.today()
        logging.info("XRCRSTK1 as of %s", as_of)
        prods, moves, docs = fetch(as_of)
        rows = report_rows(prods, moves, docs, as_of)
        logging.info("fetched %s products, %s movements, %s uninvoiced lines",
                     f"{len(prods):,}", f"{len(moves):,}", f"{len(docs):,}")

        csv_path = os.path.join(OUT_ROOT, CSV_NAME)
        write_csv(rows, csv_path)
        logging.info("wrote %s", csv_path)

        logging.info("upload: %s", upload(csv_path))
    except Exception:
        logging.exception("FAILED")
        return 1
    return 0


if __name__ == "__main__":
    if "--no-upload" in sys.argv:
        UPLOAD_REMOTE = ""
    sys.exit(main())
