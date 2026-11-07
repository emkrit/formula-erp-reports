/* =====================================================================
   PPDOR2 - รายงานสินค้าค้างรับแยกตามสินค้า (outstanding goods to receive, by product)
   Reproduces D:\Em_Project\Sample report\PPDOR2.CSV (saved 04/11/2026 15:04)
   SELECT-only. Database: FORMULA (SQL Server 2017), schema dbo.

   Parameters taken from the sample header and Sample report\Readme.txt:
     company  : CORP.FCCODE 0001 = A K & J Textile, branch 00000
     books    : all PO books; the Readme says no book range, and the sample prints 0001 and 0002
     products : 001 - บ80000059, all
     dates    : @d1 - @d2 on the required delivery date (ORDERI.FDDELIVERY), set by daily_ppdor2.py

   Layout: the sample prints a heading and a subtotal for each product. This query returns the
   order lines only; subtotals can be added up from them.
   ===================================================================== */
SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;   -- don't take locks on the live ERP

DECLARE @d1 date = '2025-01-01', @d2 date = '2026-11-30';

/* ---------- Q1. Report rows: one row per open order line ----------
   Rules:
     code     = 'PO' + book + '/' + FCCODE
     coorname = short name (Readme: ชื่อย่อ)
     qcsect   = SECT.FCCODE
     backqty  = FNQTY less the larger of received (GB) and invoiced (BI/BV/BR), cancelled
                documents left out; lines with nothing outstanding are left out.
                fnbackqty is Formula's own field, which ignores goods received but not invoiced
     inprice  = FNPRICEKE, in the document's currency; xrate = FNXRATE
     inamt    = in baht: FNBACKQTY * FNPRICEKE * FNXRATE less the line's share of the bill discount.
                The sample uses FNBACKQTY here even where it prints a lower backqty
     backamt  = the same value worked out on backqty                                            */
SELECT
    p.FCCODE                                    AS gprod,
    p.FCNAME                                    AS prodname,
    CAST(i.FDDELIVERY AS date)                  AS recedate,
    h.FCREFNO                                   AS refno,
    'PO' + b.FCCODE + '/' + h.FCCODE            AS code,
    c.FCSNAME                                   AS coorname,
    s.FCCODE                                    AS qcsect,
    i.FNQTY                                     AS orderqty,
    k.backqty,
    u.FCNAME                                    AS umname,
    i.FNPRICEKE                                 AS inprice,
    i.FNXRATE                                   AS xrate,
    ROUND(CAST(i.FNBACKQTY * i.FNPRICEKE * i.FNXRATE AS decimal(24, 8)) * n.share, 2) AS inamt,
    ROUND(CAST(k.backqty   * i.FNPRICEKE * i.FNXRATE AS decimal(24, 8)) * n.share, 2) AS backamt,
    d.received,
    d.invoiced,
    i.FNBACKQTY                                 AS fnbackqty,
    i.FCSTEP                                    AS linestep,
    h.FCSTEP                                    AS docstep,
    CAST(h.FDDATE AS date)                      AS docdate,
    b.FCCODE                                    AS book
FROM dbo.ORDERI i
JOIN dbo.ORDERH  h  ON h.FCSKID  = i.FCORDERH
JOIN dbo.BOOK    b  ON b.FCSKID  = h.FCBOOK
JOIN dbo.CORP    co ON co.FCSKID = h.FCCORP
JOIN dbo.BRANCH  br ON br.FCSKID = h.FCBRANCH
JOIN dbo.PROD    p  ON p.FCSKID  = i.FCPROD
LEFT JOIN dbo.COOR c ON c.FCSKID = h.FCCOOR
LEFT JOIN dbo.SECT s ON s.FCSKID = h.FCSECT
LEFT JOIN dbo.UM   u ON u.FCSKID = i.FCUM
CROSS APPLY (SELECT h.FNAMT + h.FNDISCAMT1
                    + CASE WHEN h.FCVATISOUT = 'N' THEN h.FNVATAMT ELSE 0 END AS amt) t
CROSS APPLY (SELECT CASE WHEN t.amt = 0 THEN CAST(1 AS decimal(20, 12))
                         ELSE CAST((t.amt - h.FNDISCAMT1) / t.amt AS decimal(20, 12)) END AS share) n
OUTER APPLY (
    SELECT COALESCE(SUM(CASE WHEN n.FCMASTERTY =  'GB' THEN n.FNQTY END), 0) AS received,
           COALESCE(SUM(CASE WHEN n.FCMASTERTY <> 'GB' THEN n.FNQTY END), 0) AS invoiced
    FROM dbo.NOTECUT n
    LEFT JOIN dbo.DORDERH dh ON n.FCMASTERTY = 'GB'  AND dh.FCSKID = n.FCMASTERH
    LEFT JOIN dbo.GLREF   g  ON n.FCMASTERTY <> 'GB' AND g.FCSKID  = n.FCMASTERH
    WHERE n.FCCHILDTYP = 'PO' AND n.FCCHILDI = i.FCSKID
      AND COALESCE(dh.FCSTAT, g.FCSTAT, '') <> 'C') d
CROSS APPLY (SELECT i.FNQTY - CASE WHEN d.received > d.invoiced THEN d.received ELSE d.invoiced END AS backqty) k
WHERE h.FCREFTYPE = 'PO'
  AND co.FCCODE   = '0001'
  AND br.FCCODE   = '00000'
  AND h.FCSTAT   <> 'C'
  AND i.FCSTAT   <> 'C'
  AND i.FCSTEP NOT IN ('L', 'P')
  AND k.backqty > 0
  AND i.FDDELIVERY >= @d1 AND i.FDDELIVERY < DATEADD(day, 1, @d2)
ORDER BY p.FCCODE COLLATE Latin1_General_BIN, i.FDDELIVERY, h.FCREFNO COLLATE Latin1_General_BIN, i.FCSEQ;
