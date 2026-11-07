# Formula ERP — Main Tables Guide

_Generated: 2026-10-02 from the 500-row read-only samples in `archive\FORMULA\`._
_Meanings come from column names, sample values and Formula conventions. Items marked ✔ were checked against the sample data._

## How Formula stores data (applies to every table)

| Convention | Meaning |
|---|---|
| Column prefix | **FC** = text/code, **FN** = number, **FD** = date, **FT** = date+time, **FM** = memo/long text |
| `FCSKID` | Hidden internal ID of every row (8 chars, e.g. `MIXCiZTP`). Other tables point to it: `ORDERI.FCPROD` = `PROD.FCSKID`. May contain odd bytes shown as `\x8c` — normal, it is an ID not text. |
| `FCCODE` | The human-readable code shown on screen (account no., product code, document no.) |
| `$%` in a link column | "None / default" — no link |
| Audit columns | `FTDATETIME` (created), `FTLASTUPD`/`FTLASTEDIT` (changed), `FCCREATEBY`/`FCCORRECTB` (user IDs). Ignore for reporting. |
| Amounts | `FNAMT` = amount in baht. Columns ending in **KE** (`FNAMTKE`, `FNPRICEKE`) are in the document currency; `FNXRATE` is the rate (e.g. 33.0 for USD). |

## Main tables

### GLHEAD — Journal voucher headers
One row per accounting entry (voucher).

| Column | Meaning |
|---|---|
| `FCCODE` | Voucher number |
| `FDDATE` | Posting date |
| `FMREMARK` | Description (e.g. "ค่าเสื่อม…" depreciation) |
| `FCACCBOOK` | Journal book → **`ACCBOOK`** ✔: SD สมุดขายเชื่อ (sales), PD สมุดซื้อเชื่อ (purchases), SC เงินสดรับ (cash receipts), PC เงินสดจ่าย (cash payments), PS เงินสดย่อย (petty cash), GJ รายวันทั่วไป (general) |
| `FCCORP` / `FCBRANCH` | Company / branch |

### GL — Journal lines
The debit/credit lines of each voucher.

| Column | Meaning |
|---|---|
| `FCGLHEAD` | → `GLHEAD.FCSKID` ✔ |
| `FCACCHART` | → `ACCHART.FCSKID` (account) ✔ 487/500 matched |
| `FNAMT` | Amount. **Positive = debit, negative = credit** ✔ (172 of 186 sample vouchers sum to 0; paying VAT debits 20110 เจ้าหนี้กรมสรรพากร with +) |
| `FCSEQ` | Line number |
| `FMDETAIL` | Line description |
| `FCSECT` / `FCJOB` / `FCPROJ` | Section (cost centre) / job / project |
| `FDDATE` | Posting date (same as header) |

### ORDERH — Order headers (sales, purchase, quotation)
All order-type documents in one table.

| Column | Meaning |
|---|---|
| `FCREFTYPE` | **Document type** ✔: `SO` sales order, `PO` purchase order (book 0001 domestic, 0002 foreign), `QS` quotation, `PR` purchase request |
| `FCBOOK` | → `BOOK` (document book) ✔ |
| `FCCODE` / `FCREFNO` | Document no. / customer's or supplier's reference |
| `FDDATE` / `FDDUEDATE` / `FDRECEDATE` | Document date / due date / receive date |
| `FCCOOR` | → `COOR` (customer or supplier) |
| `FNAMT` / `FNVATAMT` | Amount before VAT / VAT (7%) |
| `FNDISCAMT1` | Header discount |
| `FNCREDTERM` | Credit term (days) |
| `FCEMPL` | → `EMPL` (salesperson / buyer) |
| `FCCONTACTN` | Contact person |
| `FCSTEP` | **Status** ✔ (per PSALEORD report legend): `1` = not fully delivered, `P` = fully delivered, `L` = closed |
| `FCSTAT` | `C` = cancelled ✔ |
| `FNAMT` / `FNDISCAMT1` | `FNAMT` is **after** the header discount; gross = `FNAMT + FNDISCAMT1` ✔ |
| `FMMEMDATA` | Notes (e.g. "เครดิต 30 วัน") |

### ORDERI — Order lines
One row per product on an order.

| Column | Meaning |
|---|---|
| `FCORDERH` | → `ORDERH.FCSKID` ✔ |
| `FCREFTYPE` | Same document type as header (SO/PO/QS) |
| `FCPROD` | → `PROD.FCSKID` |
| `FCUM` | → `UM` (unit) |
| `FNQTY` / `FNPRICE` | Quantity / unit price |
| `FCDISCSTR` / `FNDISCAMT` | Discount text (e.g. "5%") / discount amount |
| `FNBACKQTY` | Quantity still outstanding (not yet delivered/received) |
| `FNDOQTY` | Quantity delivered |
| `FDDELIVERY` | Delivery date |
| `FCWHOUSE` | → `WHOUSE` (warehouse) |
| `FMREMARK`…`FMREMARK10` | Line notes — labels, sizes, fabric (e.g. "ปลอกหมอน 20*30*6") |

### PAYMENT — Money received and paid
Receipts, payments, cheques and transfers.

| Column | Meaning |
|---|---|
| `FCINOUT` | **`I` = money in, `O` = money out** ✔ |
| `FCPAYGROUP` | `T` transfer, `Q` cheque, `C` cash ✔ |
| `FCPAYTYPE` | Detail ✔: `TRD` transfer in, `TRW` transfer out, `CL` cheque received, `CW` cheque written, `CHI`/`CHO` cash in/out |
| `FCCODE` | Payment document no. |
| `FDDATE` / `FDDUEDATE` / `FDTOBANKDA` / `FDPASSDATE` | Date / due (cheque date) / deposited / cleared |
| `FNAMT` / `FNBANKFEE` | Amount / bank fee |
| `FCBANK` / `FCBANKACCT` / `FCBBRANCH` | Bank / company bank account / branch name |
| `FCCOOR` / `FCPAYRECV` | Customer/supplier link / payer-payee name as printed |
| `FCGLHEAD` | → `GLHEAD` (the voucher it posted) |
| `FCDOCOWNER` | Source document: `SBIL` sales bill, `PBIL` purchase bill, `CHQ` cheque |
| `FCREMARK` | Note (e.g. "USD 15000@31.265") |

### PROD — Product master
Textile products: pillows, duvets, towels, sheets.

| Column | Meaning |
|---|---|
| `FCCODE` | Product code |
| `FCNAME` / `FCNAME2` | Thai / English name (e.g. "หมอน ใยไมโคร 20*36" / "pillow microfiber 20*36") |
| `FCSNAME` / `FCSNAME2` | Short category (ผ้าเช็ดตัว / bath towel) |
| `FCTYPE` | Product type code |
| `FCPDGRP` | → `PDGRP` (product group) |
| `FCUM` | → `UM` (unit) |
| `FNSTDCOST` / `FNPRICE` | Standard cost / list price |
| `FCACCBCASH`, `FCACCBCRED`, `FCACCSCASH`, `FCACCSCRED` | GL accounts for buy-cash, buy-credit, sell-cash, sell-credit → `ACCHART` |

### ACCHART — Chart of accounts

| Column | Meaning |
|---|---|
| `FCCODE` | Account number (1xxxx assets, 2xxxx liabilities, 3xxxx equity, 4xxxx revenue, 5xxxx–7xxxx costs/expenses) |
| `FCNAME` / `FCNAME2` | Thai / English name |
| `FCCATEG2` | `GENERAL` = heading, `DETAIL` = postable account |
| `FNLEVEL` | Depth in the account tree |
| `FCDRCR` | Normal balance side (DR/CR) |
| `FCGROUP` | Top-level class 1–6 |

### CORP — Company records (4 rows)
✔ checked in the live DB 2026-10-02: `0001` (FCSKID `MExeoU01`) = **A K & J Textile, the live company**, tax ID 0105537152036. `x002` (`NEPD3L01`) = A K & J test copy ("ข้อมูลทดสอบ"), same tax ID, so filter on `FCCODE`/`FCSKID`, not tax ID. `V&J` = V & J Textile, tax ID 0105541038811. `zzzz` = Crystal Formula (vendor demo).

| Column | Meaning |
|---|---|
| `FCNAME` / `FCNAME2` / `FCTAXID` / `FCADDR*` / `FCTEL` | Company identity |
| `FCARNDUE` / `FCAPNDUE` | AR/AP ageing buckets (e.g. "15,30,60") |
| `FNTAXRATE*` | Corporate tax brackets |
| `FC*PICT` | Number display formats |

## Supporting lookup tables

| Table | Holds |
|---|---|
| `COOR` | Customers & suppliers (`FCISCUST`/`FCISSUPP` = Y, `FCCODE`, `FCNAME`, address in `FMMEMDATA`) |
| `BOOK` | Document books for orders/invoices (`FCREFTYPE`: SI credit sale, SO, SC credit note, SL billing, SD debit note…) |
| `ACCBOOK` | Journal books for GL vouchers |
| `EMPL` | Employees / salespeople |
| `UM`, `PDGRP`, `WHOUSE` | Units, product groups, warehouses |
| `SECT`, `JOB`, `PROJ` | Cost centres, jobs, projects |

## Typical report joins

```sql
-- Sales orders by customer
ORDERH h JOIN COOR c ON c.FCSKID = h.FCCOOR   WHERE h.FCREFTYPE = 'SO'
-- Sales by product
ORDERI i JOIN ORDERH h ON h.FCSKID = i.FCORDERH  JOIN PROD p ON p.FCSKID = i.FCPROD
-- SO line -> its delivery orders / invoices (NOTECUT: master = downstream doc, child = SO) ✔
NOTECUT n ON n.FCCHILDTYP='SO' AND n.FCCHILDH = h.FCSKID AND n.FCCHILDI = i.FCSKID
  -- FCMASTERTY 'DO' -> DORDERH/DORDERI, 'SI' -> GLREF/REFPROD; printed doc no. = FCREFNO
-- Trial balance (+ debit / − credit)
GL g JOIN ACCHART a ON a.FCSKID = g.FCACCHART  JOIN GLHEAD v ON v.FCSKID = g.FCGLHEAD
```

## Caveats
- The samples are the first 500 rows SQL Server returned, not a date-ordered slice. Some links only partly match in the sample (e.g. ORDERI→PROD 83/500) because the related rows fall outside the 500. A full export will resolve this.
- **Password masking:** the "*PW*" rule also blanks some non-password business columns in other tables: `VMOWK1.FCPWKSHIFT / FDPWKDATE / FNPWKQTY`, `WARRTX.FCAPPWARRT`, `EMPL.FCPWZIPSAL`. Consider exceptions before a full export.
