#!/usr/bin/env python3
"""
Run the Formula reports that are due, as set in the "Formula Report Schedule" Google Sheet.

GitHub Actions starts this on the Formula server every 30 minutes (.github/workflows/report-schedule.yml).
For each row of the Schedule tab it works out whether the task is due, runs
reports/<TASK>/daily_<task>.py with the row's dates (query -> CSV -> Google Drive), then the
Sheets upload script if "Upload to Sheets" is ticked. It writes the result back to the row
(columns "Last run" to "Last message") and adds a row to the Run log tab.

A task is due when the latest of its run times, on one of its run days, has passed since its
last run and is less than CATCH_UP_HOURS old. "Run now" runs a task at the next check whatever
its schedule (even when it is not enabled) and is then unticked.

Usage:
    python scheduler/run_schedule.py                      check the sheet and run what is due
    python scheduler/run_schedule.py --dry-run            only show what is due; runs and writes nothing
    python scheduler/run_schedule.py --task PPDOR2        run one task now with the sheet's data period
    python scheduler/run_schedule.py --task PPDOR2 --start 2025-01-01 --end 2025-06-30
                                                          run one task now for these dates
Testing options: --now "2026-11-09 06:10" (pretend it is this Thailand time),
                 --rows-json rows.json (read the Schedule rows from a file instead of the sheet).

Exit code 0 = every task that ran succeeded, 1 = at least one failed (the GitHub run turns red).
"""

import calendar
import csv
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "reports", "common"))
from formula_db import SERVICE_ACCOUNT_KEY, date_option   # noqa: E402

SHEET_ID = os.environ.get("SCHEDULE_SHEET_ID", "1_gnLoYMXrjyr8eyc6TSQ2-EHqFIEwBYDnlp2JW6fPAs")
SCHEDULE_TAB = "Schedule"
LOG_TAB = "Run log"
TH = dt.timezone(dt.timedelta(hours=7), "Asia/Bangkok")    # Thailand has no daylight saving
CATCH_UP_HOURS = 6          # a run time missed by more than this (server off, say) is skipped
DAILY_TIMEOUT = 3600        # seconds
UPLOAD_TIMEOUT = 1800

# How each report takes its dates: "range" = --start and --end, "asof" = --end only, "none" = no dates.
TASKS = {
    "XRBUYOR1": "range",
    "PGDRCVNT": "range",
    "CUSTDET2": "none",
    "PDISITM1": "range",
    "PBUYORD":  "range",
    "PPDOR2":   "range",
    "XRCRSTK1": "asof",
}

# Schedule tab headings (row 1). Columns are found by heading, so they can be moved.
COL_TASK, COL_ENABLED, COL_DAYS, COL_TIMES = "Task", "Enabled", "Run days", "Run times (TH)"
COL_PERIOD, COL_START, COL_END, COL_BACK = "Data period", "Start date", "End date", "Days back"
COL_SHEETS, COL_NOW = "Upload to Sheets", "Run now"
RESULT_COLS = ["Last run (TH)", "Last status", "Last date range", "Last rows", "Last message"]

DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


# --------------------------------------------------------------------------- parsing the sheet

def as_bool(v):
    return v is True or str(v).strip().upper() in ("TRUE", "YES", "Y", "1")


def as_date(v):
    """A sheet date: serial number (unformatted read), ISO text or dd/mm/yyyy text. Blank -> None."""
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return dt.date(1899, 12, 30) + dt.timedelta(days=int(v))
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"date {s!r} not understood; use dd/mm/yyyy")


def run_days(text):
    """'Every day', 'Mon-Fri', 'Mon,Wed,Fri', 'Mon-Wed,Sat', 'Monthly 1,15' or 'Monthly last' -> test(date)."""
    s = str(text or "").strip().lower()
    if s in ("", "every day", "everyday", "daily"):
        return lambda d: True
    m = re.fullmatch(r"monthly\s+(.+)", s)
    if m:
        days, last = set(), False
        for part in re.split(r"[,\s]+", m.group(1)):
            if part == "last":
                last = True
            elif part.isdigit() and 1 <= int(part) <= 31:
                days.add(int(part))
            elif part:
                raise ValueError(f"run days {text!r}: {part!r} is not a day of the month")
        return lambda d: d.day in days or (last and d.day == calendar.monthrange(d.year, d.month)[1])
    weekdays = set()
    for part in re.split(r"\s*,\s*", s):
        ends = [p.strip()[:3] for p in part.split("-")]
        if not all(e in DAY_NAMES for e in ends) or len(ends) > 2:
            raise ValueError(f"run days {text!r}: use Every day, Mon-Fri, Mon,Wed,Fri or Monthly 1")
        a, b = DAY_NAMES.index(ends[0]), DAY_NAMES.index(ends[-1])
        weekdays.update(range(a, b + 1) if a <= b else list(range(a, 7)) + list(range(0, b + 1)))
    return lambda d: d.weekday() in weekdays


def run_times(v):
    """'06:00, 13:30' (or a sheet time fraction such as 0.25) -> [time, ...]."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        minutes = round(v * 24 * 60) % (24 * 60)
        return [dt.time(minutes // 60, minutes % 60)]
    out = []
    for part in re.split(r"[,;\s]+", str(v or "").strip()):
        if not part:
            continue
        m = re.fullmatch(r"(\d{1,2})[:.](\d{2})", part)
        if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
            raise ValueError(f"run time {part!r}: use 24-hour HH:MM, e.g. 06:00")
        out.append(dt.time(int(m.group(1)), int(m.group(2))))
    if not out:
        raise ValueError("no run time set")
    return out


def period_dates(row, today):
    """(date_from, date_to) for the row's data period. None means 'not used'."""
    period = str(row.get(COL_PERIOD, "")).strip().lower()
    start, end = as_date(row.get(COL_START)), as_date(row.get(COL_END))
    if period == "start date to today":
        if not start:
            raise ValueError("Start date to today needs a Start date")
        return start, today
    if period == "fixed range":
        if not (start and end):
            raise ValueError("Fixed range needs a Start date and an End date")
        return start, end
    if period == "year to date":
        return dt.date(today.year, 1, 1), today
    if period == "month to date":
        return today.replace(day=1), today
    if period == "previous month":
        last = today.replace(day=1) - dt.timedelta(days=1)
        return last.replace(day=1), last
    if period == "last n days":
        try:
            n = int(float(row.get(COL_BACK)))
        except (TypeError, ValueError):
            n = 0
        if n < 1:
            raise ValueError("Last N days needs a number of days in Days back")
        return today - dt.timedelta(days=n - 1), today
    if period == "as of today":
        return None, end or today
    if period in ("no dates", ""):
        return None, None
    raise ValueError(f"unknown data period {row.get(COL_PERIOD)!r}")


def latest_slot(row, now):
    """The most recent scheduled run time at or before `now` (yesterday or today), or None."""
    on_day, times = run_days(row.get(COL_DAYS)), run_times(row.get(COL_TIMES))
    slots = [dt.datetime.combine(day, t, TH)
             for day in (now.date() - dt.timedelta(days=1), now.date()) if on_day(day)
             for t in times]
    slots = [s for s in slots if s <= now]
    return max(slots) if slots else None


def last_run_time(v):
    if v in (None, ""):
        return None
    try:
        return dt.datetime.strptime(str(v).strip(), "%Y-%m-%d %H:%M").replace(tzinfo=TH)
    except ValueError:
        return None


# --------------------------------------------------------------------------- running a task

def task_files(task):
    folder = os.path.join(ROOT, "reports", task)
    daily = os.path.join(folder, f"daily_{task.lower()}.py")
    uploads = sorted(f for f in os.listdir(folder) if f.startswith("upload_") and f.endswith(".py")) \
        if os.path.isdir(folder) else []
    upload = os.path.join(folder, uploads[0]) if uploads else None
    return daily, upload, os.path.join(folder, f"{task}_claude.csv")


def csv_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return max(sum(1 for _ in csv.reader(fh)) - 1, 0)


def tail(text, n=300):
    lines = [ln.strip() for ln in (text or "").strip().splitlines() if ln.strip()]
    return (lines[-1] if lines else "")[-n:]


def run_task(task, d1, d2, to_sheets):
    """Run the daily script, then the Sheets upload. Returns a result dict."""
    kind = TASKS[task]
    daily, upload, csv_path = task_files(task)
    args = [sys.executable, daily]
    if kind == "range":
        args += ["--start", d1.isoformat(), "--end", d2.isoformat()]
    elif kind == "asof" and d2:
        args += ["--end", d2.isoformat()]
    result = {"rows": "", "drive": "", "sheets": "" if to_sheets else "off", "status": "OK", "message": ""}

    print(f"\n=== {task}: {' '.join(os.path.basename(a) if i < 2 else a for i, a in enumerate(args))}", flush=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=DAILY_TIMEOUT, cwd=os.path.dirname(daily), env=env)
    print(p.stdout, p.stderr, sep="", flush=True)
    m = re.findall(r"^upload: (.*)$", p.stdout, flags=re.M)
    result["drive"] = m[-1].strip() if m else ""
    if p.returncode != 0:
        result.update(status="FAILED", message=tail(p.stderr) or tail(p.stdout))
        return result
    result["rows"] = csv_rows(csv_path)
    if result["drive"] and result["drive"] != "ok":
        result.update(status="WARNING", message=f"Drive upload {result['drive']}")

    if to_sheets:
        if not upload:
            result.update(sheets="none", status="WARNING", message="no Sheets upload script for this report")
            return result
        p = subprocess.run([sys.executable, upload], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=UPLOAD_TIMEOUT, cwd=os.path.dirname(upload), env=env)
        print(p.stdout, p.stderr, sep="", flush=True)
        if p.returncode != 0:
            result.update(sheets="failed", status="FAILED", message="Sheets: " + (tail(p.stderr) or tail(p.stdout)))
        else:
            result["sheets"] = "ok"
            if result["status"] == "OK":
                result["message"] = tail(p.stdout)
    return result


# --------------------------------------------------------------------------- sheet access

def retry(fn, attempts=4):
    """Call fn(), retrying network and Google API errors after 10, 30 and 60 seconds."""
    for i, wait in enumerate([10, 30, 60, None][:attempts]):
        try:
            return fn()
        except Exception as exc:          # dropped connections, 429 and 5xx from Google
            if wait is None or i == attempts - 1:
                raise
            print(f"Google Sheets call failed ({type(exc).__name__}: {str(exc)[:120]}), retrying in {wait}s",
                  flush=True)
            time.sleep(wait)


class Sheet:
    """Reads the Schedule tab and writes results back. With rows_json, works offline and writes nothing."""

    def __init__(self, rows_json=None, dry_run=False):
        self.dry_run = dry_run or bool(rows_json)
        if rows_json:
            with open(rows_json, encoding="utf-8") as fh:
                self.values = json.load(fh)
            self.ws = self.log = None
        else:
            import gspread
            gc = gspread.service_account(filename=SERVICE_ACCOUNT_KEY)
            sh = retry(lambda: gc.open_by_key(SHEET_ID))
            self.ws, self.log = retry(lambda: sh.worksheet(SCHEDULE_TAB)), retry(lambda: sh.worksheet(LOG_TAB))
            self.values = retry(lambda: self.ws.get("A1:Z", value_render_option="UNFORMATTED_VALUE",
                                                    date_time_render_option="SERIAL_NUMBER"))
        self.header = [str(h).strip() for h in self.values[0]]
        missing = [c for c in (COL_TASK, COL_ENABLED, COL_DAYS, COL_TIMES, COL_PERIOD, *RESULT_COLS)
                   if c not in self.header]
        if missing:
            raise SystemExit(f"Schedule tab is missing the column(s) {missing}")

    def rows(self):
        """[(sheet_row_number, {heading: value})] for every row with a task."""
        out = []
        for i, r in enumerate(self.values[1:], start=2):
            row = dict(zip(self.header, list(r) + [""] * (len(self.header) - len(r))))
            if str(row.get(COL_TASK, "")).strip():
                out.append((i, row))
        return out

    def _col(self, name):
        n, s = self.header.index(name) + 1, ""
        while n:
            n, r = divmod(n - 1, 26)
            s = chr(65 + r) + s
        return s

    def write_result(self, rownum, values, untick_run_now=False):
        if self.dry_run:
            return
        first, last = self._col(RESULT_COLS[0]), self._col(RESULT_COLS[-1])
        retry(lambda: self.ws.update(range_name=f"{first}{rownum}:{last}{rownum}", values=[values],
                                     value_input_option="RAW"))
        if untick_run_now and COL_NOW in self.header:
            retry(lambda: self.ws.update(range_name=f"{self._col(COL_NOW)}{rownum}", values=[[False]],
                                         value_input_option="RAW"))

    def append_log(self, values):
        if not self.dry_run:
            retry(lambda: self.log.append_row(values, value_input_option="RAW", table_range="A1"))


# --------------------------------------------------------------------------- main

def fmt(d):
    return d.strftime("%d/%m/%Y") if d else ""


def github_run_link():
    if os.environ.get("GITHUB_RUN_ID"):
        return (f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
                f"{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}")
    return "run by hand"


def summary(lines):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")


def main():
    argv = sys.argv[1:]
    dry_run = "--dry-run" in argv
    only = argv[argv.index("--task") + 1].upper() if "--task" in argv else None
    rows_json = argv[argv.index("--rows-json") + 1] if "--rows-json" in argv else None
    now = (dt.datetime.strptime(argv[argv.index("--now") + 1], "%Y-%m-%d %H:%M").replace(tzinfo=TH)
           if "--now" in argv else dt.datetime.now(TH))
    start_override, end_override = date_option("--start"), date_option("--end")

    sheet = Sheet(rows_json, dry_run)
    print(f"Schedule check at {now:%Y-%m-%d %H:%M} (Thailand){'  [dry run]' if sheet.dry_run else ''}")

    plan, problems = [], []
    for rownum, row in sheet.rows():
        task = str(row[COL_TASK]).strip().upper()
        try:
            if task not in TASKS:
                raise ValueError(f"unknown task; known tasks are {', '.join(TASKS)}")
            if only:
                if task != only:
                    continue
                trigger = "manual"
            elif as_bool(row.get(COL_NOW)):
                trigger = "run now"
            elif as_bool(row.get(COL_ENABLED)):
                slot = latest_slot(row, now)
                last = last_run_time(row.get(RESULT_COLS[0]))
                if not slot or (last and last >= slot) or now - slot > dt.timedelta(hours=CATCH_UP_HOURS):
                    continue
                trigger = f"schedule {slot:%a %H:%M}"
            else:
                continue
            d1, d2 = period_dates(row, now.date())
            if only and (start_override or end_override):
                d1, d2 = start_override or d1, end_override or d2
                if TASKS[task] == "range" and not (d1 and d2):
                    raise ValueError("give both --start and --end for this report")
            plan.append((rownum, task, trigger, row, d1, d2))
        except ValueError as exc:
            problems.append((rownum, task, str(exc), row.get(RESULT_COLS[0], "")))

    if only and not any(p[1] == only for p in plan) and not any(p[1] == only for p in problems):
        raise SystemExit(f"task {only} is not on the Schedule tab")

    for rownum, task, msg, last in problems:
        print(f"row {rownum} {task}: SETTING ERROR - {msg}")
        # keep the old "Last run" so fixing the row does not move its next run
        sheet.write_result(rownum, [last, "SETTING ERROR", "", "", msg])
    if not plan:
        print("Nothing due.")
    report = ["| Task | Trigger | Dates | Rows | Drive | Sheets | Status | Message |", "|---|---|---|---|---|---|---|---|"]
    failed = bool(problems)

    for rownum, task, trigger, row, d1, d2 in plan:
        dates = f"{fmt(d1)} - {fmt(d2)}" if d1 else (f"as of {fmt(d2)}" if d2 else "no dates")
        to_sheets = as_bool(row.get(COL_SHEETS))
        print(f"row {rownum} {task}: due ({trigger}), {dates}, Sheets {'on' if to_sheets else 'off'}")
        if sheet.dry_run:
            continue
        started = dt.datetime.now(TH)
        sheet.write_result(rownum, [f"{started:%Y-%m-%d %H:%M}", "RUNNING", dates, "", trigger])
        try:
            res = run_task(task, d1, d2, to_sheets)
        except Exception as exc:          # timeout or a script that could not start
            res = {"rows": "", "drive": "", "sheets": "", "status": "FAILED", "message": f"{type(exc).__name__}: {exc}"[:300]}
        finished = dt.datetime.now(TH)
        failed |= res["status"] == "FAILED"
        sheet.write_result(rownum, [f"{started:%Y-%m-%d %H:%M}", res["status"], dates, res["rows"], res["message"]],
                           untick_run_now=trigger == "run now")
        sheet.append_log([f"{started:%Y-%m-%d %H:%M}", f"{finished:%Y-%m-%d %H:%M}", task, trigger,
                          str(row.get(COL_PERIOD, "")), fmt(d1), fmt(d2), res["rows"], res["drive"],
                          res["sheets"], res["status"], res["message"], github_run_link()])
        report.append(f"| {task} | {trigger} | {dates} | {res['rows']} | {res['drive']} | {res['sheets']} "
                      f"| {res['status']} | {res['message'].replace('|', '/')} |")
        print(f"row {rownum} {task}: {res['status']} {res['rows']} rows  {res['message']}")

    if len(report) > 2:
        summary([f"### Formula reports, {now:%Y-%m-%d %H:%M} Thailand", "", *report])
    if problems:
        summary(["", "**Setting errors on the Schedule tab:**", *[f"- row {r} {t}: {m}" for r, t, m, _ in problems]])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
