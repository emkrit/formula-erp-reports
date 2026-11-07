#!/usr/bin/env python3
"""
Daily CUSTDET2 (customer list, as it is on the day of the run).

1. Runs Q1 of custdet2.sql (SELECT only, READ UNCOMMITTED). There is no date range.
2. Writes  D:\\Em_Project\\reports\\CUSTDET2\\CUSTDET2_claude.csv, replacing the previous file.
3. Uploads the file to Google Drive with rclone, replacing the previous file, if it is
   set up (UPLOAD_REMOTE below); otherwise the upload is skipped and logged.

Exit code 0 = OK, 1 = failed (Task Scheduler shows it as "Last Run Result").
Usage:  python daily_custdet2.py              (normal daily run)
        python daily_custdet2.py --no-upload  (local only, e.g. for testing)
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
SQL_PATH      = os.path.join(HERE, "custdet2.sql")
OUT_ROOT      = HERE
CSV_NAME      = "CUSTDET2_claude.csv"    # same name every run, so the new file replaces the old one
RCLONE        = r"D:\Em_Project\tools\rclone\rclone.exe"
UPLOAD_REMOTE = "gdrive:Formula Reports/CUSTDET2"   # rclone remote:path; "" disables upload

# Report columns (Formula's names), then extras that make the file usable on its own.
# Left out: gcoor (same as code), subhdlevel and subheadmsg (print layout), and columns the
# sample leaves blank or fixed, whose source can't be confirmed from it: mobiletel, zone,
# isexcrelim, excrelim, enddate, blacklist, grdofprice, potential, payby, custvat, custcol,
# custdeli, pricedisc, discno, discprod, discend, pathpic.
REPORT_COLS = ["runno", "code", "name", "sname", "address", "tel", "fax", "status", "inacdate",
               "personty", "taxid", "creddate", "idcard", "acchart", "percont", "addrcont", "email",
               "website", "remlay", "remthai", "remeng", "group", "saleman", "credlimit", "credterm",
               "broffice", "branchno", "branchnm", "vattype", "unitcost", "no", "floor", "room",
               "building", "moo", "soi", "road", "tambon", "amphur", "prov"]
EXTRA_COLS  = ["zip", "address2", "addrcont2", "intertel", "lastupd"]

VAT_TEXT = {"": "VAT 7 %", "1": "VAT 7 %", "3": "VAT 0 %", "4": "ไม่มี VAT"}
TAG = re.compile(r"\x7f(.{3})(.*?)\1\x7f", re.S)   # <DEL>Tax...Tax<DEL> inside the memo


def q1_sql():
    """Q1 from custdet2.sql."""
    sql = open(SQL_PATH, encoding="utf-8").read()
    code = re.sub(r"--[^\n]*", "", re.sub(r"/\*.*?\*/", "", sql, flags=re.S))
    bad = FORBIDDEN.search(code)
    if bad:
        raise SystemExit(f"Refusing to run: found '{bad.group(0)}' in {SQL_PATH}")
    q1 = re.split(r"/\* ---------- Q\d\..*?\*/", sql, flags=re.S)[1]
    return "SET NOCOUNT ON;\n" + q1


def value(v):
    """SQL value -> Python value for CSV."""
    if isinstance(v, str):
        return fix_text(v).replace("\x02", "").strip()   # \x02: stray control character in some rows
    if isinstance(v, decimal.Decimal):
        return float(v)
    return v


def fetch():
    cnxn = pyodbc.connect(CONN_STR, readonly=True, autocommit=True, timeout=30)
    cnxn.timeout = 900
    cnxn.setdecoding(pyodbc.SQL_CHAR,  encoding="latin-1")
    cnxn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16le")
    try:
        cur = cnxn.cursor()
        cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;")
        cur.execute("SET LOCK_TIMEOUT 15000;")
        cur.execute(q1_sql())
        while cur.description is None and cur.nextset():
            pass
        names = [c[0] for c in cur.description]
        return [dict(zip(names, map(value, r))) for r in cur.fetchall()]
    finally:
        cnxn.close()


def code_name(code, name):
    """'001  (โรงแรม)', as Formula prints it; blank when there is no code."""
    return f"{code}  ({name})" if code else ""


def report_row(r, runno):
    out = dict(r)
    tags = {k: v.strip() for k, v in TAG.findall(r["memo"])}
    join = lambda sep, *keys: sep.join(tags[k] for k in keys if tags.get(k))

    out["runno"]     = runno
    address = join(" ", "A11", "A21", "A31")       # no address lines: blank, even if there is a zip
    out["address"]   = f"{address} {r['zip']}".strip() if address else ""
    out["address2"]  = join(" ", "A12", "A22", "A32")
    out["addrcont"]  = (join("", "C11", "C21", "C31") + " " + tags.get("CZp", "")).strip()
    out["addrcont2"] = join(" ", "C12", "C22", "C32")
    out["fax"]       = tags.get("Fax", "")
    out["taxid"]     = tags.get("Tax", "")
    out["idcard"]    = tags.get("MId", "")
    out["email"]     = tags.get("Ema", "")
    out["website"]   = tags.get("Web", "")
    out["remlay"]    = tags.get("Lay", "")
    out["remthai"]   = tags.get("Rem", "")
    out["remeng"]    = tags.get("Rm2", "")
    out["intertel"]  = tags.get("InT", "")
    out["status"]    = r["FCSTATUS"] or "Active"
    out["vattype"]   = VAT_TEXT.get(r["FCVATTYPE"], r["FCVATTYPE"])
    out["acchart"]   = code_name(r["acchart_code"], r["acchart_name"])
    out["group"]     = code_name(r["group_code"], r["group_name"])
    out["saleman"]   = code_name(r["saleman_code"], r["saleman_name"])
    out["unitcost"]  = code_name(r["currency_sign"], r["currency_name"])
    return out


def write_csv(rows, path):
    cols = REPORT_COLS + EXTRA_COLS
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow(["" if r[c] is None else r[c].isoformat(" ") if isinstance(r[c], dt.datetime)
                        else r[c].isoformat() if isinstance(r[c], dt.date) else r[c]
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
        logging.info("CUSTDET2 as of %s", dt.date.today())
        rows = [report_row(r, i) for i, r in enumerate(fetch(), 1)]
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
