/* =====================================================================
   PSALEORD - รายงานใบสั่งขาย แสดงรายการสินค้า และใบส่งของ เรียงตามวันที่เอกสาร
   Reproduces D:\Em_Project\Sample report\PSALEORD.CSV
   SELECT-only. Database: FORMULA (SQL Server 2017), schema dbo.

   Inferred parameters (from the CSV header/data - CONFIRM):
     period   : 01/09/2026 - 30/09/2026
     book     : SO book 0001 "ใบสั่งขาย (SALE ORDER)"
     company  : CORP.FCCODE 0001 = A K & J Textile (live; x002 is the test copy with the same tax ID), branch 00000
     other    : no customer / section / salesperson / status filter;
                cancelled docs listed (A='C') but excluded from totals
   ===================================================================== */
SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;   -- don't take locks on the live ERP

DECLARE @d1 date = '2026-09-01', @d2 date = '2026-09-30';

/* ---------- Q1. Order headers: one row per SO (report subhdlevel = 1) ---------- */
WITH so AS (
    SELECT h.*
    FROM dbo.ORDERH h
    JOIN dbo.BOOK   b  ON b.FCSKID  = h.FCBOOK
    JOIN dbo.CORP   co ON co.FCSKID = h.FCCORP
    JOIN dbo.BRANCH br ON br.FCSKID = h.FCBRANCH
    WHERE h.FCREFTYPE = 'SO'
      AND b.FCCODE    = '0001'
      AND co.FCCODE   = '0001'
      AND br.FCCODE   = '00000'
      AND h.FDDATE >= @d1 AND h.FDDATE < DATEADD(day, 1, @d2)
)
SELECT
    ROW_NUMBER() OVER (ORDER BY h.FDDATE, h.FCREFNO, h.FCCODE)      AS [no],
    CASE WHEN h.FCSTAT = 'C' THEN 'C' ELSE ' ' END + RTRIM(h.FCSTEP) AS ab,       -- A: C=cancelled, B: 1/P/L
    CAST(h.FDDATE AS date)                                           AS [date],
    h.FCCODE                                                         AS docno,     -- not printed on report; for matching
    h.FCREFNO                                                        AS refno,
    c.FCCODE  AS coorcode,  c.FCNAME AS coorname,
    s.FCCODE  AS sectcode2, s.FCNAME AS sectname,
    h.FNAMT + h.FNDISCAMT1                                           AS amt,       -- before header discount
    CASE WHEN h.FNAMT + h.FNDISCAMT1 <> 0
         THEN FLOOR(h.FNDISCAMT1 * 10000 / (h.FNAMT + h.FNDISCAMT1)) / 100
         ELSE 0 END                                                  AS discamt,   -- report prints discount as % (truncated)
    h.FNDISCAMT1                                                     AS disc_baht,
    h.FNAMT                                                          AS amtbfvat,
    h.FNVATAMT                                                       AS vat,
    h.FNAMT + h.FNVATAMT                                             AS totamt,
    h.FCSTAT, h.FCSTEP, h.FCVATISOUT, h.FCVATTYPE, h.FCDISCSTR
FROM so h
LEFT JOIN dbo.COOR c ON c.FCSKID = h.FCCOOR
LEFT JOIN dbo.SECT s ON s.FCSKID = h.FCSECT
ORDER BY [no];

/* ---------- Q2. Order lines (report run > 0, subhdlevel = 2) ---------- */
WITH so AS (
    SELECT h.*
    FROM dbo.ORDERH h
    JOIN dbo.BOOK   b  ON b.FCSKID  = h.FCBOOK
    JOIN dbo.CORP   co ON co.FCSKID = h.FCCORP
    JOIN dbo.BRANCH br ON br.FCSKID = h.FCBRANCH
    WHERE h.FCREFTYPE = 'SO' AND b.FCCODE = '0001'
      AND co.FCCODE = '0001' AND br.FCCODE = '00000'
      AND h.FDDATE >= @d1 AND h.FDDATE < DATEADD(day, 1, @d2)
)
SELECT
    h.FCCODE                                    AS docno,
    h.FCSTAT,
    ROW_NUMBER() OVER (PARTITION BY h.FCSKID ORDER BY i.FCSEQ) AS run,
    RTRIM(i.FCREFPDTYP) + RTRIM(i.FCPRODTYPE)   AS prodtype,      -- e.g. P1
    p.FCCODE                                    AS prodcode,
    p.FCNAME                                    AS prodname,
    CAST(i.FMREMARK AS nvarchar(max))           AS remark,        -- report splits this over continuation rows
    i.FNPRICE                                   AS prodprice,
    i.FCDISCSTR                                 AS itemdisc,
    i.FNDISCAMT                                 AS itemdisc_baht,
    i.FNQTY                                     AS qty,
    u.FCNAME                                    AS unit,
    i.FNQTY * i.FNUMQTY                         AS stdqty,
    us.FCNAME                                   AS stdunit,
    ROUND((i.FNQTY * i.FNPRICE - i.FNDISCAMT)
          * CASE WHEN h.FNAMT + h.FNDISCAMT1 <> 0
                 THEN h.FNAMT / (h.FNAMT + h.FNDISCAMT1) ELSE 1 END, 2) AS amtitem,  -- net of pro-rata header discount
    CAST(i.FDDELIVERY AS date)                  AS duedate2,
    i.FNBACKQTY, i.FNDOQTY
FROM so h
JOIN dbo.ORDERI i  ON i.FCORDERH = h.FCSKID
LEFT JOIN dbo.PROD p  ON p.FCSKID  = i.FCPROD
LEFT JOIN dbo.UM   u  ON u.FCSKID  = i.FCUM
LEFT JOIN dbo.UM   us ON us.FCSKID = i.FCUMSTD
ORDER BY h.FDDATE, h.FCREFNO, h.FCCODE, run;

/* ---------- Q3. Delivery notes / invoices against each SO line (subhdlevel = 3) ----------
   NOTECUT: master = downstream doc (DO or SI), child = the SO line.
   DO lives in DORDERH/DORDERI; SI lives in GLREF/REFPROD.                              */
WITH so AS (
    SELECT h.*
    FROM dbo.ORDERH h
    JOIN dbo.BOOK   b  ON b.FCSKID  = h.FCBOOK
    JOIN dbo.CORP   co ON co.FCSKID = h.FCCORP
    JOIN dbo.BRANCH br ON br.FCSKID = h.FCBRANCH
    WHERE h.FCREFTYPE = 'SO' AND b.FCCODE = '0001'
      AND co.FCCODE = '0001' AND br.FCCODE = '00000'
      AND h.FDDATE >= @d1 AND h.FDDATE < DATEADD(day, 1, @d2)
)
SELECT
    h.FCCODE                                     AS docno,
    i.FCSEQ                                      AS so_seq,
    n.FCMASTERTY                                 AS inv_type,     -- DO / SI
    CAST(COALESCE(dh.FDDATE, g.FDDATE) AS date)  AS invdate,
    COALESCE(dh.FCREFNO, g.FCREFNO)              AS invrefno,     -- printed ref no. (e.g. 27839, N69090001)
    COALESCE(dh.FCCODE, g.FCCODE)                AS inv_docno,
    COALESCE(di.FCDISCSTR, rp.FCDISCSTR)         AS invdisc,
    COALESCE(di.FNPRICE, rp.FNPRICE)             AS invprice,
    n.FNQTY                                      AS invqty,
    u.FCNAME                                     AS invunit,
    COALESCE(dh.FCSTAT, g.FCSTAT)                AS inv_stat
FROM so h
JOIN dbo.ORDERI  i  ON i.FCORDERH = h.FCSKID
JOIN dbo.NOTECUT n  ON n.FCCHILDTYP = 'SO' AND n.FCCHILDH = h.FCSKID AND n.FCCHILDI = i.FCSKID
LEFT JOIN dbo.DORDERH dh ON n.FCMASTERTY = 'DO' AND dh.FCSKID = n.FCMASTERH
LEFT JOIN dbo.DORDERI di ON n.FCMASTERTY = 'DO' AND di.FCSKID = n.FCMASTERI
LEFT JOIN dbo.GLREF   g  ON n.FCMASTERTY = 'SI' AND g.FCSKID  = n.FCMASTERH
LEFT JOIN dbo.REFPROD rp ON n.FCMASTERTY = 'SI' AND rp.FCSKID = n.FCMASTERI
LEFT JOIN dbo.UM      u  ON u.FCSKID = COALESCE(di.FCUM, rp.FCUM)
ORDER BY h.FDDATE, h.FCREFNO, h.FCCODE, i.FCSEQ, invdate, invrefno;

/* ---------- Q4. Grand totals to compare with the report footer ---------- */
WITH so AS (
    SELECT h.*
    FROM dbo.ORDERH h
    JOIN dbo.BOOK   b  ON b.FCSKID  = h.FCBOOK
    JOIN dbo.CORP   co ON co.FCSKID = h.FCCORP
    JOIN dbo.BRANCH br ON br.FCSKID = h.FCBRANCH
    WHERE h.FCREFTYPE = 'SO' AND b.FCCODE = '0001'
      AND co.FCCODE = '0001' AND br.FCCODE = '00000'
      AND h.FDDATE >= @d1 AND h.FDDATE < DATEADD(day, 1, @d2)
)
SELECT
    COUNT(*)                                                       AS docs_all,
    SUM(CASE WHEN FCSTAT = 'C' THEN 1 ELSE 0 END)                  AS docs_cancelled,
    SUM(CASE WHEN FCSTAT <> 'C' THEN FNAMT + FNDISCAMT1 ELSE 0 END) AS amt,        -- expect 17,663,486.95
    SUM(CASE WHEN FCSTAT <> 'C' THEN FNAMT ELSE 0 END)             AS amtbfvat,    -- expect 17,650,247.73
    SUM(CASE WHEN FCSTAT <> 'C' THEN FNVATAMT ELSE 0 END)          AS vat,         -- expect  1,225,820.39
    SUM(CASE WHEN FCSTAT <> 'C' THEN FNAMT + FNVATAMT ELSE 0 END)  AS totamt,      -- expect 18,876,068.12
    (SELECT COUNT(*) FROM dbo.ORDERI i WHERE i.FCORDERH IN (SELECT FCSKID FROM so)) AS lines_all  -- expect 675
FROM so;
