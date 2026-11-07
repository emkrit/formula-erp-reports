/* =====================================================================
   CUSTDET2 - รายชื่อลูกหนี้ (เรียงตามรหัส)
   Reproduces D:\Em_Project\Sample report\CUSTDET2.CSV (saved 07/10/2026 18:40)
   SELECT-only. Database: FORMULA (SQL Server 2017), schema dbo.

   Parameters taken from the sample header:
     company : CORP.FCCODE 0001 = A K & J Textile
     range   : all customers (the sample's N-001 - ฮ.288 was the whole list on the day it was saved)

   This is a list of customers as they are now, so it has no date filter.
   One row per customer.

   Address, tax ID, fax, email and remarks are not ordinary columns: they are tagged text
   inside the memo columns, e.g. <DEL>Tax0105522000839Tax<DEL>. The query returns the
   memo as it is and daily_custdet2.py reads the tags.
   ===================================================================== */
SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;   -- don't take locks on the live ERP

/* ---------- Q1. Report rows: one row per customer ----------
   Rules confirmed against the sample:
     creddate = FTDATETIME (date the customer was created)
     group    = CRGRP, saleman = EMPL, unitcost = CURRENCY, acchart = ACCHART
     broffice = FCISHEADBR
     vattype  = FCVATTYPE: 1 or blank VAT 7 %, 3 VAT 0 %, 4 no VAT (mapped in the .py)
     status   = FCSTATUS: blank is Active. No other value exists yet (see the .py)            */
SELECT
    c.FCCODE                                    AS code,
    c.FCNAME                                    AS name,
    c.FCSNAME                                   AS sname,
    c.FCTEL                                     AS tel,
    c.FCSTATUS,
    CAST(c.FDINACTIVE AS date)                  AS inacdate,
    c.FCPERSONTY                                AS personty,
    CAST(c.FTDATETIME AS date)                  AS creddate,
    a.FCCODE                                    AS acchart_code,
    a.FCNAME                                    AS acchart_name,
    c.FCCONTACTN                                AS percont,
    g.FCCODE                                    AS group_code,
    g.FCNAME                                    AS group_name,
    e.FCCODE                                    AS saleman_code,
    e.FCNAME                                    AS saleman_name,
    c.FNCREDLIM                                 AS credlimit,
    c.FNCREDTERM                                AS credterm,
    c.FCISHEADBR                                AS broffice,
    c.FCBRANCHNO                                AS branchno,
    c.FCBRANCHNM                                AS branchnm,
    c.FCVATTYPE,
    cu.FCSIGN                                   AS currency_sign,
    cu.FCNAME                                   AS currency_name,
    c.FCNO                                      AS [no],
    c.FCFLOOR                                   AS [floor],
    c.FCROOMNO                                  AS room,
    c.FCBUILDING                                AS building,
    c.FCMOO                                     AS moo,
    c.FCSOI                                     AS soi,
    c.FCROAD                                    AS road,
    c.FCTAMBON                                  AS tambon,
    c.FCAMPHUR                                  AS amphur,
    c.FCPROVINCE                                AS prov,
    c.FCZIP                                     AS zip,
    c.FTLASTUPD                                 AS lastupd,
    CAST(ISNULL(c.FMMEMDATA,  '') AS varchar(max)) + ISNULL(c.FMMEMDATA2, '') + ISNULL(c.FMMEMDATA3, '')
        + ISNULL(c.FMMEMDATA4, '') + ISNULL(c.FMMEMDATA5, '') + ISNULL(c.FMMEMDATA6, '')
        + ISNULL(c.FMMEMDATA7, '') + ISNULL(c.FMMEMDATA8, '') + ISNULL(c.FMMEMDATA9, '')
        + ISNULL(c.FMMEMDATAA, '')              AS memo
FROM dbo.COOR c
JOIN dbo.CORP co ON co.FCSKID = c.FCCORP
LEFT JOIN dbo.CRGRP    g  ON g.FCSKID  = c.FCCRGRP
LEFT JOIN dbo.EMPL     e  ON e.FCSKID  = c.FCEMPL
LEFT JOIN dbo.CURRENCY cu ON cu.FCSKID = c.FCCURRENCY
LEFT JOIN dbo.ACCHART  a  ON a.FCSKID  = c.FCACCHART
WHERE c.FCISCUST = 'Y'
  AND co.FCCODE  = '0001'
ORDER BY c.FCCODE;
