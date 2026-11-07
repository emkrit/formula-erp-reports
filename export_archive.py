#!/usr/bin/env python3
"""
Read-only sample export of the Formula ERP databases (max 500 rows per table).

- Connects to the local SQL Server 'server' with Windows authentication.
- READ-ONLY: issues only SELECT statements. No INSERT/UPDATE/DELETE/DDL.
- Exports every NON-EMPTY table of each database in DATABASES to
  D:\\Em_Project\\archive\\<DATABASE>\\<TABLE>.csv  (SELECT TOP (500) *).
- CSV is UTF-8 *with BOM* (utf-8-sig) so Thai opens correctly in Excel.

Fixes vs. the 2026-10-01 run:
- LOCKS: live ERP clients keep transactions open, so a plain SELECT waited
  forever on their locks (the run hung on UALLOC). Reads now use
  READ UNCOMMITTED (takes no shared locks, never blocks ERP users) plus a
  LOCK_TIMEOUT, so a table can never hang the whole export.
- THAI DECODING: some CHAR/TEXT fields contain bytes 0x80-0x9F that are not
  valid cp874, which crashed decoding (11 tables exported 0 rows). CHAR data
  is now fetched as raw bytes (latin-1) and decoded as cp874 here; invalid
  bytes are kept as \\x8d-style escapes instead of failing.
- LOG: export_log.csv is appended after EVERY table, so a crash still leaves
  a record of what was done.
- Also exports cloudreportdb (previously skipped).
- PASSWORDS: any column whose name contains "PW" is written blank.

Usage:  python export_archive.py               (all tables)
        python export_archive.py EMPLR CORP    (only these tables; the
                                                log rows for them are replaced)
"""

import csv
import os
import sys
import time
import datetime
import pyodbc

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SERVER        = "server"          # local instance (this computer)
DATABASES     = ["FORMULA", "cloudreportdb"]
DRIVER        = "ODBC Driver 13 for SQL Server"
OUT_ROOT      = r"D:\Em_Project\archive"
LOG_PATH      = os.path.join(OUT_ROOT, "export_log.csv")
MAX_ROWS      = 500               # rows exported per table (TOP n)
LOCK_TIMEOUT  = 15000             # ms to wait on a lock before giving up
QUERY_TIMEOUT = 120               # s per query (safety net)

# Thai data: CHAR/VARCHAR/TEXT are code page 874 (collation Thai_BIN).
CHAR_ENCODING = "cp874"

# Password masking: columns whose name contains this text are written blank.
MASK_TEXT = "PW"
# ...except these (TABLE, COLUMN) pairs, which contain "PW" but are not passwords.
MASK_EXCEPTIONS = {
    ("VMOWK1", "FCPWKSHIFT"),
    ("VMOWK1", "FDPWKDATE"),
    ("VMOWK1", "FNPWKQTY"),
    ("WARRTX", "FCAPPWARRT"),
    ("EMPL",   "FCPWZIPSAL"),
}

LOG_FIELDS = ["database", "table", "catalog_rows", "expected_rows",
              "exported_rows", "match", "bad_byte_values", "masked_columns",
              "seconds", "status"]


def connect(database):
    """Open a read-only Windows-auth connection that never waits on ERP locks."""
    conn_str = (
        f"DRIVER={{{DRIVER}}};"
        f"SERVER={SERVER};"
        f"DATABASE={database};"
        "Trusted_Connection=yes;"
        "APP=FORMULA archive export (read-only);"
    )
    cnxn = pyodbc.connect(conn_str, readonly=True, autocommit=True, timeout=15)
    cnxn.timeout = QUERY_TIMEOUT
    # latin-1 maps every byte 1:1, so CHAR data arrives undamaged; it is
    # decoded as cp874 in fix_text() where bad bytes can be handled.
    cnxn.setdecoding(pyodbc.SQL_CHAR,  encoding="latin-1")
    cnxn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16le")
    cnxn.setencoding(encoding="utf-8")
    cur = cnxn.cursor()
    cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;")
    cur.execute(f"SET LOCK_TIMEOUT {LOCK_TIMEOUT};")
    cur.close()
    return cnxn


def get_nonempty_tables(cnxn):
    """Return [(schema, table, catalog_rowcount)] for non-empty base tables,
    ordered smallest-first so quick wins show progress early."""
    sql = """
        SELECT s.name AS sch, t.name AS tbl, SUM(p.rows) AS rows
        FROM sys.tables t
        JOIN sys.schemas s     ON t.schema_id = s.schema_id
        JOIN sys.partitions p  ON t.object_id = p.object_id
                               AND p.index_id IN (0, 1)
        GROUP BY s.name, t.name
        HAVING SUM(p.rows) > 0
        ORDER BY SUM(p.rows) ASC;
    """
    cur = cnxn.cursor()
    cur.execute(sql)
    rows = [(r.sch, r.tbl, int(r.rows)) for r in cur.fetchall()]
    cur.close()
    return rows


def fix_text(s):
    """Decode a latin-1-carried CHAR value as cp874.
    Returns (text, had_bad_bytes)."""
    raw = s.encode("latin-1")
    try:
        return raw.decode(CHAR_ENCODING), False
    except UnicodeDecodeError:
        return raw.decode(CHAR_ENCODING, errors="backslashreplace"), True


def fmt(value):
    """Render one SQL value as a CSV-safe string. Returns (text, had_bad_bytes)."""
    if value is None:
        return "", False
    if isinstance(value, str):
        return fix_text(value)
    if isinstance(value, datetime.datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S"), False
    if isinstance(value, datetime.date):
        return value.strftime("%Y-%m-%d"), False
    if isinstance(value, (bytes, bytearray)):
        return value.hex(), False          # binary columns -> hex, never lossy
    return str(value), False


def export_table(cnxn, schema, table, out_path):
    """Write up to MAX_ROWS rows of one table to CSV.
    Returns (rows_written, values_with_bad_bytes, masked_column_names)."""
    cur = cnxn.cursor()
    cur.execute(f"SELECT TOP ({MAX_ROWS}) * FROM [{schema}].[{table}]")  # read-only
    headers = [col[0] for col in cur.description]
    rows = cur.fetchall()
    cur.close()

    masked = [h for h in headers
              if MASK_TEXT in h.upper()
              and (table.upper(), h.upper()) not in MASK_EXCEPTIONS]
    bad = 0
    out_rows = []
    for row in rows:
        cells = []
        for h, v in zip(headers, row):
            if h in masked:
                cells.append("")                 # password-like column: blank
                continue
            text, was_bad = fmt(v)
            bad += was_bad
            cells.append(text)
        out_rows.append(cells)

    # Write only after a successful fetch, so a failure never leaves a
    # misleading header-only file.
    with open(out_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(headers)
        writer.writerows(out_rows)
    return len(out_rows), bad, masked


def append_log(row):
    """Add one table's result to the log, replacing any older row for it."""
    rows = []
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, newline="", encoding="utf-8-sig") as fh:
            rows = [r for r in csv.DictReader(fh)
                    if (r["database"], r["table"]) != (row["database"], row["table"])]
    rows.append(row)
    with open(LOG_PATH, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=LOG_FIELDS, restval="",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    only = {t.upper() for t in sys.argv[1:]}    # optional table filter
    os.makedirs(OUT_ROOT, exist_ok=True)
    if not only and os.path.exists(LOG_PATH):
        os.remove(LOG_PATH)                 # full run: start a fresh log

    log_rows = []
    for database in DATABASES:
        out_dir = os.path.join(OUT_ROOT, database)
        os.makedirs(out_dir, exist_ok=True)
        print(f"\nConnecting to {SERVER}/{database} (Windows auth, read-only) ...")
        cnxn = connect(database)
        tables = get_nonempty_tables(cnxn)
        if only:
            tables = [t for t in tables if t[1].upper() in only]
        total = len(tables)
        print(f"Found {total} non-empty tables. Output -> {out_dir}  (max {MAX_ROWS} rows each)\n")

        for idx, (schema, table, catalog) in enumerate(tables, 1):
            expected = min(catalog, MAX_ROWS)
            print(f"[{database} {idx}/{total}] {table}  (catalog {catalog:,}, expect {expected:,})")
            t0 = time.time()
            status, exported, bad, masked = "OK", 0, 0, []
            try:
                exported, bad, masked = export_table(
                    cnxn, schema, table, os.path.join(out_dir, f"{table}.csv"))
            except pyodbc.Error as exc:
                status = f"ERROR: {exc}"
                print(f"      !! {status}")
                if "1222" in str(exc):          # lock request time out
                    status = "LOCKED (timeout) - " + status
            except Exception as exc:            # keep going on any failure
                status = f"ERROR: {type(exc).__name__}: {exc}"
                print(f"      !! {status}")
            dt = time.time() - t0

            if status != "OK":
                match = "N/A"
            else:
                match = "MATCH" if exported == expected else "MISMATCH"
            note = f"  ({bad} values with non-cp874 bytes, escaped)" if bad else ""
            if masked:
                note += f"  (masked: {', '.join(masked)})"
            print(f"      done: {exported:,} rows  [{match}]  {dt:.1f}s{note}")

            row = {
                "database":        database,
                "table":           table,
                "catalog_rows":    catalog,
                "expected_rows":   expected,
                "exported_rows":   exported,
                "match":           match,
                "bad_byte_values": bad,
                "masked_columns":  " ".join(masked),
                "seconds":         round(dt, 1),
                "status":          status,
            }
            append_log(row)
            log_rows.append(row)
        cnxn.close()

    # Summary
    mism = [r for r in log_rows if r["match"] == "MISMATCH"]
    errs = [r for r in log_rows if r["status"] != "OK"]
    badt = [r for r in log_rows if r["bad_byte_values"]]
    print("\n" + "=" * 60)
    for database in DATABASES:
        sub = [r for r in log_rows if r["database"] == database]
        print(f"{database:15}: {len(sub)} tables, "
              f"{sum(r['exported_rows'] for r in sub):,} rows exported")
    print(f"Mismatches      : {len(mism)}")
    print(f"Errors          : {len(errs)}")
    print(f"Tables w/ escaped non-cp874 bytes: {len(badt)}")
    for r in mism:
        print(f"   MISMATCH {r['database']}.{r['table']}: expected {r['expected_rows']} got {r['exported_rows']}")
    for r in errs:
        print(f"   ERROR    {r['database']}.{r['table']}: {r['status']}")
    print(f"\nLog written to {LOG_PATH}")


if __name__ == "__main__":
    main()
