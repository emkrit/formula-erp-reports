#!/usr/bin/env python3
"""
Daily XRBUYOR1 (purchase-order report). Meant for Windows Task Scheduler at 03:00.

1. Runs Q1 of xrbuyor1.sql (SELECT only, READ UNCOMMITTED) for START_DATE .. today.
2. Writes  D:\\Em_Project\\reports\\XRBUYOR1\\XRBUYOR1_claude.csv, replacing the previous file.
3. Uploads the file to Google Drive with rclone, replacing the previous file, if it is
   set up (UPLOAD_REMOTE below); otherwise the upload is skipped and logged.

Exit code 0 = OK, 1 = failed (Task Scheduler shows it as "Last Run Result").
Usage:  python daily_xrbuyor1.py              (normal daily run)
        python daily_xrbuyor1.py --no-upload  (local only, e.g. for testing)
"""

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
SQL_PATH      = os.path.join(HERE, "xrbuyor1.sql")
OUT_ROOT      = HERE
CSV_NAME      = "XRBUYOR1_claude.csv"    # same name every run, so the new file replaces the old one
START_DATE    = dt.date(2025, 1, 1)
RCLONE       = r"D:\Em_Project\tools\rclone\rclone.exe"
UPLOAD_REMOTE = "gdrive:Formula Reports/XRBUYOR1"   # rclone remote:path; "" disables upload

# Report columns (Formula's order), then two extras that make the file usable on its own.
REPORT_COLS = ["date", "refno", "code", "coorcode", "prodcode", "prodname", "prodprice",
               "itemdisc", "qty", "unit", "totamt", "refnogb", "qtygb", "unreceiqty",
               "unreceiamt", "duedate2", "sectcode", "sectname"]
EXTRA_COLS  = {"bookcode": "book", "FCSTAT": "cancelled"}
KEY_COLS   = ("code", "FCSEQ")          # one PO line


def q1_sql():
    """Q1 from xrbuyor1.sql with the dates turned into parameters."""
    sql = open(SQL_PATH, encoding="utf-8").read()
    code = re.sub(r"--[^\n]*", "", re.sub(r"/\*.*?\*/", "", sql, flags=re.S))
    bad = FORBIDDEN.search(code)
    if bad:
        raise SystemExit(f"Refusing to run: found '{bad.group(0)}' in {SQL_PATH}")
    q1 = re.split(r"/\* ---------- Q\d\..*?\*/", sql, flags=re.S)[1]
    return "SET NOCOUNT ON;\nDECLARE @d1 date = ?, @d2 date = ?;\n" + q1


def value(v):
    """SQL value -> Python value for Excel/CSV/SQLite."""
    if isinstance(v, str):
        return fix_text(v).strip()
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, dt.datetime):
        return v.date() if v.time() == dt.time() else v
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
        cur.execute(q1_sql(), d1, d2)
        while cur.description is None and cur.nextset():
            pass
        names = [c[0] for c in cur.description]
        return [dict(zip(names, map(value, r))) for r in cur.fetchall()]
    finally:
        cnxn.close()


def report_row(r):
    out = {c: r[c] for c in REPORT_COLS}
    out["book"] = r["bookcode"]
    out["cancelled"] = "C" if r["FCSTAT"] == "C" else ""
    return out


def write_csv(rows, path):
    cols = REPORT_COLS + list(EXTRA_COLS.values())
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow(["" if r[c] is None else r[c].isoformat() if isinstance(r[c], dt.date) else r[c]
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
    today = dt.date.today()
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
    try:
        logging.info("XRBUYOR1 %s .. %s", START_DATE, today)
        rows = [report_row(r) for r in fetch(START_DATE, today)]
        logging.info("fetched %s rows", f"{len(rows):,}")

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
