FORMULA ERP REPORTS - HOW TO PUT THIS PROJECT ON GITHUB
=======================================================

This is a guide for creating the GitHub repository "formula-erp-reports" on your own computer.
For how the project works, see README.md. GitHub shows that file on the repository's front page.


1. WHAT IS IN THE PROJECT
-------------------------
The project rebuilds Formula ERP print reports from the FORMULA SQL Server database, which only
works on the server. Each report then goes to Google Drive as a CSV and to Google Sheets as a
tab called <TASK>_Claude.

  D:\Em_Project
    README.md                 project overview, shown on GitHub
    readme.txt                this guide
    .gitignore                list of files that git must never upload
    requirement_sample.txt    the 5-step process and strict rules for each new report
    requirement.txt           original database discovery brief
    erp_discovery.md          how the ERP and database were found
    erp_tables.md             FORMULA table guide
    export_archive.py         one-off raw table export
    psaleord.sql
    Sample report\
      Readme.txt              filters used when each sample was printed
      formular_mapping.xlsx   English column -> Thai heading
      *.CSV                   sample reports (NOT uploaded: company data)
    reports\
      common\formula_db.py    shared connection settings (Windows login, no password)
      <TASK>\<task>.sql       the query
      <TASK>\daily_<task>.py  runs the query, writes <TASK>_claude.csv, uploads it to Drive
      <TASK>\upload_<task>_claude.py   loads the CSV into Google Sheets with Thai headings
      <TASK>\analysis\        compare scripts and notes against the sample
    config\                   Google service-account key  (NEVER upload)
    tools\                    rclone.exe, portable Git/gh downloads (not uploaded)
    archive\                  raw database exports (not uploaded)

  Reports: XRBUYOR1, PGDRCVNT, CUSTDET2, PDISITM1, PBUYORD, PPDOR2 (live),
           XRCRSTK1 (paused), PSALEORD (investigation only).


2. WHAT GOES TO GITHUB (CODE ONLY)
----------------------------------
.gitignore leaves these out, so git won't upload them even if they're in the folder:
  - every .csv / .CSV file (sample reports and generated _claude.csv files)
  - config\   the Google service-account key. If this is ever uploaded, delete the key in
              Google Cloud Console straight away and make a new one.
  - tools\    rclone.exe (58 MB), PortableGit, gh
  - archive\  raw exports
  - __pycache__\ and *.pyc

What's left is 47 files, about 290 KB: the .sql, .py and .md files, requirement*.txt,
README.md, readme.txt, .gitignore, Sample report\Readme.txt and formular_mapping.xlsx.

PLEASE CHECK BEFORE MAKING THE REPOSITORY PUBLIC. These code files still contain company details:
  - erp_tables.md                       company names and tax IDs (A K & J, V & J)
  - reports\XRBUYOR1\analysis\differences.md   purchase totals per year, PO numbers
  - reports\PSALEORD\differences.md     sales totals, order numbers, customer codes
  - reports\PSALEORD\formula_report_definition.md and erp_discovery.md   server folders and
                                        SQL Server version
  - upload_*_claude.py                  Google spreadsheet IDs (the sheets only open for accounts
                                        they're shared with)
  - some .sql / .py comments            document numbers and amounts from the comparisons
To keep any of these private, either make the repository Private, or add their paths to
.gitignore before the first commit.


3. COPY THE PROJECT TO YOUR COMPUTER
------------------------------------
On the server, copy the project to a USB drive or shared folder, leaving out the secret key and
the data. Change E:\formula-erp-reports to wherever you want it:

  robocopy D:\Em_Project E:\formula-erp-reports /E /XD config tools archive __pycache__ /XF *.csv *.pyc

Make sure .gitignore was copied too (it is a hidden-looking file that starts with a dot).


4. ON YOUR COMPUTER: ONE-TIME SETUP
-----------------------------------
a) Install Git for Windows:  https://git-scm.com/download/win  (the default options are fine)
b) Open PowerShell (or Git Bash) and set your name and email once:

     git config --global user.name  "emkrit.akj"
     git config --global user.email "emkrit.akj@gmail.com"

c) On https://github.com, sign in, click "+" (top right) > "New repository":
     Repository name: formula-erp-reports
     Visibility:      Public or Private (see section 2)
     Do NOT tick "Add a README", ".gitignore" or "license" (the project already has them)
   Click "Create repository".


5. CREATE THE LOCAL REPOSITORY AND PUSH
---------------------------------------
  cd E:\formula-erp-reports
  git init -b main
  git add .
  git status

Check the "Changes to be committed" list:
  - It should show about 47 files.
  - It must have NO .csv file and nothing under config\, tools\ or archive\.
  - If something is wrong, run  git rm --cached <file> , fix .gitignore, then  git add .  again.

  git commit -m "Formula ERP report pipeline"
  git remote add origin https://github.com/<your-github-username>/formula-erp-reports.git
  git push -u origin main

The first push opens a browser window to sign in to GitHub. Refresh the repository page
afterwards: README.md is shown at the bottom.


6. UPDATING GITHUB LATER
------------------------
After changing scripts on the server:
  1. Run the robocopy command from section 3 again (it only copies changed files).
  2. On your computer:
       cd E:\formula-erp-reports
       git status                      check what changed (still no CSVs)
       git add .
       git commit -m "Short description of the change, e.g. Add PPDDT2 report"
       git push

Adding a new report: follow requirement_sample.txt (steps 1-5), then copy and push as above.


7. RUNNING THE REPORTS (SERVER ONLY)
------------------------------------
The scripts need the FORMULA database, so they only run on the server, not on your computer.
They also need:
  - Python 3.9+ and:  pip install pyodbc pandas gspread gspread_dataframe
  - ODBC Driver 13 for SQL Server
  - tools\rclone\rclone.exe with a remote called "gdrive"
  - config\<service-account key>.json, with each Google Sheet shared to the key's client_email

  cd D:\Em_Project\reports\PPDOR2
  python daily_ppdor2.py               query, write PPDOR2_claude.csv, upload to Drive
  python daily_ppdor2.py --no-upload   local CSV only
  python upload_ppdor2_claude.py       load the CSV into the PPDOR2_Claude tab
  python analysis\compare.py           check against Sample report\PPDOR2.CSV

If you cloned the repository somewhere else, the CSV and key paths inside the scripts point to
D:\Em_Project. Change them, or keep the project at D:\Em_Project.

Rules (from requirement_sample.txt): SELECT only on the database, no service changes, nothing
written outside D:\Em_Project.


8. HOUSEKEEPING
---------------
D:\Em_Project\tools\_download holds the PortableGit and GitHub CLI downloads (about 75 MB). You
don't need them if you use Git on your own computer, so you can delete that folder. It's never
uploaded either way.
