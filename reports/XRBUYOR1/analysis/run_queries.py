#!/usr/bin/env python3
"""
Run xrbuyor1.sql (SELECT only) and save each query's result as db_q<n>_*.csv.

- Windows auth to the local SQL Server 'server', database FORMULA, read-only.
- READ UNCOMMITTED + LOCK_TIMEOUT so the live ERP is never blocked.
- CHAR data fetched as latin-1 and decoded as cp874 (as in export_archive.py).
"""

import csv
import datetime
import os
import re
import sys
import pyodbc

sys.path.insert(0, r"D:\Em_Project\reports\common")
from formula_db import CONN_STR, FORBIDDEN, fix_text

HERE     = os.path.dirname(os.path.abspath(__file__))
SQL_PATH = os.path.join(os.path.dirname(HERE), "xrbuyor1.sql")
OUTPUTS  = ["db_q1_lines.csv", "db_q2_receipts.csv", "db_q3_totals.csv"]


def fmt(v):
    if v is None:
        return ""
    if isinstance(v, str):
        return fix_text(v).strip()          # Formula's report trims both sides
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, datetime.date):
        return v.strftime("%Y-%m-%d")
    return str(v)


def main():
    sql = open(SQL_PATH, encoding="utf-8").read()
    # strip comments before the safety check (they mention words like UPDATE in prose)
    code = re.sub(r"/\*.*?\*/", "", sql, flags=re.S)
    code = re.sub(r"--[^\n]*", "", code)
    bad = FORBIDDEN.search(code)
    if bad:
        raise SystemExit(f"Refusing to run: found '{bad.group(0)}' in {SQL_PATH}")

    preamble, *queries = re.split(r"/\* ---------- Q\d\..*?\*/", sql, flags=re.S)
    declare = re.search(r"DECLARE[^;]*;", preamble).group(0)

    cnxn = pyodbc.connect(CONN_STR, readonly=True, autocommit=True, timeout=15)
    cnxn.timeout = 600
    cnxn.setdecoding(pyodbc.SQL_CHAR,  encoding="latin-1")
    cnxn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16le")
    cur = cnxn.cursor()
    cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;")
    cur.execute("SET LOCK_TIMEOUT 15000;")

    for q, out in zip(queries, OUTPUTS):
        cur.execute("SET NOCOUNT ON;\n" + declare + "\n" + q)
        while cur.description is None and cur.nextset():
            pass
        headers = [d[0] for d in cur.description]
        rows = cur.fetchall()
        with open(os.path.join(HERE, out), "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(headers)
            w.writerows([fmt(v) for v in r] for r in rows)
        print(f"{out}: {len(rows):,} rows")
    cnxn.close()


if __name__ == "__main__":
    main()
