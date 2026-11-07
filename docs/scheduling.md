# Phase 3: scheduled runs and tracking

The reports run on the Formula server on a schedule you set in a Google Sheet. GitHub Actions
starts a check every 30 minutes, and each result is written back to the sheet.

```
Google Sheet "Formula Report Schedule"          you set task, run days, run times, data period
        |  read every 30 minutes
        v
GitHub Actions  .github/workflows/report-schedule.yml
        |  runs on the Formula server (self-hosted runner, label "formula")
        v
scheduler/run_schedule.py     works out which tasks are due and their dates
        |
        |  reports/<TASK>/daily_<task>.py --start .. --end ..   query -> CSV -> Google Drive
        |  reports/<TASK>/upload_<task>_claude.py               CSV -> Google Sheets tab
        v
Schedule tab (Last run, status, rows, message)  +  Run log tab  +  GitHub Actions history
```

GitHub's own cloud machines can't reach the SQL Server on the office network, so the job runs
on the server itself through a GitHub "self-hosted runner". The database is still only read
(SELECT only), as before.

## The control sheet

[Formula Report Schedule](https://docs.google.com/spreadsheets/d/1_gnLoYMXrjyr8eyc6TSQ2-EHqFIEwBYDnlp2JW6fPAs/edit)
is shared with the service account `google-sheet-connect@yt-analysis-project-402700.iam.gserviceaccount.com`,
which the scripts already use for the report sheets.

| Tab | What it is |
|---|---|
| Schedule | One row per task. You edit columns A to J; the server fills in K to O after each run. |
| Run log | One row per run: start and end time, task, trigger, dates, rows, Drive, Sheets, status, message, link to the GitHub run. |
| Help | What to type in each column. |

Columns you set:

| Column | Example | Notes |
|---|---|---|
| Task | `PPDOR2` | Must match a folder in `reports/`. |
| Enabled | ticked | Untick to pause the task. |
| Run days | `Mon-Sat`, `Every day`, `Mon,Wed,Fri`, `Monthly 1`, `Monthly 1,15`, `Monthly last` | |
| Run times (TH) | `06:00` or `06:00, 13:00` | Thailand time, 24-hour. |
| Data period | see below | |
| Start date, End date, Days back | `01/01/2025`, `31/10/2026`, `30` | Only the ones the data period needs. |
| Upload to Sheets | ticked | Also load the CSV into the report's Google Sheet tab. |
| Run now | ticked | Runs at the next check (within 30 minutes), then unticks itself. Works even when the task is paused. |

| Data period | Dates used |
|---|---|
| Start date to today | Start date up to the day of the run |
| Fixed range | Start date to End date |
| Year to date | 1 January this year up to the day of the run |
| Month to date | 1st of this month up to the day of the run |
| Previous month | The whole of last month (pair it with `Monthly 1`) |
| Last N days | The last N days, N in Days back |
| As of today | Stock as of the day of the run, or as of End date if one is set (XRCRSTK1) |
| No dates | No date filter (CUSTDET2) |

When a task is due: its latest run time, on one of its run days, has passed since its last run.
A run time missed by more than 6 hours, for example because the server was off, is skipped
until the next one. GitHub can start scheduled jobs 5 to 30 minutes late at busy times, so a
06:00 task usually starts between 06:00 and 06:45.

A row with a mistake (an unknown task, a time like `6am`, a Fixed range without an End date)
shows `SETTING ERROR` in Last status with the reason, and that check turns red in GitHub.

## One-time setup

### 1. Make the repository private

GitHub advises against self-hosted runners on public repositories, because anyone could open a
pull request that tries to run code on the server. On GitHub, open the repository, go to
**Settings → General → Danger Zone → Change visibility**, and choose **Private**. Private
repositories can use self-hosted runners at no cost, and GitHub doesn't pause their schedules
for inactivity.

### 2. Prepare the Formula server

Sign in to the server as the Windows account that runs the reports today (the one that can
connect with `sqlcmd -S server -E`).

1. Check that these files are still in place. They are not in git:
   - `D:\Em_Project\config\yt-analysis-project-402700-6c9fee962152.json`
   - `D:\Em_Project\tools\rclone\rclone.exe`, with its `gdrive` remote set up
2. Install the Python packages for that account:
   ```powershell
   python -m pip install pyodbc pandas gspread gspread_dataframe
   ```
3. Check where rclone keeps its settings:
   ```powershell
   D:\Em_Project\tools\rclone\rclone.exe config file
   ```
   If it shows a file inside that account's profile (`C:\Users\<account>\AppData\Roaming\rclone\rclone.conf`),
   nothing more is needed. If it's somewhere else, add `RCLONE_CONFIG: <that path>` under `env:`
   in `.github/workflows/report-schedule.yml`.
4. If Windows Task Scheduler already runs any `daily_*.py` script, disable those tasks so the
   reports don't run twice.

### 3. Install the GitHub runner on the server

1. On GitHub, open the repository, then **Settings → Actions → Runners → New self-hosted runner**,
   and choose **Windows** / **x64**.
2. In PowerShell on the server, run the commands GitHub shows: create `C:\actions-runner`,
   download and extract the runner, then run `config.cmd` with the URL and token from that page.
   The token expires after an hour.
3. Answer the `config.cmd` questions:
   - Runner group: press Enter (Default)
   - Runner name: `formula-server`
   - Additional labels: `formula`
   - Work folder: press Enter (`_work`)
   - Run as service: `Y`
   - Service account: the same Windows account as in step 2, for example `SERVER\Administrator`,
     and its password. Don't keep the default `NT AUTHORITY\NETWORK SERVICE`: that account
     can't sign in to SQL Server with Windows authentication and can't see the rclone settings.
4. On GitHub, **Settings → Actions → Runners** should now list `formula-server` as **Idle**, with
   the labels `self-hosted`, `Windows`, `X64` and `formula`.

### 4. First runs

1. On GitHub, open **Actions → Formula report schedule → Run workflow**. Tick **Only show what
   would run**, then click **Run workflow**. The log should list the Schedule rows that are due.
2. Run one real task: choose **Task** `CUSTDET2` (no dates), leave the box unticked, and click
   **Run workflow**. Check that the Schedule row shows `OK` with a row count, that Run log has a
   new row, and that the CSV on Drive and the Sheets tab were updated.
3. From then on the schedule runs by itself.

## Tracking

- **Schedule tab, columns K to O:** last run time, status (`RUNNING`, `OK`, `WARNING`,
  `FAILED`, `SETTING ERROR`), date range, row count and message for each task.
- **Run log tab:** every run, newest at the bottom, with a link to its GitHub run.
- **GitHub Actions tab:** every 30-minute check, with the full output of the report scripts.
  Checks with nothing to do finish in a few seconds. A red cross means a report failed or a row
  has a setting error. GitHub emails you about failed scheduled runs (settings under
  **GitHub → Settings → Notifications → Actions**).

## Running a report by hand

From GitHub: **Actions → Formula report schedule → Run workflow**, then pick the task and,
optionally, the start and end dates (YYYY-MM-DD). Without dates it uses the task's data period
from the sheet. Without a task it checks the schedule as usual.

On the server itself:

```powershell
cd D:\path\to\formula-erp-reports
python scheduler\run_schedule.py --dry-run                 # what is due now
python scheduler\run_schedule.py --task PPDOR2             # run one task now, sheet's data period
python scheduler\run_schedule.py --task PPDOR2 --start 2025-01-01 --end 2025-06-30
python reports\PPDOR2\daily_ppdor2.py --start 2025-01-01 --end 2025-06-30 --no-upload
```

## Changing the code

Edit and push from your own computer as before (`git add .`, `git commit -m "..."`, `git push`).
The next scheduled check uses the new code: the runner fetches it from GitHub every time, so
you no longer need to copy scripts to the server by hand. Only the key and rclone stay in
`D:\Em_Project` on the server.

## Settings in the code

| Setting | Where | Default |
|---|---|---|
| Control sheet ID | `SCHEDULE_SHEET_ID` in `scheduler/run_schedule.py` (or env var) | the sheet above |
| Check interval | `cron` in `.github/workflows/report-schedule.yml` | every 30 minutes |
| Missed-run window | `CATCH_UP_HOURS` in `scheduler/run_schedule.py` | 6 hours |
| Folder with key and rclone | `EM_HOME` in the workflow (or env var) | `D:\Em_Project` |
| rclone and key paths | `RCLONE_EXE`, `GOOGLE_SA_KEY` env vars | under `EM_HOME` |
| Tasks and how they take dates | `TASKS` in `scheduler/run_schedule.py` | |

To add a new report to the schedule: create it in `reports/<TASK>/` as in `requirement_sample.txt`,
give its daily script the `--start` / `--end` options like the others, add it to `TASKS`, add a
row in the sheet, and add it to the task list in the workflow's `options`.
