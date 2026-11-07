#!/usr/bin/env python3
"""
Daily PDISITM1 (general ledger listing with details).

1. Runs Q1 and Q2 of pdisitm1.sql (SELECT only, READ UNCOMMITTED) for START_DATE .. END_DATE.
2. Writes  D:\\Em_Project\\reports\\PDISITM1\\PDISITM1_claude.csv, replacing the previous file.
3. Uploads the file to Google Drive with rclone, replacing the previous file, if it is
   set up (UPLOAD_REMOTE below); otherwise the upload is skipped and logged.

Rows have rowtype LINE (a ledger line) or BANK (a bank document printed under the line above).
BANK rows carry no debit or credit, so dramt and cramt can be added up directly.

Exit code 0 = OK, 1 = failed (Task Scheduler shows it as "Last Run Result").
Usage:  python daily_pdisitm1.py              (normal daily run)
        python daily_pdisitm1.py --no-upload  (local only, e.g. for testing)
        python daily_pdisitm1.py --start 2025-01-01 --end 2025-12-31  (another date range)
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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from formula_db import CONN_STR, FORBIDDEN, RCLONE, date_option, fix_text

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HERE          = os.path.dirname(os.path.abspath(__file__))
SQL_PATH      = os.path.join(HERE, "pdisitm1.sql")
OUT_ROOT      = HERE
CSV_NAME      = "PDISITM1_claude.csv"    # same name every run, so the new file replaces the old one
START_DATE    = dt.date(2026, 1, 1)
END_DATE      = dt.date(2026, 10, 31)
UPLOAD_REMOTE = "gdrive:Formula Reports/PDISITM1"   # rclone remote:path; "" disables upload

# Report columns (Formula's names), then extras that make the file usable on its own.
# Left out: subhdlevel and subheadmsg (print layout).
REPORT_COLS = ["gbranch", "gacchart", "gbankdoc", "gchqno", "gchqstat", "gchqdate", "gchqamt", "date",
               "branch", "code", "poststep", "desc", "dramt", "cramt", "balamt"]
EXTRA_COLS  = ["rowtype", "acctname", "detail"]


def queries():
    """Q1 and Q2 from pdisitm1.sql with the dates turned into parameters."""
    sql = open(SQL_PATH, encoding="utf-8").read()
    code = re.sub(r"--[^\n]*", "", re.sub(r"/\*.*?\*/", "", sql, flags=re.S))
    bad = FORBIDDEN.search(code)
    if bad:
        raise SystemExit(f"Refusing to run: found '{bad.group(0)}' in {SQL_PATH}")
    parts = re.split(r"/\* ---------- Q\d\..*?\*/", sql, flags=re.S)[1:]
    return ["SET NOCOUNT ON;\nDECLARE @d1 date = ?, @d2 date = ?;\n" + q for q in parts]


def value(v):
    """SQL value -> Python value for CSV."""
    if isinstance(v, str):
        return re.sub(r"\s*[\r\n]+\s*", " ", fix_text(v)).strip()   # one line per cell
    if isinstance(v, decimal.Decimal):
        return v
    return v


def fetch(d1, d2):
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
            cur.execute(q, d1, d2)
            while cur.description is None and cur.nextset():
                pass
            names = [c[0] for c in cur.description]
            results.append([dict(zip(names, map(value, r))) for r in cur.fetchall()])
        return results
    finally:
        cnxn.close()


def report_rows(lines, docs):
    """Put ledger lines in order with a running balance, and bank documents under them.

    The balance starts from 0 at START_DATE for each account, as in the sample: there is no
    brought-forward amount. A voucher's bank documents print under its last line in each
    account. A document from a journal entry (owner GL) that names an account prints only
    under that account.
    """
    by_voucher = collections.defaultdict(list)
    for d in docs:
        by_voucher[d["voucher_id"]].append(d)

    last_in_account = {}
    for i, r in enumerate(lines):
        last_in_account[(r["voucher_id"], r["gacchart"])] = i

    rows, balance = [], collections.defaultdict(decimal.Decimal)
    for i, r in enumerate(lines):
        balance[r["gacchart"]] += r["amt"]
        rows.append({**r, "rowtype": "LINE", "branch": r["gbranch"], "code": r["book"] + r["voucher"],
                     "dramt": r["amt"] if r["amt"] > 0 else decimal.Decimal(0),
                     "cramt": -r["amt"] if r["amt"] < 0 else decimal.Decimal(0),
                     "balamt": balance[r["gacchart"]]})
        if last_in_account[(r["voucher_id"], r["gacchart"])] != i:
            continue
        for d in by_voucher.get(r["voucher_id"], []):
            if d["owner_type"] == "GL" and d["acct"] and d["acct"] != r["gacchart"]:
                continue
            rows.append({"rowtype": "BANK", "gbranch": r["gbranch"], "gacchart": r["gacchart"],
                         "acctname": r["acctname"], "date": r["date"], "branch": r["gbranch"],
                         "code": r["book"] + r["voucher"], "gbankdoc": d["gbankdoc"],
                         "gchqno": d["gchqno"], "gchqstat": d["gchqstat"],
                         "gchqdate": d["gchqdate"], "gchqamt": d["gchqamt"]})
    return rows


def write_csv(rows, path):
    cols = REPORT_COLS + EXTRA_COLS
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow(["" if r.get(c) is None else r[c].isoformat() if isinstance(r[c], dt.date)
                        else f"{r[c]:.2f}" if isinstance(r[c], decimal.Decimal) else r[c]
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
        logging.info("PDISITM1 %s .. %s", START_DATE, END_DATE)
        lines, docs = fetch(START_DATE, END_DATE)
        rows = report_rows(lines, docs)
        logging.info("fetched %s ledger lines, %s rows in the report", f"{len(lines):,}", f"{len(rows):,}")

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
    START_DATE = date_option("--start") or START_DATE
    END_DATE = date_option("--end") or END_DATE
    sys.exit(main())
