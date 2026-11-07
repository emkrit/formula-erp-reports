import csv, sys, collections, datetime as dt, re
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Em_Project\reports\common")
from formula_db import CONN_STR, fix_text
import gspread, pyodbc
gc = gspread.service_account(filename=r"D:\Em_Project\config\yt-analysis-project-402700-6c9fee962152.json")
sh = gc.open_by_key("17IUycqF7OmTIo3G5xgBkXy21xAdWD0Eycpbp7kNMHSc")
print("tabs:", [(w.title, w.row_count, w.col_count) for w in sh.worksheets()])
vals = sh.worksheet("PDISITM1_Claude").get_all_values()
rd = csv.reader(open(r"D:\Em_Project\reports\PDISITM1\PDISITM1_claude.csv", encoding="utf-8-sig"))
head = next(rd); rows = list(rd)
print("csv rows", len(rows), "sheet rows", len(vals)-1, "cols", len(vals[0])); print("headings", vals[0])
TEXT={"gbranch","gacchart","gbankdoc","gchqno","gchqstat","branch","code","poststep","desc","rowtype","acctname","detail"}
tot=0
for i,c in enumerate(head):
    if c in TEXT:
        d=[(r[9],r[i],v[i]) for r,v in zip(rows,vals[1:]) if r[i].strip()!=v[i].strip()]; tot+=len(d)
        if d: print(" ",c,len(d),d[:3])
    else:
        num=c not in("date","gchqdate")
        d=[]
        for r,v in zip(rows,vals[1:]):
            if num:
                a=float(r[i]) if r[i] else None; b=float(v[i].replace(",","")) if v[i] else None
                if a!=b: d.append((r[9],r[i],v[i]))
            elif r[i]!=v[i]: d.append((r[9],r[i],v[i]))
        print(" ",c,"diff",len(d),d[:2])
print("text cell differences", tot, "| error cells", sum(1 for v in vals for x in v if x.startswith("#")))
print("row2", vals[1][:12])
for t in ("PDISITM1","B01","search"):
    print(t, "reads:", sh.worksheet(t).get("A1:C3")[:2])
L=[r for r in rows if r[15]=="LINE"]
print("dates",min(r[7] for r in L),max(r[7] for r in L),"docs",len({r[9] for r in L}),"lines",len(L),"bank",len(rows)-len(L),"accts",len({r[1] for r in L}))
print("debit",round(sum(float(r[12]) for r in L),2),"credit",round(sum(float(r[13]) for r in L),2))
cn = pyodbc.connect(CONN_STR, readonly=True, autocommit=True, timeout=30)
cn.setdecoding(pyodbc.SQL_CHAR, encoding="latin-1"); cn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16le")
c=cn.cursor(); c.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;")
c.execute("""SELECT b.FCCODE, v.FCCODE, v.FTDATETIME, v.FTLASTUPD FROM dbo.GLHEAD v JOIN dbo.ACCBOOK b ON b.FCSKID=v.FCACCBOOK JOIN dbo.CORP co ON co.FCSKID=v.FCCORP JOIN dbo.BRANCH br ON br.FCSKID=v.FCBRANCH WHERE co.FCCODE='0001' AND br.FCCODE='00000' AND v.FDDATE>='2026-01-01' AND v.FDDATE<'2026-11-01' AND v.FTDATETIME>='2026-11-04 10:50:00'""")
x=[(fix_text(a).strip()+fix_text(b).strip(),str(t)[11:19]) for a,b,t,u in c.fetchall()]
print("vouchers created after the sample",len(x),sorted(x,key=lambda z:z[1]))
c.execute("""SELECT COUNT(*) FROM dbo.GLHEAD v JOIN dbo.CORP co ON co.FCSKID=v.FCCORP JOIN dbo.BRANCH br ON br.FCSKID=v.FCBRANCH WHERE co.FCCODE='0001' AND br.FCCODE='00000' AND v.FDDATE>='2026-01-01' AND v.FDDATE<'2026-11-01' AND v.FTLASTUPD>='2026-11-04 10:50:00' AND v.FTDATETIME<'2026-11-04 10:50:00'"""); print("older vouchers edited after the sample",c.fetchone()[0])
