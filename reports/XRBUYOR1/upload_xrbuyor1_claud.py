"""
Upload XRBUYOR1 (PO report) to Google Sheet tab "XRBUYOR1_Claud".

Reads the CSV made by the daily query script, renames the headings to Thai
(XRBUYOR1 mapping from formular_mapping.xlsx, written into the code below),
and replaces the contents of the XRBUYOR1_Claud tab. No other tab is touched.

Run by hand:
    python upload_xrbuyor1_claud.py
or with another CSV:
    python upload_xrbuyor1_claud.py "D:\\path\\to\\file.csv"
"""

import sys
from datetime import datetime

import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe   # pip install gspread gspread_dataframe

# ---------------------------------------------------------------- settings
CSV_PATH = r"D:\Em_Project\reports\XRBUYOR1\XRBUYOR1_claude.csv"
SERVICE_ACCOUNT_KEY = r"D:\Em_Project\config\yt-analysis-project-402700-6c9fee962152.json"
SPREADSHEET_NAME = "XRBUYOR1_Claud"
WORKSHEET_NAME = "XRBUYOR1_Claud"

# Column mapping: XRBUYOR1_1 -> XRBUYOR1_2 (from formular_mapping.xlsx)
COLUMN_MAPPING = {
    "date":       "วันที่",
    "refno":      "เลขที่อ้างอิง",
    "code":       "เลขที่ภายใน",
    "coorcode":   "รหัสผู้จำหน่าย",
    "prodcode":   "รหัสสินค้า",
    "prodname":   "ชื่อสินค้า",
    "prodprice":  "ราคา/หน่วย",
    "itemdisc":   "ส่วนลด",
    "qty":        "จำนวน",
    "unit":       "หน่วย",
    "totamt":     "รวมเงิน",
    "refnogb":    "เลขที่อ้างอิง(GB)",
    "qtygb":      "จำนวน(GB)",
    "unreceiqty": "ค้างรับ",
    "unreceiamt": "มูลค่าค้างรับ",
    "duedate2":   "วันที่ต้องการสินค้า",
    "sectcode":   "รหัสแผนก",
    "sectname":   "ชื่อแผนก",
    # "book" and "cancelled" are not in the mapping file, so they keep English names
}

# Text columns: sent with a leading ' so Sheets keeps them as typed (03445 stays 03445).
# This also gives QUERY one type per column; it blanks values of a column's minority type.
TEXT_COLUMNS = ["refno", "code", "coorcode", "prodcode", "prodname", "itemdisc", "unit", "refnogb",
                "sectcode", "sectname", "book", "cancelled"]


def main():
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

    # 3. Upload to the XRBUYOR1_Claud tab only
    gc = gspread.service_account(filename=SERVICE_ACCOUNT_KEY)
    sh = gc.open_by_key("12iyaGsxufeu04DRC1SVfQTPYsfYdg2CBqT2yMxo15YI")
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
