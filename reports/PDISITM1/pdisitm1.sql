/* =====================================================================
   PDISITM1 - รายการแยกประเภท มีรายละเอียด (general ledger listing with details)
   Reproduces D:\Em_Project\Sample report\PDISITM1.CSV (saved 04/11/2026 10:50)
   SELECT-only. Database: FORMULA (SQL Server 2017), schema dbo.

   Parameters taken from the sample header and Sample report\Readme.txt:
     company : CORP.FCCODE 0001 = A K & J Textile
     branch  : 00000 head office
     dates   : 01/01/2026 - 31/10/2026
     accounts: 1 - 99999, accounts with movement, posted and not yet posted

   Layout: the sample prints bank documents as rows under a ledger line, and also prints
   totals. This file returns ledger lines (Q1) and bank documents (Q2);
   daily_pdisitm1.py puts them in the sample's order and works out the running balance.
   Totals rows aren't kept, because they can be added up from the ledger lines.
   ===================================================================== */
SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;   -- don't take locks on the live ERP

DECLARE @d1 date = '2026-01-01', @d2 date = '2026-10-31';

/* ---------- Q1. Ledger lines: one row per GL line ----------
   Rules confirmed against the sample:
     code     = ACCBOOK.FCCODE + GLHEAD.FCCODE (SC + 69010214)
     desc     = GLHEAD.FMREMARK, for every line of the voucher; GL.FMDETAIL is not printed
     dramt    = FNAMT when positive; cramt = -FNAMT when negative
     poststep = GL.FCATSTEP                                                                   */
SELECT
    v.FCSKID                                    AS voucher_id,
    br.FCCODE                                   AS gbranch,
    a.FCCODE                                    AS gacchart,
    a.FCNAME                                    AS acctname,
    CAST(v.FDDATE AS date)                      AS [date],
    b.FCCODE                                    AS book,
    v.FCCODE                                    AS voucher,
    g.FCSEQ                                     AS seq,
    g.FCATSTEP                                  AS poststep,
    v.FMREMARK                                  AS [desc],
    g.FMDETAIL                                  AS detail,
    g.FNAMT                                     AS amt
FROM dbo.GL g
JOIN dbo.GLHEAD  v  ON v.FCSKID  = g.FCGLHEAD
JOIN dbo.ACCHART a  ON a.FCSKID  = g.FCACCHART
JOIN dbo.CORP    co ON co.FCSKID = g.FCCORP
JOIN dbo.BRANCH  br ON br.FCSKID = g.FCBRANCH
JOIN dbo.ACCBOOK b  ON b.FCSKID  = v.FCACCBOOK
WHERE co.FCCODE = '0001'
  AND br.FCCODE = '00000'
  AND v.FDDATE >= @d1 AND v.FDDATE < DATEADD(day, 1, @d2)
ORDER BY a.FCCODE, v.FDDATE, v.FCCODE, g.FCSEQ, b.FCCODE;

/* ---------- Q2. Bank documents of those vouchers ----------
   Rules confirmed against the sample:
     PAYMENT : gbankdoc = FCPAYTYPE, gchqno = FCCODE, gchqstat = FCSTAT,
               gchqdate = FDDUEDATE, gchqamt = FNAMT
     PAYINH  : gbankdoc = PAY, gchqno = FCCODE, gchqdate = FDDATE, gchqamt = FNAMT
     owner   : PAYMENT.FCDOCOWNER, used by the .py to place the document under a line          */
SELECT
    d.voucher_id, d.gbankdoc, d.gchqno, d.gchqstat, d.gchqdate, d.gchqamt, d.owner_type, d.acct, d.seq
FROM (
    SELECT p.FCGLHEAD AS voucher_id, p.FCPAYTYPE AS gbankdoc, p.FCCODE AS gchqno, p.FCSTAT AS gchqstat,
           CAST(p.FDDUEDATE AS date) AS gchqdate, p.FNAMT AS gchqamt, p.FCDOCOWNER AS owner_type,
           a.FCCODE AS acct, p.FCSEQ AS seq
    FROM dbo.PAYMENT p
    LEFT JOIN dbo.ACCHART a ON a.FCSKID = p.FCACCHART
    UNION ALL
    SELECT h.FCGLHEAD, 'PAY', h.FCCODE, '', CAST(h.FDDATE AS date), h.FNAMT, 'PAYIN', NULL, ''
    FROM dbo.PAYINH h
) d
JOIN dbo.GLHEAD v  ON v.FCSKID  = d.voucher_id
JOIN dbo.CORP   co ON co.FCSKID = v.FCCORP
JOIN dbo.BRANCH br ON br.FCSKID = v.FCBRANCH
WHERE co.FCCODE = '0001'
  AND br.FCCODE = '00000'
  AND v.FDDATE >= @d1 AND v.FDDATE < DATEADD(day, 1, @d2)
ORDER BY d.voucher_id, d.seq, d.gchqno;
