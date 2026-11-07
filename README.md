# Formula ERP reports

Rebuilds Formula ERP print reports straight from the Formula SQL Server database, then publishes
each one as a CSV on Google Drive and as a tab in Google Sheets. Each run gives you a new file
that replaces the old one.

The company is retiring Formula. These scripts extract its historical data for internal reporting,
and they only read from the database.

## How the pipeline works

```
Formula SQL Server (FORMULA, Windows auth, SELECT only)
        |  <task>.sql            query rebuilt from the sample report
        v
daily_<task>.py                  runs the query, writes <TASK>_claude.csv (replaced every run)
        |  rclone copyto
        v
gdrive:Formula Reports/<TASK>/<TASK>_claude.csv
        |
upload_<task>_claude.py          renames headings to Thai (formular_mapping.xlsx),
        v                        keeps code columns as text
Google Sheet <TASK>, tab <TASK>_Claude
```

## Project phases

| Phase | What | Status |
|---|---|---|
| 1 | Find the ERP database and map its tables (`erp_discovery.md`, `erp_tables.md`) | Done |
| 2 | Rebuild each report from SQL, check it against the sample, publish to Drive and Sheets (`reports/`) | Done |
| 3 | Run the reports on a schedule set in a Google Sheet, with tracking, through GitHub Actions on the server (`scheduler/`, [docs/scheduling.md](docs/scheduling.md)) | Code ready; runner to be installed on the server |

## Folder layout

```
D:\Em_Project
├── requirement_sample.txt     the 5-step process and strict rules for each new report
├── requirement.txt            original database discovery brief
├── erp_discovery.md           how the ERP and database were found
├── erp_tables.md              table list and module map for the FORMULA database
├── export_archive.py          one-off raw table export (output in archive/, not in git)
├── requirements.txt           Python packages (pip install -r requirements.txt)
├── .github\workflows\report-schedule.yml   GitHub Actions job, every 30 minutes on the server
├── scheduler\run_schedule.py  reads the schedule sheet, runs what is due, writes results back
├── docs\scheduling.md         Phase 3 setup and how to use the schedule sheet
├── Sample report\             reports saved from the Formula client (the targets to match)
│   ├── <TASK>.CSV
│   ├── Readme.txt             filters used when each sample was printed
│   └── formular_mapping.xlsx  English column -> Thai heading for each report
└── reports\
    ├── common\formula_db.py   connection string, SQL safety check, Thai text decoding
    └── <TASK>\
        ├── <task>.sql
        ├── daily_<task>.py
        ├── upload_<task>_claude.py
        ├── <TASK>_claude.csv
        └── analysis\          compare.py and its results against the sample
```

Left out of git (see `.gitignore`): every CSV (the sample reports and the generated
`_claude.csv` files hold company data), `config\` (Google service-account key), `tools\`
(rclone.exe) and `archive\` (raw exports). To run the compare scripts, put the sample CSVs back
into `Sample report\`.

## Reports

| Report | What it is | Date range | Drive and Sheets |
|---|---|---|---|
| XRBUYOR1 | Purchase orders and receipts | 01/01/2025 – today | Uploaded |
| PGDRCVNT | Goods received, non-domestic | per sample | Uploaded (tab needs a re-run) |
| CUSTDET2 | Customer details | – | Uploaded |
| PDISITM1 | Stock movement by item | 01/01/2026 – 31/10/2026 | Uploaded |
| PBUYORD | Purchase orders with deliveries | 01/01/2025 – today | Uploaded |
| PPDOR2 | Outstanding goods to receive, by product | 01/01/2025 – today | Uploaded |
| XRCRSTK1 | Stock report | up to date | Paused, local only |
| PSALEORD | Sales orders | – | Investigation only, no daily script |

## Running a report

Requirements: Windows with ODBC Driver 13 for SQL Server, Python 3.9+, and
`pip install pyodbc pandas gspread gspread_dataframe`. rclone goes in `tools\rclone\rclone.exe`,
with a remote called `gdrive`. The service-account key goes in `config\`, and each spreadsheet
must be shared with the key's `client_email`.

```powershell
cd D:\Em_Project\reports\PPDOR2
python daily_ppdor2.py               # query, write CSV, upload to Drive
python daily_ppdor2.py --no-upload   # local CSV only
python daily_ppdor2.py --start 2025-01-01 --end 2025-06-30   # another date range
python upload_ppdor2_claude.py       # load the CSV into the PPDOR2_Claude tab
python analysis\compare.py           # check against Sample report\PPDOR2.CSV
```

Dated reports take `--start` and `--end` (YYYY-MM-DD); XRCRSTK1 takes `--end` as its as-of date.
Without them, each script uses the dates in its settings. rclone and the key are found under
`D:\Em_Project` unless the `EM_HOME` environment variable points somewhere else.

## Scheduled runs (Phase 3)

The run days, times and data period of each report are set in the
[Formula Report Schedule](https://docs.google.com/spreadsheets/d/1_gnLoYMXrjyr8eyc6TSQ2-EHqFIEwBYDnlp2JW6fPAs/edit)
Google Sheet. GitHub Actions checks it every 30 minutes on the Formula server, runs what is due,
and writes the status, row count and a log entry back to the sheet. Setup and use:
[docs/scheduling.md](docs/scheduling.md).

## Adding a new report

Follow `requirement_sample.txt`:

1. Work out the SQL from the sample report and `Sample report\Readme.txt`. Ask about anything unclear.
2. Create `<task>.sql` and `daily_<task>.py` in `reports\<TASK>\`.
3. Compare with the sample over its date range: documents, lines and amounts, with each difference explained.
4. Run and upload to `gdrive:Formula Reports/<TASK>/`, then confirm the Drive file matches.
5. Upload to Google Sheets with Thai headings, keeping code columns as text.

Strict rules: read-only on the database (SELECT only), no service changes, and nothing written
outside `D:\Em_Project`.

## Data notes

- Formula stores Thai in CHAR columns. The scripts fetch it as latin-1 and decode it as cp874.
- Queries run under READ UNCOMMITTED so they don't lock the live ERP.
- The sample CSVs are cp874 and contain bare `"` characters in names. The compare scripts parse
  them with a regex rather than the csv module.
