# XRBUYOR1 (01/01/2024–30/09/2026): sample vs database

Sample: `Sample report\XRBUYOR1.CSV`, saved 2026-09-01 14:26. Database run: 2026-10-13 (FORMULA, read-only).
Report: รายงานใบสั่งซื้อ แสดงข้อมูลตามแนวคอลัมน์ เรียงตาม วันที่เอกสาร (purchase orders, one row per PO line, sorted by date).
Filters: `ORDERH.FCREFTYPE = 'PO'`, CORP.FCCODE 0001 (A K & J), branch 00000, **both PO books** (0001 PO01/ domestic, 0002 PO02/ foreign), 01/01/2024–30/09/2026. **Cancelled POs are included** (all 35 cancelled lines are in the sample). There are no totals in the report.

## Result

| | Sample | Database | Note |
|---|---:|---:|---|
| Rows (PO lines) | 8,235 | 8,555 | |
| Matched to a database line | 8,231 | | |
| … every field identical | 8,094 | | |
| … line changed after the sample | 137 | | product, qty or price edited after 01/09 (`FTLASTUPD`) |
| Database only | | 324 | all created or edited after the sample; 297 are dated after 01/09 |
| Sample only | 4 | | removed after the sample (see below) |

Over the 8,094 exact matches, **every report column agrees** except where the data was changed after 01/09/2026:

| Column | Same | Different | Why |
|---|---:|---:|---|
| date, refno, itemdisc, unit, duedate2, sectcode, totamt | 8,094 | 0 | |
| refnogb | 7,846 | 248 | GB receipt linked after 01/09 |
| qtygb / unreceiqty | 7,829 | 265 | GB receipt posted after 01/09 |
| unreceiamt | 7,834 | 260 | same as above |
| coorcode | 8,084 | 10 | supplier code ก.012 → บก.012 changed in `COOR` on 14/09/2026 |
| sectname | 8,090 | 4 | section renamed in `SECT` on 14/09 and 29/09/2026 |
| prodname | 8,093 | 1 | product 13000277 renamed in `PROD` on 08/09/2026 |

## How Formula builds each column (confirmed)

| Column | Source |
|---|---|
| date / refno / code | `ORDERH.FDDATE` / `FCREFNO` / `FCCODE` |
| coorcode | `COOR.FCCODE` (supplier) |
| prodcode / prodname | `PROD.FCCODE` / `FCNAME` |
| prodprice | `ORDERI.FNPRICE` (baht) |
| itemdisc | `ORDERI.FCDISCSTR` |
| qty / unit | `ORDERI.FNQTY` / `UM.FCNAME` |
| **totamt** | `ROUND(FNQTY × FNPRICEKE − FNDISCAMTK, 2) × ORDERI.FNXRATE`. The amount is rounded in the PO currency, then converted to baht. On some foreign POs `FNPRICE` was keyed equal to the USD price, so prodprice × qty ≠ totamt (e.g. 24010000009 line 6: 1,000 × 6.22 shown, totamt 217,700 = 1,000 × 6.22 × 35). |
| **refnogb** | `FCREFNO` of the GB goods receipt (`DORDERH`) whose `NOTECUT` link was **created first** (`NOTECUT.FTDATETIME`), not the earliest-dated GB. Invoices (BI) are never shown. Blank if there's no GB. |
| **qtygb** | Total `NOTECUT.FNQTY` over all GB receipts for the line |
| **unreceiqty** | `FNQTY − qtygb`. Goes **negative** on over-receipt; Formula's own `FNBACKQTY` stops at 0, so don't use it. |
| **unreceiamt** | `ROUND(unreceiqty × FNPRICEKE × (1 − line discount %), 2) × FNXRATE`, or **0** when unreceiqty ≤ 0 |
| duedate2 | `ORDERI.FDDELIVERY` |
| sectcode / sectname | `SECT.FCCODE` / `FCNAME` (header section = customer/hotel the PO is for) |
| (all text) | trimmed on both sides |

Refno prefixes like `im26-…`, `sam…` and `emporium…` are free text in `FCREFNO` within books 0001/0002, not separate books.

## Rows only in the sample (removed after 01/09)
- `im26-426` (26090000001) and `im26-427` (26090000002), both dated 01/09/2026: these POs are no longer in the database.
- `PO01/69090006` product 22100184 qty 3: the PO was edited on 07/10/2026 and now has 2 lines; this one was removed.

## Totals in the database (not in the report; for reference)

| Book | Year | Lines | Cancelled lines | POs | Amount (baht) |
|---|---|---:|---:|---:|---:|
| 0001 domestic | 2024 | 1,539 | 3 | 1,110 | 42,994,994.68 |
| 0001 domestic | 2025 | 1,518 | 14 | 910 | 32,012,887.80 |
| 0001 domestic | 2026 | 1,435 | 18 | 764 | 36,220,878.92 |
| 0002 foreign | 2024 | 1,271 | 0 | 480 | 146,630,878.95 |
| 0002 foreign | 2025 | 1,461 | 0 | 570 | 130,320,975.54 |
| 0002 foreign | 2026 | 1,296 | 0 | 502 | 120,087,275.00 |

Lines and amounts exclude cancelled POs; the POs count includes them. 2026 runs to 30/09.

## Files
- `xrbuyor1.sql`: the query (Q1 report rows, Q2 every receipt per PO line, Q3 totals). SELECT only.
- `run_queries.py`: runs it read-only and writes `db_q1_lines.csv`, `db_q2_receipts.csv`, `db_q3_totals.csv`
- `compare.py`: re-parses the sample (Formula leaves `"` inch marks unescaped) into `sample_XRBUYOR1_cleaned.csv` and writes `compare_rows.csv` (one row per sample/db line with the differing fields)
- To refresh: `python run_queries.py` then `python compare.py`
