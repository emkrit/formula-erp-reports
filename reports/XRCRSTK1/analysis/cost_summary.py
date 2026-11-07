import csv, re, sys
sys.stdout.reconfigure(encoding="utf-8")
ROW = re.compile(r'^"(.*)","(.*)",(-?[\d.]+),"(.*)",(-?[\d.]+),(-?[\d.]+),(\d),"(.*)"$')
S={}
for l in open(r"D:\Em_Project\Sample report\XRCRSTK1.CSV","rb").read().decode("cp874").split("\r\n")[1:]:
    m=ROW.match(l)
    if m and m.group(7)=="1": S[m.group(1).strip()]=(float(m.group(3)),float(m.group(5)),float(m.group(6)))
O={r["prodcode"]:r for r in csv.DictReader(open(r"D:\Em_Project\reports\XRCRSTK1\XRCRSTK1_claude.csv",encoding="utf-8-sig"))}
k=[x for x in S if x in O]
nz=[x for x in k if S[x][1]]
print("no discount line: sample",round(sum(S[x][2] for x in k if x!="50000009"),2),"report",round(sum(float(O[x]["amt"]) for x in k if x!="50000009"),2))
d=lambda x:abs(float(O[x]["cost"])-S[x][1])
print("within .015",sum(d(x)<.0151 for x in nz),"within 1%",sum(d(x)<=S[x][1]*.01 for x in nz),"1-5%",sum(S[x][1]*.01<d(x)<=S[x][1]*.05 for x in nz),">5%",sum(d(x)>S[x][1]*.05 for x in nz),"of",len(nz))
print("sample shows no cost, report shows one",sum(1 for x in k if not S[x][1] and float(O[x]["cost"])),"sum amt",round(sum(float(O[x]["amt"]) for x in k if not S[x][1]),2))
print("sample has cost, report none",[(x,S[x]) for x in nz if not float(O[x]["cost"])][:6])
print("bal diff",[(x,S[x][0],O[x]["balance"]) for x in k if abs(float(O[x]["balance"])-S[x][0])>=.005])
