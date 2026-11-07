/* =====================================================================
   PGDRCVNT - รายงานใบรับของชั่วคราว รายการสินค้า และ รายการ Invoice ที่ส่งของ เรียงตามวันที่เอกสาร
   Reproduces D:\Em_Project\Sample report\PGDRCVNT.CSV (saved 09/06/2026 11:05)
   SELECT-only. Database: FORMULA (SQL Server 2017), schema dbo.

   Parameters taken from the sample header:
     book     : GB book 0002 (ใบรับของชั่วคราว ต่างประเทศ)
     company  : CORP.FCCODE 0001 = A K & J Textile, branch 00000

   Layout: the sample prints each receipt on three levels (document, product, invoice) and
   repeats the parent fields. This query returns the same data as one flat table:
   one row per receipt line + invoice; a line with no invoice yet gets one row, invoice columns blank.

   Links (NOTECUT):
     GB line -> invoice  : child = GB line, master = BI/BV/BR (GLREF / REFPROD)
     GB line -> PO line  : master = GB line, child = PO (ORDERH)
   ===================================================================== */
SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;   -- don't take locks on the live ERP

DECLARE @d1 date = '2025-01-01', @d2 date = '2026-12-31';

/* ---------- Q1. Report rows: one row per receipt line + invoice ----------
   Rules confirmed against the sample:
     ab         = FCSTAT (C = cancelled) + FCSTEP (1 not fully delivered, P fully delivered, L closed)
     amtbfdisc  = FNAMT + FNDISCAMT1; FNAMT is after the header discount
     totamt     = FNAMT + FNVATAMT
     disc       = FNDISCAMT1 in baht, so amtbfdisc - disc + vat = totamt. The sample prints a much
                  smaller figure here (0.08 for 767.59 on 10275), but its own totals only add up with baht
     refpo      = the PO linked to the receipt first (one per document, repeated on every row);
                  refpo_line is the PO of this particular line, which often differs
     prodprice  = FNPRICEKE (document currency); invprice = REFPROD.FNPRICE (baht)
     stdqty     = FNQTY * FNUMQTY; invqtystd = NOTECUT.FNQTY * NOTECUT.FNUMQTY
     prodname, sect: full text; the sample cuts them short                                    */
SELECT
    b.FCCODE                                    AS book,
    h.FCCODE                                    AS code,
    h.FCSTAT,
    h.FCSTEP,
    CAST(h.FDDATE AS date)                      AS [date],
    h.FCREFNO                                   AS refno,
    c.FCCODE                                    AS coorcode,
    c.FCSNAME                                   AS coorname,
    s.FCNAME                                    AS sect,
    h.FNAMT + h.FNDISCAMT1                      AS amtbfdisc,
    h.FNDISCAMT1                                AS disc,
    h.FNVATAMT                                  AS vat,
    h.FNAMT + h.FNVATAMT                        AS totamt,
    (SELECT TOP 1 po.FCREFNO
       FROM dbo.NOTECUT n2
       JOIN dbo.ORDERH po ON po.FCSKID = n2.FCCHILDH
      WHERE n2.FCMASTERTY = 'GB' AND n2.FCCHILDTYP = 'PO' AND n2.FCMASTERH = h.FCSKID
      ORDER BY n2.FTDATETIME)                   AS refpo,
    (SELECT TOP 1 po.FCREFNO
       FROM dbo.NOTECUT n2
       JOIN dbo.ORDERH po ON po.FCSKID = n2.FCCHILDH
      WHERE n2.FCMASTERTY = 'GB' AND n2.FCCHILDTYP = 'PO' AND n2.FCMASTERI = i.FCSKID
      ORDER BY n2.FTDATETIME)                   AS refpo_line,
    ROW_NUMBER() OVER (PARTITION BY h.FCSKID, i.FCSKID ORDER BY n.FTDATETIME) AS inv_no,
    DENSE_RANK() OVER (PARTITION BY h.FCSKID ORDER BY i.FCSEQ, i.FCSKID)      AS run,
    p.FCCODE                                    AS prodcode,
    p.FCNAME                                    AS prodname,
    i.FNPRICEKE                                 AS prodprice,
    i.FCDISCSTR                                 AS itemdisc,
    i.FNQTY                                     AS qty,
    u.FCNAME                                    AS unit,
    i.FNQTY * i.FNUMQTY                         AS stdqty,
    us.FCNAME                                   AS stdunit,
    i.FNSTQTY                                   AS stqty,
    st.FCNAME                                   AS stunit,
    i.FNBACKQTY                                 AS bakmsg,
    n.FCMASTERTY                                AS invtype,
    CAST(g.FDDATE AS date)                      AS invdate,
    g.FCREFNO                                   AS invcode,
    g.FCSTAT                                    AS invstat,
    r.FCDISCSTR                                 AS invdisc,
    r.FNPRICE                                   AS invprice,
    n.FNQTY                                     AS invqty,
    ru.FCNAME                                   AS invunit,
    n.FNQTY * n.FNUMQTY                         AS invqtystd,
    rs.FCNAME                                   AS invstdunit
FROM dbo.DORDERH h
JOIN dbo.BOOK    b  ON b.FCSKID  = h.FCBOOK
JOIN dbo.CORP    co ON co.FCSKID = h.FCCORP
JOIN dbo.BRANCH  br ON br.FCSKID = h.FCBRANCH
JOIN dbo.DORDERI i  ON i.FCDORDERH = h.FCSKID
LEFT JOIN dbo.COOR c   ON c.FCSKID  = h.FCCOOR
LEFT JOIN dbo.SECT s   ON s.FCSKID  = h.FCSECT
LEFT JOIN dbo.PROD p   ON p.FCSKID  = i.FCPROD
LEFT JOIN dbo.UM   u   ON u.FCSKID  = i.FCUM
LEFT JOIN dbo.UM   us  ON us.FCSKID = i.FCUMSTD
LEFT JOIN dbo.UM   st  ON st.FCSKID = i.FCSTUM
LEFT JOIN dbo.NOTECUT n ON n.FCCHILDTYP = 'GB' AND n.FCCHILDI = i.FCSKID
LEFT JOIN dbo.GLREF   g ON g.FCSKID = n.FCMASTERH
LEFT JOIN dbo.REFPROD r ON r.FCSKID = n.FCMASTERI
LEFT JOIN dbo.UM   ru  ON ru.FCSKID = r.FCUM
LEFT JOIN dbo.UM   rs  ON rs.FCSKID = r.FCUMSTD
WHERE h.FCREFTYPE = 'GB'
  AND co.FCCODE   = '0001'
  AND br.FCCODE   = '00000'
  AND b.FCCODE    = '0002'
  AND h.FDDATE >= @d1 AND h.FDDATE < DATEADD(day, 1, @d2)
ORDER BY h.FDDATE, h.FCREFNO, h.FCCODE, i.FCSEQ, n.FTDATETIME;
