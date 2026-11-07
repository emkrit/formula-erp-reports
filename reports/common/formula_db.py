"""
Shared settings for the report scripts.

- Windows auth to the local SQL Server 'server', database FORMULA, read-only.
- CHAR data is fetched as latin-1 and decoded as cp874 (as in export_archive.py).
"""

import re

CONN_STR = ("DRIVER={ODBC Driver 13 for SQL Server};SERVER=server;DATABASE=FORMULA;"
            "Trusted_Connection=yes;APP=FORMULA reports (read-only);")
FORBIDDEN = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|EXEC|MERGE|BACKUP|RESTORE)\b", re.I)


def fix_text(s):
    return s.encode("latin-1").decode("cp874", errors="backslashreplace")
