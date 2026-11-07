"""Summary of PPDOR2_claude.csv: size, dates, books, amounts, and where inamt and backamt differ."""

import collections
import csv
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
r = list(csv.DictReader(open(os.path.join(HERE, "..", "PPDOR2_claude.csv"), encoding="utf-8-sig")))
print("rows", len(r), "| documents", len({x["refno"] + x["docdate"] for x in r}), "| products", len({x["gprod"] for x in r}))
print("by book", collections.Counter(x["book"] for x in r))
print("required dates", min(x["recedate"] for x in r), max(x["recedate"] for x in r))
print("document dates", min(x["docdate"] for x in r), max(x["docdate"] for x in r))
print("backqty %.2f | inamt %.2f | backamt %.2f" % (
    sum(float(x["backqty"]) for x in r), sum(float(x["inamt"]) for x in r), sum(float(x["backamt"]) for x in r)))
d = [x for x in r if abs(float(x["inamt"]) - float(x["backamt"])) > 0.005]
print("lines where inamt differs from backamt:", len(d), "| gap %.2f" % sum(float(x["inamt"]) - float(x["backamt"]) for x in d))
y = [x for x in r if abs(float(x["backqty"]) - float(x["fnbackqty"])) > 0.005]
print("lines where backqty differs from fnbackqty:", len(y))
print("lines with no price:", sum(float(x["inprice"]) == 0 for x in r))
