/* =====================================================================
   XRCRSTK1 - รายงานสินค้าและวัตถุดิบคงเหลือแยกหรือรวมคลัง แสดงล็อตสินค้า (สำหรับ Warehouse)
   Reproduces D:\Em_Project\Sample report\XRCRSTK1.CSV (saved 04/11/2026 11:07)
   SELECT-only. Database: FORMULA (SQL Server 2017), schema dbo.

   Parameters taken from the sample header and Sample report\Readme.txt:
     company   : CORP.FCCODE 0001 = A K & J Textile
     branch    : 00000 head office, total of all its warehouses (0001 - z000000002)
     products  : all products, types 1 - R, codes 001 - บ80000059, zero balances included
     as-of date: @d, set by daily_xrcrstk1.py to the day of the run
     lots      : not printed

   The balance is not read from dbo.STOCK: STOCK.FNQTY still counts some cancelled documents.
   This file returns products (Q1), stock movements (Q2) and goods received or delivered but not
   yet invoiced (Q3); daily_xrcrstk1.py works out the balance and the average cost from them.
   ===================================================================== */
SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;   -- don't take locks on the live ERP

DECLARE @d date = '2026-11-04';

/* ---------- Q1. Products: one row per product, in report order (type, then code) ---------- */
SELECT
    p.FCCODE                                    AS prodcode,
    p.FCNAME                                    AS prodname,
    u.FCNAME                                    AS unit,
    p.FCTYPE                                    AS prodtype,
    t.FCNAME                                    AS prodtypename
FROM dbo.PROD p
JOIN dbo.CORP co ON co.FCSKID = p.FCCORP
LEFT JOIN dbo.UM u ON u.FCSKID = p.FCUM
LEFT JOIN dbo.PRODTYPE t ON t.FCCODE = p.FCTYPE
WHERE co.FCCODE = '0001'
ORDER BY p.FCTYPE, p.FCCODE;

/* ---------- Q2. Stock movements up to the as-of date, cancelled lines left out ----------
     qty = FNQTY * FNUMQTY; FCIOTYPE I = in, O = out; FNCOSTAMT = cost value of the line     */
SELECT
    p.FCCODE                                    AS prodcode,
    r.FCIOTYPE                                  AS io,
    r.FCREFTYPE                                 AS reftype,
    CAST(r.FDDATE AS date)                      AS [date],
    r.FTDATETIME                                AS entered,
    r.FNQTY * r.FNUMQTY                         AS qty,
    r.FNCOSTAMT                                 AS costamt
FROM dbo.REFPROD r
JOIN dbo.PROD   p  ON p.FCSKID  = r.FCPROD
JOIN dbo.CORP   co ON co.FCSKID = r.FCCORP
JOIN dbo.BRANCH br ON br.FCSKID = r.FCBRANCH
WHERE co.FCCODE = '0001'
  AND br.FCCODE = '00000'
  AND r.FCSTAT <> 'C'
  AND r.FDDATE < DATEADD(day, 1, @d)
ORDER BY p.FCCODE, r.FDDATE, r.FTDATETIME;

/* ---------- Q3. Goods received (GB, in) and delivered (DO, out) but not yet invoiced ----------
     qty = FNBACKQTY * FNUMQTY, valued at FNPRICE                                             */
SELECT
    p.FCCODE                                    AS prodcode,
    h.FCREFTYPE                                 AS reftype,
    CAST(h.FDDATE AS date)                      AS [date],
    i.FTDATETIME                                AS entered,
    i.FNBACKQTY * i.FNUMQTY                     AS qty,
    i.FNPRICE                                   AS price
FROM dbo.DORDERI i
JOIN dbo.DORDERH h  ON h.FCSKID  = i.FCDORDERH
JOIN dbo.PROD    p  ON p.FCSKID  = i.FCPROD
JOIN dbo.CORP    co ON co.FCSKID = h.FCCORP
JOIN dbo.BRANCH  br ON br.FCSKID = h.FCBRANCH
WHERE co.FCCODE = '0001'
  AND br.FCCODE = '00000'
  AND h.FCREFTYPE IN ('GB', 'DO')
  AND h.FCSTAT <> 'C'
  AND i.FNBACKQTY <> 0
  AND h.FDDATE < DATEADD(day, 1, @d)
ORDER BY p.FCCODE, h.FDDATE, i.FTDATETIME;
