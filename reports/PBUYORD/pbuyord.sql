/* =====================================================================
   PBUYORD - รายงานใบสั่งซื้อ แสดงรายการสินค้า และใบส่งของ เรียงตามวันที่เอกสาร
   Reproduces D:\Em_Project\Sample report\PBUYORD.CSV (saved 04/11/2026 13:24)
   SELECT-only. Database: FORMULA (SQL Server 2017), schema dbo.

   Parameters taken from the sample header and Sample report\Readme.txt:
     company : CORP.FCCODE 0001 = A K & J Textile, branch 00000
     books   : PO books 0001 (domestic) and 0002 (foreign)
     status  : all documents, cancelled included
     dates   : @d1 - @d2, set by daily_pbuyord.py

   Layout: the sample prints each order on three levels (document, product, delivery) and
   repeats the parent fields. This query returns the same data as one flat table:
   one row per order line + delivery document; a line with no delivery gets one row, delivery
   columns blank. The sample's outstanding rows become the columns bakmsg and bakstd.

   Links:
     PO line -> delivery : NOTECUT child = PO line, master = GB (DORDERH/DORDERI)
                           or BI/BV/BR (GLREF/REFPROD)
     PO -> deposit       : DEPREF.FCORDERH -> GLREF (P5)
   ===================================================================== */
SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;   -- don't take locks on the live ERP

DECLARE @d1 date = '2025-01-01', @d2 date = '2026-11-30';

/* ---------- Q1. Report rows: one row per order line + delivery ----------
   Rules confirmed against the sample:
     no        = running number within the book, by date then reference number
     ab        = FCSTAT (C = cancelled) + FCSTEP (1 not fully delivered, P delivered, L closed)
     amt       = before the bill discount: FNAMT + FNDISCAMT1, plus FNVATAMT when VAT is
                 inside the price (FCVATISOUT = N)
     discamt   = the bill discount as a percent of amt; disc_baht is the same discount in baht
     amtbfvat  = FNAMT; totamt = FNAMT + FNVATAMT
     prodprice = FNPRICE; amtitem = qty * FNPRICEKE * FNXRATE less the line discount and its
                 share of the bill discount
     stdqty    = FNQTY * FNUMQTY; stdunit = the product's unit
     bakmsg    = FNQTY less invoiced, or less received when nothing is invoiced yet; negative
                 means over-delivered. fnbackqty is Formula's own field, which stops at 0
     delivery  = linked GB and BI/BV/BR, cancelled documents left out, GB first then by entry time
     invprice  = FNPRICEKE * FNXRATE of the delivery line
     prodname, coorname: full text; the sample cuts them short                                  */
SELECT
    b.FCCODE                                    AS book,
    h.FCCODE                                    AS code,
    DENSE_RANK() OVER (PARTITION BY b.FCCODE ORDER BY h.FDDATE, h.FCREFNO COLLATE Latin1_General_BIN, h.FCSKID) AS [no],
    h.FCSTAT,
    h.FCSTEP,
    CAST(h.FDDATE AS date)                      AS [date],
    h.FCREFNO                                   AS refno,
    c.FCCODE                                    AS coorcode,
    c.FCNAME                                    AS coorname,
    s.FCCODE                                    AS sectcode2,
    s.FCNAME                                    AS sectname,
    t.amt,
    CASE WHEN h.FNAMT = 0 OR t.amt = 0 THEN 0
         ELSE ROUND(h.FNDISCAMT1 * 100.0 / t.amt, 2, 1) END AS discamt,
    h.FNDISCAMT1                                AS disc_baht,
    h.FNAMT                                     AS amtbfvat,
    h.FNVATAMT                                  AS vat,
    h.FNAMT + h.FNVATAMT                        AS totamt,
    dep.depcode,
    dep.depamt,
    CASE WHEN i.FCSKID IS NOT NULL
         THEN DENSE_RANK() OVER (PARTITION BY h.FCSKID ORDER BY i.FCSEQ, i.FCSKID) END AS run,
    i.FCREFPDTYP + i.FCPRODTYPE                 AS prodtype,
    p.FCCODE                                    AS prodcode,
    p.FCNAME                                    AS prodname,
    i.FNPRICE                                   AS prodprice,
    i.FCDISCSTR                                 AS itemdisc,
    i.FNQTY                                     AS qty,
    u.FCNAME                                    AS unit,
    i.FNQTY * i.FNUMQTY                         AS stdqty,
    pu.FCNAME                                   AS stdunit,
    ROUND(CAST(i.FNQTY * i.FNPRICEKE * i.FNXRATE - i.FNDISCAMT AS float)
          * CASE WHEN t.amt = 0 THEN 1 ELSE 1 - CAST(h.FNDISCAMT1 AS float) / CAST(t.amt AS float) END, 2) AS amtitem,
    CAST(i.FDDELIVERY AS date)                  AS duedate2,
    i.FNQTY - CASE WHEN SUM(d.invoiced)  OVER (PARTITION BY i.FCSKID) <> 0
                   THEN SUM(d.invoiced)  OVER (PARTITION BY i.FCSKID)
                   ELSE COALESCE(SUM(d.received) OVER (PARTITION BY i.FCSKID), 0) END AS bakmsg,
    i.FNUMQTY                                   AS line_umqty,
    i.FNBACKQTY                                 AS fnbackqty,
    d.invtype,
    d.invdate,
    d.invrefno,
    d.invdisc,
    d.invprice,
    d.invqty,
    iu.FCNAME                                   AS invunit,
    d.invqtystd,
    ius.FCNAME                                  AS invstdunit
FROM dbo.ORDERH h
JOIN dbo.BOOK    b  ON b.FCSKID  = h.FCBOOK
JOIN dbo.CORP    co ON co.FCSKID = h.FCCORP
JOIN dbo.BRANCH  br ON br.FCSKID = h.FCBRANCH
CROSS APPLY (SELECT h.FNAMT + h.FNDISCAMT1
                    + CASE WHEN h.FCVATISOUT = 'N' THEN h.FNVATAMT ELSE 0 END AS amt) t
LEFT JOIN dbo.ORDERI i  ON i.FCORDERH = h.FCSKID
LEFT JOIN dbo.COOR c    ON c.FCSKID  = h.FCCOOR
LEFT JOIN dbo.SECT s    ON s.FCSKID  = h.FCSECT
LEFT JOIN dbo.PROD p    ON p.FCSKID  = i.FCPROD
LEFT JOIN dbo.UM   u    ON u.FCSKID  = i.FCUM
LEFT JOIN dbo.UM   pu   ON pu.FCSKID = p.FCUM
LEFT JOIN (
    SELECT n.FCCHILDI                                     AS po_line,
           n.FCMASTERTY                                   AS invtype,
           n.FTDATETIME                                   AS entered,
           CAST(COALESCE(dh.FDDATE, g.FDDATE) AS date)    AS invdate,
           COALESCE(dh.FCREFNO, g.FCREFNO)                AS invrefno,
           COALESCE(di.FCDISCSTR, r.FCDISCSTR)            AS invdisc,
           ROUND(COALESCE(di.FNPRICEKE * di.FNXRATE, r.FNPRICEKE * r.FNXRATE), 2) AS invprice,
           n.FNQTY                                        AS invqty,
           n.FNQTY * n.FNUMQTY                            AS invqtystd,
           COALESCE(di.FCUM, r.FCUM)                      AS um,
           COALESCE(di.FCUMSTD, r.FCUMSTD)                AS umstd,
           CASE WHEN n.FCMASTERTY =  'GB' THEN n.FNQTY ELSE 0 END AS received,
           CASE WHEN n.FCMASTERTY <> 'GB' THEN n.FNQTY ELSE 0 END AS invoiced
    FROM dbo.NOTECUT n
    LEFT JOIN dbo.DORDERH dh ON n.FCMASTERTY = 'GB'  AND dh.FCSKID = n.FCMASTERH
    LEFT JOIN dbo.DORDERI di ON n.FCMASTERTY = 'GB'  AND di.FCSKID = n.FCMASTERI
    LEFT JOIN dbo.GLREF   g  ON n.FCMASTERTY <> 'GB' AND g.FCSKID  = n.FCMASTERH
    LEFT JOIN dbo.REFPROD r  ON n.FCMASTERTY <> 'GB' AND r.FCSKID  = n.FCMASTERI
    WHERE n.FCCHILDTYP = 'PO'
      AND COALESCE(dh.FCSTAT, g.FCSTAT, '') <> 'C'
) d ON d.po_line = i.FCSKID
LEFT JOIN dbo.UM   iu   ON iu.FCSKID  = d.um
LEFT JOIN dbo.UM   ius  ON ius.FCSKID = d.umstd
OUTER APPLY (SELECT TOP 1 dg.FCREFNO AS depcode, x.FNAMT AS depamt
               FROM dbo.DEPREF x
               JOIN dbo.GLREF dg ON dg.FCSKID = x.FCGLREF
              WHERE x.FCORDERH = h.FCSKID AND dg.FCSTAT <> 'C'
              ORDER BY x.FTDATETIME) dep
WHERE h.FCREFTYPE = 'PO'
  AND co.FCCODE   = '0001'
  AND br.FCCODE   = '00000'
  AND b.FCCODE IN ('0001', '0002')
  AND h.FDDATE >= @d1 AND h.FDDATE < DATEADD(day, 1, @d2)
ORDER BY b.FCCODE, h.FDDATE, h.FCREFNO COLLATE Latin1_General_BIN, h.FCSKID, i.FCSEQ, i.FCSKID,
         CASE WHEN d.invtype = 'GB' THEN 0 ELSE 1 END, d.entered;
