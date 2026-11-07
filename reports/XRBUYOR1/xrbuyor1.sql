/* =====================================================================
   XRBUYOR1 - รายงานใบสั่งซื้อ แสดงข้อมูลตามแนวคอลัมน์ เรียงตาม วันที่เอกสาร
   Reproduces D:\Em_Project\Sample report\XRBUYOR1.CSV (saved 01/09/2026 14:26)
   SELECT-only. Database: FORMULA (SQL Server 2017), schema dbo.

   Inferred parameters (from the CSV header/data - CONFIRM):
     period   : 01/01/2024 - 30/09/2026
     books    : PO book 0001 PO01/ (domestic) + 0002 PO02/ (foreign)
     company  : CORP.FCCODE 0001 = A K & J Textile, branch 00000
     layout   : one row per PO line (subhdlevel 1), no totals

   Receipts against a PO line come from NOTECUT (child = PO line):
     GB (goods receipt)         -> DORDERH / DORDERI
     BI, BV, BR (invoice, ...)  -> GLREF   / REFPROD
   ===================================================================== */
SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;   -- don't take locks on the live ERP

DECLARE @d1 date = '2024-01-01', @d2 date = '2026-09-30';

/* ---------- Q1. Report rows: one row per PO line, with receipt summary ----------
   Rules confirmed against the sample (see differences.md):
     refnogb    = ref no. of the goods receipt (GB) that was linked to the PO line first
                  (NOTECUT.FTDATETIME), not the earliest-dated GB; invoices (BI) are not shown
     qtygb      = total GB quantity
     unreceiqty = qty - qtygb   (negative on over-receipt; FNBACKQTY stops at 0)
     totamt     = ROUND(qty * FNPRICEKE - FNDISCAMTK, 2) * FNXRATE: rounded in the PO currency,
                  then converted to baht. prodprice shows FNPRICE (baht), which on some foreign
                  POs was keyed equal to FNPRICEKE, so prodprice * qty can differ from totamt.
     unreceiamt = ROUND(unreceiqty * net unit price in PO currency, 2) * FNXRATE,
                  net of the line discount; 0 when the line is over-received               */
WITH po AS (
    SELECT h.*, b.FCCODE AS bookcode
    FROM dbo.ORDERH h
    JOIN dbo.BOOK   b  ON b.FCSKID  = h.FCBOOK
    JOIN dbo.CORP   co ON co.FCSKID = h.FCCORP
    JOIN dbo.BRANCH br ON br.FCSKID = h.FCBRANCH
    WHERE h.FCREFTYPE = 'PO'
      AND co.FCCODE   = '0001'
      AND br.FCCODE   = '00000'
      AND h.FDDATE >= @d1 AND h.FDDATE < DATEADD(day, 1, @d2)
),
rc AS (   -- every receiving document per PO line
    SELECT n.FCCHILDI, n.FCMASTERTY,
           COALESCE(dh.FCREFNO, g.FCREFNO) AS refno,
           COALESCE(dh.FDDATE,  g.FDDATE)  AS rdate,
           COALESCE(dh.FCSTAT,  g.FCSTAT)  AS rstat,
           n.FNQTY,
           n.FTDATETIME                    AS linked
    FROM dbo.NOTECUT n
    LEFT JOIN dbo.DORDERH dh ON n.FCMASTERTY = 'GB' AND dh.FCSKID = n.FCMASTERH
    LEFT JOIN dbo.GLREF   g  ON n.FCMASTERTY <> 'GB' AND g.FCSKID = n.FCMASTERH
    WHERE n.FCCHILDTYP = 'PO'
)
SELECT
    h.bookcode,
    h.FCSTAT,
    i.FCSEQ,
    CAST(h.FDDATE AS date)                      AS [date],
    h.FCREFNO                                   AS refno,
    h.FCCODE                                    AS code,
    c.FCCODE                                    AS coorcode,
    p.FCCODE                                    AS prodcode,
    p.FCNAME                                    AS prodname,
    i.FNPRICE                                   AS prodprice,
    i.FCDISCSTR                                 AS itemdisc,
    i.FNQTY                                     AS qty,
    u.FCNAME                                    AS unit,
    ROUND(i.FNQTY * i.FNPRICEKE - i.FNDISCAMTK, 2) * i.FNXRATE          AS totamt,
    gb.refno_first                              AS refnogb,
    ISNULL(gb.qty, 0)                           AS qtygb,
    i.FNQTY - ISNULL(gb.qty, 0)                 AS unreceiqty,
    CASE WHEN i.FNQTY - ISNULL(gb.qty, 0) > 0
         THEN ROUND((i.FNQTY - ISNULL(gb.qty, 0)) * i.FNPRICEKE
                    * CASE WHEN i.FNQTY * i.FNPRICEKE <> 0
                           THEN 1 - i.FNDISCAMTK / (i.FNQTY * i.FNPRICEKE) ELSE 1 END, 2) * i.FNXRATE
         ELSE 0 END                             AS unreceiamt,
    CAST(i.FDDELIVERY AS date)                  AS duedate2,
    s.FCCODE                                    AS sectcode,
    s.FCNAME                                    AS sectname,
    -- diagnostics for the comparison (not report columns)
    i.FCSKID                                    AS line_id,   -- unique; FCSEQ can repeat within a PO
    i.FNXRATE, i.FNPRICEKE, i.FNDISCAMTK,
    i.FNBACKQTY,
    -- receipt candidates for refnogb / qtygb (which one the report prints is checked in the comparison)
    (SELECT COUNT(*) FROM rc WHERE rc.FCCHILDI = i.FCSKID AND rc.FCMASTERTY = 'GB')  AS n_gb,
    (SELECT COUNT(*) FROM rc WHERE rc.FCCHILDI = i.FCSKID AND rc.FCMASTERTY <> 'GB') AS n_bi,
    (SELECT TOP 1 rc.refno FROM rc WHERE rc.FCCHILDI = i.FCSKID AND rc.FCMASTERTY = 'GB'  ORDER BY rc.rdate, rc.refno) AS gb_first,
    (SELECT TOP 1 rc.refno FROM rc WHERE rc.FCCHILDI = i.FCSKID AND rc.FCMASTERTY = 'GB'  ORDER BY rc.rdate DESC, rc.refno DESC) AS gb_last,
    (SELECT TOP 1 rc.refno FROM rc WHERE rc.FCCHILDI = i.FCSKID AND rc.FCMASTERTY <> 'GB' ORDER BY rc.rdate, rc.refno) AS bi_first,
    (SELECT TOP 1 rc.refno FROM rc WHERE rc.FCCHILDI = i.FCSKID AND rc.FCMASTERTY <> 'GB' ORDER BY rc.rdate DESC, rc.refno DESC) AS bi_last,
    (SELECT SUM(rc.FNQTY) FROM rc WHERE rc.FCCHILDI = i.FCSKID AND rc.FCMASTERTY = 'GB')  AS gb_qty,
    (SELECT SUM(rc.FNQTY) FROM rc WHERE rc.FCCHILDI = i.FCSKID AND rc.FCMASTERTY <> 'GB') AS bi_qty,
    i.FNQTY - i.FNBACKQTY                       AS received_qty,
    h.FTLASTUPD                                 AS h_lastupd,
    i.FTLASTUPD                                 AS i_lastupd
FROM po h
JOIN dbo.ORDERI i  ON i.FCORDERH = h.FCSKID
LEFT JOIN dbo.COOR c ON c.FCSKID = h.FCCOOR
LEFT JOIN dbo.PROD p ON p.FCSKID = i.FCPROD
LEFT JOIN dbo.UM   u ON u.FCSKID = i.FCUM
LEFT JOIN dbo.SECT s ON s.FCSKID = h.FCSECT
OUTER APPLY (
    SELECT SUM(rc.FNQTY) AS qty,
           (SELECT TOP 1 r2.refno FROM rc r2
             WHERE r2.FCCHILDI = i.FCSKID AND r2.FCMASTERTY = 'GB' AND ISNULL(r2.rstat, '') <> 'C'
             ORDER BY r2.linked, r2.refno) AS refno_first
    FROM rc
    WHERE rc.FCCHILDI = i.FCSKID AND rc.FCMASTERTY = 'GB' AND ISNULL(rc.rstat, '') <> 'C'
) gb
ORDER BY h.FDDATE, h.FCREFNO, h.FCCODE, i.FCSEQ;

/* ---------- Q2. Every receiving document against each PO line ---------- */
WITH po AS (
    SELECT h.*
    FROM dbo.ORDERH h
    JOIN dbo.CORP   co ON co.FCSKID = h.FCCORP
    JOIN dbo.BRANCH br ON br.FCSKID = h.FCBRANCH
    WHERE h.FCREFTYPE = 'PO' AND co.FCCODE = '0001' AND br.FCCODE = '00000'
      AND h.FDDATE >= @d1 AND h.FDDATE < DATEADD(day, 1, @d2)
)
SELECT
    h.FCCODE                                     AS code,
    i.FCSEQ                                      AS po_seq,
    n.FCMASTERTY                                 AS rec_type,     -- GB / BI / BV / BR
    CAST(COALESCE(dh.FDDATE, g.FDDATE) AS date)  AS rec_date,
    COALESCE(dh.FCREFNO, g.FCREFNO)              AS rec_refno,
    COALESCE(dh.FCCODE, g.FCCODE)                AS rec_docno,
    n.FNQTY                                      AS rec_qty,
    COALESCE(di.FNPRICE, rp.FNPRICE)             AS rec_price,
    COALESCE(dh.FCSTAT, g.FCSTAT)                AS rec_stat,
    n.FTDATETIME                                 AS linked        -- refnogb = first-linked GB
FROM po h
JOIN dbo.ORDERI  i  ON i.FCORDERH = h.FCSKID
JOIN dbo.NOTECUT n  ON n.FCCHILDTYP = 'PO' AND n.FCCHILDH = h.FCSKID AND n.FCCHILDI = i.FCSKID
LEFT JOIN dbo.DORDERH dh ON n.FCMASTERTY = 'GB'  AND dh.FCSKID = n.FCMASTERH
LEFT JOIN dbo.DORDERI di ON n.FCMASTERTY = 'GB'  AND di.FCSKID = n.FCMASTERI
LEFT JOIN dbo.GLREF   g  ON n.FCMASTERTY <> 'GB' AND g.FCSKID  = n.FCMASTERH
LEFT JOIN dbo.REFPROD rp ON n.FCMASTERTY <> 'GB' AND rp.FCSKID = n.FCMASTERI
ORDER BY h.FDDATE, h.FCREFNO, h.FCCODE, i.FCSEQ, rec_date, rec_refno;

/* ---------- Q3. Totals by book and year ---------- */
WITH po AS (
    SELECT h.*, b.FCCODE AS bookcode
    FROM dbo.ORDERH h
    JOIN dbo.BOOK   b  ON b.FCSKID  = h.FCBOOK
    JOIN dbo.CORP   co ON co.FCSKID = h.FCCORP
    JOIN dbo.BRANCH br ON br.FCSKID = h.FCBRANCH
    WHERE h.FCREFTYPE = 'PO' AND co.FCCODE = '0001' AND br.FCCODE = '00000'
      AND h.FDDATE >= @d1 AND h.FDDATE < DATEADD(day, 1, @d2)
)
SELECT h.bookcode, YEAR(h.FDDATE) AS yr,
       SUM(CASE WHEN h.FCSTAT = 'C' THEN 1 ELSE 0 END)                         AS lines_cancelled,
       SUM(CASE WHEN h.FCSTAT <> 'C' THEN 1 ELSE 0 END)                        AS lines,
       SUM(CASE WHEN h.FCSTAT <> 'C' THEN i.FNQTY ELSE 0 END)                  AS qty,
       SUM(CASE WHEN h.FCSTAT <> 'C' THEN ROUND(i.FNQTY * i.FNPRICEKE - i.FNDISCAMTK, 2) * i.FNXRATE ELSE 0 END) AS totamt_baht,
       COUNT(DISTINCT h.FCSKID)                                                AS docs
FROM po h
JOIN dbo.ORDERI i ON i.FCORDERH = h.FCSKID
GROUP BY h.bookcode, YEAR(h.FDDATE)
ORDER BY h.bookcode, yr;
