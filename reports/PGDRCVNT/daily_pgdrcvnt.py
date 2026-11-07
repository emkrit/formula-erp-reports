#!/usr/bin/env python3
"""
Daily PGDRCVNT (temporary goods receipts with their products and invoices).

1. Runs Q1 of pgdrcvnt.sql (SELECT only, READ UNCOMMITTED) for START_DATE .. today.
2. Writes  D:\\Em_Project\\reports\\PGDRCVNT\\PGDRCVNT_claude.csv, replacing the previous file.
3. Uploads the file to Google Drive with rclone, replacing the previous file, if it is
   set up (UPLOAD_REMOTE below); otherwise the upload is skipped and logged.

Exit code 0 = OK, 1 = failed (Task Scheduler shows it as "Last Run Result").
Usage:  python daily_pgdrcvnt.py              (normal daily run)
        python daily_pgdrcvnt.py --no-upload  (local only, e.g. for testing)
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
SQL_PATH      = os.path.join(HERE, "pgdrcvnt.sql")
OUT_ROOT      = HERE
CSV_NAME      = "PGDRCVNT_claude.csv"    # same name every run, so the new file replaces the old one
START_DATE    = dt.date(2025, 1, 1)
RCLONE        = r"D:\Em_Project\tools\rclone\rclone.exe"
UPLOAD_REMOTE = "gdrive:Formula Reports/PGDRCVNT"   # rclone remote:path; "" disables upload
NO_PO_TEXT    = "ไม่พบใบสั่งซื้อ"            # what Formula prints when a receipt has no PO

# Report columns (Formula's names), then extras that make the file usable on its own.
REPORT_COLS = ["ab", "date", "refno", "coorcode", "coorname", "sect", "amtbfdisc", "disc", "vat",
               "totamt", "refpo", "run", "prodcode", "prodname", "prodprice", "itemdisc", "qty",
               "unit", "stdqty", "stdunit", "stqty", "stunit", "bakmsg", "invdate", "invcode",
               "invdisc", "invprice", "invqty", "invunit", "invqtystd", "invstdunit"]
EXTRA_COLS  = ["book", "code", "refpo_line", "invtype"]


def q1_sql():
    """Q1 from pgdrcvnt.sql with the dates turned into parameters."""
    sql = open(SQL_PATH, encoding="utf-8").read()
    code = re.sub(r"--[^\n]*", "", re.sub(r"/\*.*?\*/", "", sql, flags=re.S))
    bad = FORBIDDEN.search(code)
    if bad:
        raise SystemExit(f"Refusing to run: found '{bad.group(0)}' in {SQL_PATH}")
    q1 = re.split(r"/\* ---------- Q\d\..*?\*/", sql, flags=re.S)[1]
    return "SET NOCOUNT ON;\nDECLARE @d1 date = ?, @d2 date = ?;\n" + q1


def value(v):
    """SQL value -> Python value for CSV."""
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
    out = dict(r)
    out["ab"] = ("C" if r["FCSTAT"] == "C" else "") + (r["FCSTEP"] or "")
    out["refpo"] = r["refpo"] or NO_PO_TEXT
    return out


def write_csv(rows, path):
    cols = REPORT_COLS + EXTRA_COLS
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
        logging.info("PGDRCVNT %s .. %s", START_DATE, today)
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
