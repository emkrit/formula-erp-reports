# PSALEORD: Formula's built-in report definition vs `psaleord.sql`

Investigated 2026-10-06. Everything here was read-only: file listings, `SELECT` queries and the SQL Server query cache. Nothing was changed, no Formula program was run, and no .ini, .config, .udl or .dsn file was opened.

## 1. Where the definition lives

| Place checked | Result |
|---|---|
| Files named `*SALEORD*` in `C:\FORMULA.SQL`, `D:\Formula`, `D:\FORMULA.SQL`, `C:\FORMULA.SQL_BAK`, `C:\FORMULA.SQL123`, `C:\FORMULA.SQL_T`, `C:\FORMULA.SQL_Before_Update_090724`, `C:\FM_OLD` | None |
| Report files (.frx/.frt/.rpt/.lbx/.lbt/.fxp/.prg/.scx/.sct/.xml/.sql) in `FMSO`, `RPT` and `TEM` of all those copies | 166 files, all Crystal `.rpt` in `RPT`, all tax, VAT and GL statements (`PHTAX*`, `PHVAT*`, `PVATB89*`, `PCRBLSHT`, …). None for sales orders. No .frx or .prg anywhere in `FMSO`. |
| SSIS: `msdb.dbo.sysssispackages`, `SSISDB`, SQL Agent SSIS steps, `.dtsx` files on C: and D: | Only the 8 SQL Server **Data Collector** system packages (2017). No `SSISDB`, no SSIS job steps. **The report doesn't come from SSIS.** |
| `FORMULA.dbo.REPFILE`, `REPVAR` | 0 rows. These hold GL financial-statement layouts. |
| **`FORMULA.dbo.REPSET`** (`FCSYSTASK = 'PSALEORD'`) | **173 rows**: the saved column layout for 4 users |
| **`FORMULA.dbo.REPCFG`** (`FCREPCODE = 'PSALEORD'`) | 1 row of output settings, all blank, last updated 16/07/2020 |

**Conclusion:** PSALEORD is a built-in report compiled into `FORMAHC.EXE`, the Visual FoxPro program. It has no separate definition file. The program builds its SQL at run time. The database only stores each user's column layout and options (`REPSET`) and output settings (`REPCFG`). The EXE was **not** inspected, as you asked.

So the closest thing to Formula's "definition" comes from two sources: (a) the `REPSET` layout below, and (b) the SQL the program actually sends, as seen in the query cache (section 3).

## 2. Report layout from `REPSET`

There are 4 saved layouts: users `$%` (last updated 22/08/2020), `MIWMsp01`, `MIWMsp04` and `MIWTia01` (all from 03–08/08/2020). The `$%` layout has the same columns and headings as the sample CSV. The others differ only in which columns are hidden. `FMOPTDATA` and `FMOPTDATA2` (saved options) are empty in every row, so there are **no saved filters**. Filters are typed in at run time.

`FNITEMNO` is the report level, which matches `subhdlevel` in the CSV. `prn=0` means the column is hidden.

**Level 1: order header**

| seq | col id | Heading | Likely source |
|---:|---:|---|---|
| 1 | 1 | ลำดับ (no.) | row number |
| 2 | 2 | AB | A = `FCSTAT` ('C' = cancelled), B = `FCSTEP` |
| 3 | 4 | วันที่ (date) | `ORDERH.FDDATE` |
| 4 | 3 | เลขที่อ้างอิง (ref no.) | `ORDERH.FCREFNO` |
| 5–6 | 6, 7 | รหัส/ชื่อลูกค้า (customer code / name) | `COOR.FCCODE`, `FCNAME` |
| 7–8 | 8, 9 | รหัส/ชื่อแผนก (department code / name) | `SECT.FCCODE`, `FCNAME` |
| 9 | 10 | มูลค่าก่อนหักส่วนลด (amount before discount) | `FNAMT + FNDISCAMT1` |
| 10 | 11 | ส่วนลด (discount) | header discount, printed as % |
| 11 | 59 | มูลค่าก่อน VAT (amount before VAT) | `FNAMT` |
| 12 | 12 | VAT | `FNVATAMT` |
| 13 | 13 | รวมเงิน (total) | `FNAMT + FNVATAMT` |
| 14 | 48 | รหัสโครงการ (project code) | project |
| **15** | **61** | **เลขที่ใบรับเงินมัดจำ (deposit receipt no.)** | **deposit, `depcode`** |
| **16** | **62** | **มูลค่าเงินมัดจำ (deposit amount)** | **deposit, `depamt`** |

**Level 2: order lines.** The printed columns are: spacer, ลำดับ (no.), spacer, รหัสสินค้า (product code), ชื่อสินค้า (product name), ราคา/หน่วย (unit price), ส่วนลด (discount), จำนวน (qty), หน่วย (unit), วันที่ส่งของ (delivery date), ค้างส่ง[หน่วย|มาตรฐาน] (backorder [unit | standard]). Hidden for `$%` but present in the CSV export: จำนวนมาตรฐาน/หน่วย (standard qty / unit), col 32/33, and จำนวนหน่วยคุมสต๊อค/หน่วย (stock-unit qty / unit), col 35/36.

**Level 3: delivery notes and invoices.** The printed columns are: spacer, วันที่ (date), เลขที่อ้างอิง (ref no., col 69), ส่วนลด (discount), ราคา (price), จำนวน (qty), หน่วย (unit). Hidden: จำนวนมาตรฐาน/หน่วย (standard qty / unit).

## 3. SQL Formula actually sends (query cache)

The query cache doesn't record which report sent a query. The queries below are the ones whose tables and columns match PSALEORD's columns. They are not a confirmed trace of a PSALEORD run.

- **Order headers.** The 13-parameter `SELECT ORDERH… UNION SELECT ORDERH…` queries seen earlier belong to the **document browse screen**: they return print count, print-by and approval status. They aren't the report query. They do show Formula's standard SO filter: `FCCORP = @corp AND FCBRANCH = @branch AND FCREFTYPE = 'SO' AND FCBOOK = @book AND FDDATE BETWEEN @d1 AND @d2`, with an **inner** join to `COOR`.
- **Order lines, per order** (`ORDERI WHERE FCCORP, FCBRANCH, FCORDERH ORDER BY … FCSEQ`). It reads `FNPRICE, FNQTY, FCDISCSTR, FNDISCAMT, FNUMQTY, FDDELIVERY, FNSTQTY, FCSTUM, FNBACKQTY, FCSTEP, FMREMARK…FMREMARK10`.
- **Delivery and invoice links, per line:** `NOTECUT` joined to `DORDERI` (DO) and to `REFPROD` (SI). Quantities come from `NOTECUT.FNQTY` / `FNUMQTY`, and dates and status from `DORDERI.FDDATE, FCSTAT` / `REFPROD.FDDATE, FCSTAT`.
- **Deposits, per order:**
  ```sql
  SELECT DISTINCT FCGLREF, FCORDERH, FNAMT FROM DEPREF
  WHERE FCCORP = @P1 AND FCBRANCH = @P2 AND FCORDERH = @P3          -- 56,933 runs

  SELECT GLREF.FCCODE, GLREF.FCREFNO, DEPREF.FNAMT, DEPREF.FNAMTKE, DEPREF.FNPAYAMT,
         DEPREF.FNPAYAMTKE, DEPREF.FNVATAMT, DEPREF.FNVATAMTKE, GLREF.FCSTAT
  FROM DEPREF, GLREF
  WHERE DEPREF.FCGLREF = GLREF.FCSKID AND DEPREF.FCCORP = @P1 AND DEPREF.FCBRANCH = @P2
    AND DEPREF.FCORDERH = @P3 AND GLREF.FCSTAT <> @P4                -- @P4 is probably 'C' (cancelled)
  ```
  The `DEPREF`, `NOTECUT` and `ORDERI` per-order queries all have the same last run time (02/10/2026 10:56:51). That fits Formula going through orders one at a time to build each report row, rather than running one big query.

## 4. Differences from `psaleord.sql`

| Area | Formula (inferred) | `psaleord.sql` | Effect / suggested change |
|---|---|---|---|
| **Deposit columns (`depcode`, `depamt`)** | Per SO: `DEPREF.FCORDERH = ORDERH.FCSKID`, joined to `GLREF` (the deposit receipt), cancelled receipts excluded. Receipt no. comes from `GLREF.FCREFNO` or `FCCODE` (the sample shows values like `R6908018`); amount comes from `DEPREF.FNAMT`. | **Not implemented** | Add a Q1b; see below. Which field gives the receipt no. still needs checking against the sample. |
| Date filter | `FDDATE BETWEEN @d1 AND @d2` | `FDDATE >= @d1 AND FDDATE < @d2 + 1` | Same result while `FDDATE` has no time part. `psaleord.sql` is the safer form. |
| Customer join | Inner join `ORDERH.FCCOOR = COOR.FCSKID` | `LEFT JOIN COOR` | Formula would drop an SO with no valid customer. No difference was seen for 09/2026. |
| Currency | Browse queries also join `CURRENCY` (a UNION for blank currency) | Not used | Only matters for foreign-currency SOs (`FNAMTKE`, `FNXRATE`). |
| Stock-unit qty / unit (`stqty`, `stunit`) | Reads `ORDERI.FNSTQTY`, `FCSTUM` | Not output | Add `i.FNSTQTY AS stqty` and the stock-unit name (`UM` via `i.FCSTUM`) to Q2. |
| Backorder `[หน่วย \| มาตรฐาน]` (backorder in order unit / standard unit) | Reads `FNBACKQTY`. The report prints backorder qty and backorder × `FNUMQTY`. | Outputs raw `FNBACKQTY`, `FNDOQTY` | Add `i.FNBACKQTY * i.FNUMQTY AS backqty_std`. |
| Line remarks | Reads `FMREMARK` … `FMREMARK10` | Only `FMREMARK` | Only matters if multi-line remarks are printed. |
| Delivery / invoice rows | `NOTECUT` → `DORDERI` / `REFPROD`, qty from `NOTECUT.FNQTY`, also reads `FCSTAT` | Same joins plus `DORDERH` / `GLREF` for ref no. and date. `inv_stat` is output but not filtered. | Logic matches. Decide whether cancelled DO/SI rows should be excluded (`FCSTAT <> 'C'`). |
| Header discount % | Shown as % in the ส่วนลด (discount) column | `FLOOR(disc*10000/amt)/100` | Already matches all 217 sample orders. |
| Company / branch / book | Run-time parameters | Hard-coded `CORP 0001`, `BRANCH 00000`, `BOOK 0001` | Fine for this report. Turn them into parameters if it's reused. |

### Suggested deposit query (Q1b), still to be confirmed against the sample
```sql
-- one row per deposit receipt linked to each SO in the period
SELECT h.FCCODE AS docno, g.FCCODE AS dep_docno, g.FCREFNO AS depcode,
       d.FNAMT AS depamt, g.FCSTAT AS dep_stat
FROM so h
JOIN dbo.DEPREF d ON d.FCORDERH = h.FCSKID AND d.FCCORP = h.FCCORP AND d.FCBRANCH = h.FCBRANCH
JOIN dbo.GLREF  g ON g.FCSKID = d.FCGLREF
WHERE g.FCSTAT <> 'C'
ORDER BY h.FDDATE, h.FCREFNO, h.FCCODE;
```
**To verify:** run it for 09/2026 and compare it with the 12 sample orders that have a deposit. That will show (1) whether `depcode` is `GLREF.FCREFNO` or `GLREF.FCCODE`, (2) whether `depamt` is `DEPREF.FNAMT` or `FNPAYAMT`, and (3) how orders with more than one deposit are printed.

## 5. Working files
These are saved in Claude's scratchpad, not in the project. Re-run if needed:
- `F_repset.csv`, `F_repcfg.csv`: the PSALEORD rows from `REPSET` and `REPCFG`
- `dump\`, `dumpG\`: cached query texts
