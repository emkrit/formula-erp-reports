# ERP Discovery Report

_Generated: 2026-10-01 — read-only discovery, no data modified._

## 1. ERP Identification

| Item | Value |
|------|-------|
| **ERP name** | **Formula** (Thai ERP / accounting suite) |
| **Client install path** | `C:\FORMULA.SQL\` (one subfolder per module) |
| **Secondary copy** | `D:\Formula`, `D:\FORMULA.SQL` (present, not inspected) |
| **Deployment** | On-premise LAN, no cloud |

The Thai master tables (`JANGWAT` = province, `AMPHUR` = district, `TAMBON` = sub-district, `ZIPCODE`) confirm a Thai-localized Formula installation.

### Installed modules (from Start Menu shortcuts)

| Shortcut / EXE | Module |
|----------------|--------|
| `FMGLWIN` | General Ledger |
| `FMAP` | Accounts Payable |
| `FMAR` | Accounts Receivable |
| `FMSO` | Sales Order |
| `FMPO` | Purchase Order |
| `FMIC` | Inventory Control |
| `FMFA` | Fixed Assets |
| `FMPE` / `FMPF` | Personnel / Payroll |
| `FMCQ` | Cheque |
| `FMAC` | (accounting utility) |
| `F3FAS`, `F3MIS`, `F3SOC` | F3-generation modules (MIS / SOC / FAS) |
| `FORMULA.EXE` (`C:\FORMULA.SQL\ALL\`) | Main launcher |

## 2. Database Engine & Connection

| Item | Value |
|------|-------|
| **Engine** | Microsoft SQL Server 2017 (RTM) 14.0.1000.169, Standard Edition (64-bit) |
| **Host** | `server` — **this computer** (local instance), on Windows Server 2019 Standard |
| **Database** | `FORMULA` (also present: `cloudreportdb` — ignored per instruction) |
| **System DBs** | master, tempdb, model, msdb |
| **Authentication** | Windows Authentication (Integrated) — no SQL password in use |
| **Connection string (ODBC)** | `Driver={ODBC Driver 13};Server=server;Database=FORMULA;Trusted_Connection=yes;` |

### How to connect (read-only)
```
sqlcmd -S server -E -d FORMULA -Q "SELECT ..."
```
`-E` = Windows auth (current user). Connection tested OK with `SELECT @@VERSION`.

## 3. Client Tools / Drivers on this PC

| Tool | Location / Status |
|------|-------------------|
| **sqlcmd** | `C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\130\Tools\Binn\SQLCMD.EXE` ✔ |
| **ODBC Driver** | SQL Server Client SDK 13.0 (ODBC) installed ✔ |

(Full ODBC DSN enumeration not performed — connection via `-E` to the local instance needs no DSN.)

## 4. Data Overview — FORMULA database

**~145 non-empty tables**, all in schema `dbo`. Row counts from catalog views (`sys.partitions`) — no table scans. Largest tables:

| Table | Rows | Likely content |
|-------|------|----------------|
| `NOTECUT` | 214,971 | Document notes / cut records |
| `KEEPTRAC` | 205,122 | Audit / change tracking |
| `GL` | 157,095 | **General Ledger transactions** |
| `REFPROD` | 154,449 | Product references |
| `ORDERI` | 133,562 | **Order line items** (sales/purchase) |
| `DORDERI` | 74,061 | Draft/delivery order items |
| `GLREF` / `GLREFDT` | 65,990 / 64,246 | GL reference docs + details |
| `GLHEAD` | 57,062 | **GL document headers** |
| `MGL` | 45,836 | GL master / monthly GL |
| `TRANSDT1` | 38,867 | Transaction details |
| `ORDERH` / `ORDERHDT` | 33,442 / 33,162 | **Order headers** + details |
| `REFPAY` | 32,712 | Payment references |
| `PAYMENT` | 20,568 | **Payments** |
| `BILPAY` | 17,669 | Bill payments |
| `PROD` | 8,807 | **Product master** |
| `ASSETDPR` / `ASSET` | 7,237 / 559 | **Fixed asset depreciation / assets** |
| `ACCHART` | 841 | **Chart of accounts** |

### Inferred module → table mapping
_(inferred from table names + Formula conventions; verify before relying on it)_

| Module | Key tables |
|--------|-----------|
| **FMGL** – General Ledger | `GL`, `GLHEAD`, `GLREF`, `GLREFDT`, `GLREFRD`, `MGL`, `AGL`, `ACCHART`, `ACCBOOK`, `BOOK`, `ACLINK`, `ACEXP` |
| **FMAR** – Accounts Receivable | `ORDERH`, `ORDERI`, `ORDERHDT`, `REFPAY`, `PAYMENT`, `BILPAY`, `PAYINH`, `PAYINI` |
| **FMAP** – Accounts Payable | `PAYMENT`, `PAYMNTTR`, `BILPAY`, `REFPAY` (shared w/ AR), `DORDERH`, `DORDERI` |
| **FMSO** – Sales Order | `ORDERH`, `ORDERI`, `FORMH`, `FORMI`, `FORMH2`, `FORMI2` |
| **FMPO** – Purchase Order | `ORDERH`/`ORDERI` (type-flagged), `PRCVH`, `PRCVI` |
| **FMIC** – Inventory | `PROD`, `PRODX*`, `REFPROD`, `STOCK`, `COOR`, `COORBAL`, `COORFIFO`, `PRICE`, `WHOUSE`, `UM`, `PRODTYPE`, `RUBBIN` |
| **FMFA** – Fixed Assets | `ASSET`, `ASSETDPR`, `ASSETX02`, `MCALDEPR`, `DEPREF`, `ASGRP` |
| **Masters / shared** | `CORP`, `BRANCH`, `BANK`, `BANKACCT`, `CURRENCY`, `COUNTRY`, `JANGWAT`, `AMPHUR`, `TAMBON`, `ZIPCODE`, `EMPL`, `DEPT`, `JOB` |
| **System / audit** | `KEEPTRAC`, `NOTECUT`, `DATALUPD`, `LOGINLOG`, `LOGILOCK`, `SYSINDEX`, `TASKQUEU` |

## 5. Next Safe Step

The connection is proven and the data is mapped. **Stopping here before any bulk extraction, as instructed.**

Recommended next steps (all read-only SELECT), to confirm with you first:
1. **Inspect column layouts** of the specific tables your report needs (e.g. `GLHEAD`/`GL`, `ORDERH`/`ORDERI`, `PROD`) via `INFORMATION_SCHEMA.COLUMNS` — no data pulled, just structure.
2. **Pull sample rows** (`SELECT TOP 10 ...`) from those tables so we agree on which fields matter and what the codes mean.
3. **Define the exact report scope** (date range, modules, fields) — then run targeted SELECTs and export to CSV/Excel in `D:\Em_Project\`.

> Tell me which report(s) you need and for which period, and I'll start with structure + samples for just those tables.
