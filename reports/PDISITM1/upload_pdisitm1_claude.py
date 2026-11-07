"""
Upload PDISITM1 (general ledger listing) to Google Sheet tab "PDISITM1_Claude".

Reads the CSV made by daily_pdisitm1.py, renames the headings to Thai (PDISITM1 mapping from
formular_mapping.xlsx, written into the code below), and replaces the contents of the
PDISITM1_Claude tab. No other tab is touched. Other tabs' formulas read the PDISITM1 tab,
so it is left as it is.

Run by hand:
    python upload_pdisitm1_claude.py
or with another CSV:
    python upload_pdisitm1_claude.py "D:\\path\\to\\file.csv"
"""

import sys
from datetime import datetime

import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe   # pip install gspread gspread_dataframe

# ---------------------------------------------------------------- settings
CSV_PATH = r"D:\Em_Project\reports\PDISITM1\PDISITM1_claude.csv"
SERVICE_ACCOUNT_KEY = r"D:\Em_Project\config\yt-analysis-project-402700-6c9fee962152.json"
SPREADSHEET_KEY = "17IUycqF7OmTIo3G5xgBkXy21xAdWD0Eycpbp7kNMHSc"
SPREADSHEET_NAME = "PDISITM1_2026"
WORKSHEET_NAME = "PDISITM1_Claude"

# Column mapping: PDISITM1_1 -> PDISITM1_2 (from formular_mapping.xlsx), spaces kept as written there.
# Columns not listed keep their English names.
COLUMN_MAPPING = {
    "gacchart": "GL_num",
    "gbankdoc": " สถานะ",
    "gchqno":   "เช็คเลขที่",
    "gchqstat": "สถานะจ่าย",
    "date":     "วันที่",
    "branch":   "สาขา",
    "code":     "เอกสาร #",
    "desc":     "          ร า ย ก า ร",
    "dramt":    "จำนวนเงินเดบิต",
    "cramt":    "จำนวนเงินเครดิต",
    "balamt":   "ยอดคงเหลือ",
}

# Text columns: sent with a leading ' so Sheets keeps them as typed (00000 stays 00000)
TEXT_COLUMNS = ["gbranch", "gacchart", "gbankdoc", "gchqno", "gchqstat", "branch", "code", "poststep",
                "desc", "rowtype", "acctname", "detail"]


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

    # 3. Upload to the PDISITM1_Claude tab only
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
