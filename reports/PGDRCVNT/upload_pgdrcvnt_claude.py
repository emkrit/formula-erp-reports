"""
Upload PGDRCVNT (temporary goods receipts) to Google Sheet tab "PGDRCVNT_Claude".

Reads the CSV made by daily_pgdrcvnt.py, renames the headings to Thai (the same
headings as the PGDRCVNT tab), and replaces the contents of the PGDRCVNT_Claude tab.
No other tab is touched.

Run by hand:
    python upload_pgdrcvnt_claude.py
or with another CSV:
    python upload_pgdrcvnt_claude.py "D:\\path\\to\\file.csv"
"""

import os
import sys
from datetime import datetime

import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe   # pip install gspread gspread_dataframe

# ---------------------------------------------------------------- settings
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "PGDRCVNT_claude.csv")
SERVICE_ACCOUNT_KEY = os.environ.get(
    "GOOGLE_SA_KEY",
    os.path.join(os.environ.get("EM_HOME", r"D:\Em_Project"), "config",
                 "yt-analysis-project-402700-6c9fee962152.json"))
SPREADSHEET_KEY = "1ZCs4lC4umxSyaVrNqnyXnzYwok6KaubH3mvHB9Yfy_k"
SPREADSHEET_NAME = "PGDRCVNT"
WORKSHEET_NAME = "PGDRCVNT_Claude"

# Column mapping: same Thai headings as the PGDRCVNT tab. Columns not listed keep English names.
COLUMN_MAPPING = {
    "date":      "วันที่",
    "refno":     "เลขที่อ้างอิง",
    "coorcode":  "รหัส ผู้จำหน่าย",
    "coorname":  "ชื่อ ผู้จำหน่าย",
    "sect":      "แผนก",
    "amtbfdisc": "มูลค่าก่อนส่วนลด",
    "disc":      "ส่วนลด",
    "vat":       "มูลค่า Vat",
    "totamt":    "มูลค่าสุทธิ",
    "refpo":     "ใบสั่งซื้อ",
    "prodcode":  "รหัสสินค้า",
    "prodname":  "ชื่อสินค้า",
    "prodprice": "ราคา/หน่วย",
    "itemdisc":  "ส่วนลด",
    "qty":       "จำนวน",
    "unit":      "หน่วย",
    "stdqty":    "จำนวนมาตรฐาน",
    "stdunit":   "หน่วย",
    "stqty":     "จำนวนหน่วยคุมสต๊อค",
    "stunit":    "หน่วย",
    "bakmsg":    "ค้างทำ",
}

# Text columns: sent with a leading ' so Sheets keeps them as typed (02705 stays 02705)
TEXT_COLUMNS = ["ab", "refno", "coorcode", "coorname", "sect", "refpo", "prodcode", "prodname",
                "itemdisc", "unit", "stdunit", "stunit", "invcode", "invdisc", "invunit",
                "invstdunit", "book", "code", "refpo_line", "invtype"]


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

    # 3. Upload to the PGDRCVNT_Claude tab only
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
