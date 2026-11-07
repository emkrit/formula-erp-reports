"""
Upload PPDOR2 (outstanding goods to receive) to Google Sheet tab "PPDOR2_Claude".

Reads the CSV made by daily_ppdor2.py, renames the headings to Thai (PPDOR2 mapping from
formular_mapping.xlsx, written into the code below), and replaces the contents of the
PPDOR2_Claude tab. No other tab is touched.

Run by hand:
    python upload_ppdor2_claude.py
or with another CSV:
    python upload_ppdor2_claude.py "D:\\path\\to\\file.csv"
"""

import sys
from datetime import datetime

import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe   # pip install gspread gspread_dataframe

# ---------------------------------------------------------------- settings
CSV_PATH = r"D:\Em_Project\reports\PPDOR2\PPDOR2_claude.csv"
SERVICE_ACCOUNT_KEY = r"D:\Em_Project\config\yt-analysis-project-402700-6c9fee962152.json"
SPREADSHEET_KEY = "16cTuUpPwkxchn0FwOEPqbhzuf6m7omFofnwJ19jNSdk"
SPREADSHEET_NAME = "PPDOR2"
WORKSHEET_NAME = "PPDOR2_Claude"

# Column mapping: PPDOR2_1 -> PPDOR2_2 (from formular_mapping.xlsx).
# Columns not listed (refno has no heading in the mapping, and the extras) keep their English names.
COLUMN_MAPPING = {
    "gprod":    "รหัสสินค้า",
    "recedate": "วันที่ต้องการสินค้า",
    "code":     "เลขที่ใบสั่งซื้อ",
    "coorname": "ผู้จำหน่าย",
    "qcsect":   "แผนก",
    "orderqty": "ยอดสั่ง",
    "backqty":  "ค้างรับ",
    "umname":   "หน่วยนับ",
    "inprice":  "ราคาซื้อ/หน่วย",
    "inamt":    "จำนวนเงิน",
}

# Text columns: sent with a leading ' so Sheets keeps them as typed (00001 stays 00001)
TEXT_COLUMNS = ["gprod", "refno", "code", "coorname", "qcsect", "umname", "prodname",
                "linestep", "docstep", "book"]


def main():
    if not SPREADSHEET_KEY:
        sys.exit("SPREADSHEET_KEY is not set: confirm the target spreadsheet first.")
    csv_path = sys.argv[1] if len(sys.argv) > 1 else CSV_PATH

    # 1. Read
    df = pd.read_csv(
        csv_path,
        encoding="utf-8-sig",
        dtype={c: str for c in TEXT_COLUMNS},
        keep_default_na=False,
        na_values=[""],
    )
    print(f"Read {len(df):,} rows x {len(df.columns)} columns from {csv_path}")

    # 2. Keep text as text, then rename headings
    for c in TEXT_COLUMNS:
        df[c] = df[c].map(lambda v: "'" + v if isinstance(v, str) else v)
    missing = [c for c in COLUMN_MAPPING if c not in df.columns]
    if missing:
        print(f"Warning: columns not found in CSV: {missing}")
    df = df.rename(columns=COLUMN_MAPPING)

    # 3. Upload to the PPDOR2_Claude tab only
    gc = gspread.service_account(filename=SERVICE_ACCOUNT_KEY)
    sh = gc.open_by_key(SPREADSHEET_KEY)
    try:
        ws = sh.worksheet(WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=WORKSHEET_NAME,
                              rows=len(df) + 100, cols=len(df.columns) + 2)
        print(f"Created tab {WORKSHEET_NAME}")

    ws.clear()
    set_with_dataframe(ws, df, include_index=False, resize=True, string_escaping="off")

    # 4. Check
    uploaded = len(ws.col_values(1)) - 1   # minus heading row
    print(f"Uploaded {uploaded:,} rows to '{SPREADSHEET_NAME}' / '{WORKSHEET_NAME}' "
          f"at {datetime.now():%Y-%m-%d %H:%M}")
    if uploaded != len(df):
        print(f"WARNING: row count mismatch (CSV {len(df):,} vs sheet {uploaded:,})")
        sys.exit(1)


if __name__ == "__main__":
    main()
