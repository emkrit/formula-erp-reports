import csv, sys
import gspread
gc = gspread.service_account(filename=r"D:\Em_Project\config\yt-analysis-project-402700-6c9fee962152.json")
ws = gc.open_by_key("17IUycqF7OmTIo3G5xgBkXy21xAdWD0Eycpbp7kNMHSc").worksheet("PDISITM1_Claude")
vals = ws.get("O2:O29802", value_render_option="UNFORMATTED_VALUE")
rd = csv.reader(open(r"D:\Em_Project\reports\PDISITM1\PDISITM1_claude.csv", encoding="utf-8-sig")); next(rd)
rows = list(rd); bad = 0
for i, r in enumerate(rows):
    v = vals[i][0] if i < len(vals) and vals[i] else ""
    if (r[14] == "") != (v == "") or (r[14] and abs(float(r[14]) - float(v)) > 0.005): bad += 1
print("balance cells compared", len(rows), "real value differences", bad)
