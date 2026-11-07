"""
Shared settings for the report scripts.

- Windows auth to the local SQL Server 'server', database FORMULA, read-only.
- CHAR data is fetched as latin-1 and decoded as cp874 (as in export_archive.py).
- Files that are not in git (rclone.exe, the Google service-account key) are found under
  EM_HOME, D:\\Em_Project unless the EM_HOME environment variable says otherwise.
  RCLONE_EXE and GOOGLE_SA_KEY override the two paths one by one.
"""

import datetime as dt
import os
import re
import sys

CONN_STR = ("DRIVER={ODBC Driver 13 for SQL Server};SERVER=server;DATABASE=FORMULA;"
            "Trusted_Connection=yes;APP=FORMULA reports (read-only);")
FORBIDDEN = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|EXEC|MERGE|BACKUP|RESTORE)\b", re.I)

EM_HOME = os.environ.get("EM_HOME", r"D:\Em_Project")
RCLONE = os.environ.get("RCLONE_EXE", os.path.join(EM_HOME, "tools", "rclone", "rclone.exe"))
SERVICE_ACCOUNT_KEY = os.environ.get(
    "GOOGLE_SA_KEY", os.path.join(EM_HOME, "config", "yt-analysis-project-402700-6c9fee962152.json"))


def fix_text(s):
    return s.encode("latin-1").decode("cp874", errors="backslashreplace")


def date_option(flag, argv=None):
    """The date after `flag` on the command line (YYYY-MM-DD), or None if the flag is absent.

    Example: `python daily_pbuyord.py --start 2025-01-01 --end 2025-12-31`.
    """
    argv = sys.argv if argv is None else argv
    if flag not in argv:
        return None
    i = argv.index(flag)
    if i + 1 >= len(argv):
        raise SystemExit(f"{flag} needs a date, e.g. {flag} 2025-01-01")
    try:
        return dt.date.fromisoformat(argv[i + 1])
    except ValueError:
        raise SystemExit(f"{flag} {argv[i + 1]!r}: use YYYY-MM-DD, e.g. 2025-01-01")
