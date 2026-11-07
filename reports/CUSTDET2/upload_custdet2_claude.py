"""
Upload CUSTDET2 (customer list) to Google Sheet tab "CUSTDET2_Claude".

Reads the CSV made by daily_custdet2.py, renames the headings to Thai (the same
headings as the CUSTDET2 tab), and replaces the contents of the CUSTDET2_Claude tab.
No other tab is touched. Other tabs' formulas read the CUSTDET2 tab, so it is left as it is.

Run by hand:
    python upload_custdet2_claude.py
or with another CSV:
    python upload_custdet2_claude.py "D:\\path\\to\\file.csv"
"""

import os
import sys
from datetime import datetime

import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe   # pip install gspread gspread_dataframe

# ---------------------------------------------------------------- settings
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CUSTDET2_claude.csv")
SERVICE_ACCOUNT_KEY = os.environ.get(
    "GOOGLE_SA_KEY",
    os.path.join(os.environ.get("EM_HOME", r"D:\Em_Project"), "config",
                 "yt-analysis-project-402700-6c9fee962152.json"))
SPREADSHEET_KEY = "1T5N9z9638sPDX-s4jW1ZobHBDke9mdD6OaqhbkyBBjQ"
SPREADSHEET_NAME = "CUSTDET2"
WORKSHEET_NAME = "CUSTDET2_Claude"

# Column mapping: same Thai headings as the CUSTDET2 tab. Columns not listed keep English names.
COLUMN_MAPPING = {
    "runno":     "ลำดับ",
    "code":      "รหัส",
    "name":      "ชื่อ",
    "sname":     "ชื่อเล่น",
    "address":   "ที่อยู่",
    "tel":       "โทรศัพท์",
    "fax":       "โทรสาร",
    "status":    "สถานะ",
    "inacdate":  "วันที่ InActive",
    "personty":  "เป็นนิติบุคคล ?",
    "taxid":     "เลขผู้เสียภาษี",
    "creddate":  "วันที่คีย์ข้อมูล",
    "idcard":    "เลขที่บัตรประจำตัวประชาชน",
    "acchart":   "รหัสบัญชี",
    "percont":   "ชื่อผู้ติดต่อ",
    "addrcont":  "ที่อยู่ที่ใช้ติดต่อ",
    "email":     "E-mail",
    "website":   "Web Site",
    "remlay":    "หมายเหตุใบวางบิล",
    "remthai":   "หมายเหตุภาษาไทย",
    "remeng":    "หมายเหตุภาษา2",
    "group":     "กลุ่มลูกค้า",
    "saleman":   "พนักงานขาย",
    "credlimit": "วงเงินเครดิต",
    "credterm":  "เครดิตเทอม",
    "broffice":  "เป็นสำนักงานใหญ่?",
    "branchno":  "รหัสสาขาในรายงานภาษี",
    "branchnm":  "ชื่อสาขาในรายงานภาษี",
    "vattype":   "ชนิด VAT",
    "unitcost":  "หน่วยเงินของต้นทุนมาตรฐาน",
    "no":        "เลขที่",
    "floor":     "ชั้นที่",
    "room":      "ห้องที่",
    "building":  "อาคารหมู่บ้าน",
    "moo":       "หมู่",
    "soi":       "ซอย",
    "road":      "ถนน",
    "tambon":    "ตำบล",
    "amphur":    "อำเภอ",
    "prov":      "จังหวัด",
}

# Sent as numbers or dates; everything else goes with a leading ' so Sheets keeps it as
# typed (0105522000839 stays 0105522000839, +66-81... doesn't become a formula).
NOT_TEXT = ["runno", "inacdate", "creddate", "credlimit", "credterm", "lastupd"]


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else CSV_PATH

    # 1. Read
    columns = pd.read_csv(csv_path, encoding="utf-8-sig", nrows=0).columns
    text_columns = [c for c in columns if c not in NOT_TEXT]
    df = pd.read_csv(
        csv_path,
        encoding="utf-8-sig",
        dtype={c: str for c in text_columns},
        keep_default_na=False,
        na_values=[""],
    )
    print(f"Read {len(df):,} rows x {len(df.columns)} columns from {csv_path}")

    # 2. Keep text as text, then rename headings
    for c in text_columns:
        df[c] = df[c].map(lambda v: "'" + v if isinstance(v, str) else v)
    missing = [c for c in COLUMN_MAPPING if c not in df.columns]
    if missing:
        print(f"Warning: columns not found in CSV: {missing}")
    df = df.rename(columns=COLUMN_MAPPING)

    # 3. Upload to the CUSTDET2_Claude tab only
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
