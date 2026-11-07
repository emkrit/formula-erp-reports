# PSALEORD Sep 2026 — sample vs database

Sample: `Sample report\PSALEORD.CSV`, saved 2026-09-28 15:02. Database run: 2026-10-02 (FORMULA, read-only).
Filters: SO book 0001, CORP.FCCODE 0001 (A K & J), branch 00000, 01/09/2026–30/09/2026, no other filters.
Cancelled orders (FCSTAT = 'C') are listed but left out of the totals, as in the report.

## Totals

| | Sample | Database | Difference |
|---|---:|---:|---:|
| Orders | 217 (1 cancelled) | 232 (3 cancelled) | +15 |
| Order lines | 671 | 716 | +45 (new orders) |
| Amount before discount | 17,663,486.95 | 18,532,365.01 | +868,878.06 |
| Amount before VAT | 17,650,247.73 | 18,519,125.79 | +868,878.06 |
| VAT | 1,225,820.39 | 1,286,105.51 | +60,285.12 |
| Total | 18,876,068.12 | 19,805,231.30 | +929,163.18 |

All 217 sample orders match on amount, discount, VAT and total. All 671 sample lines match on price, quantity, unit and line amount.

## Differences (all confirmed by database timestamps to be after the export)

1. **15 new orders** (25/09 ×2, 28/09 ×1, 29/09 ×7, 30/09 ×8), 2 of them cancelled (69090218, 69090225). The 13 that count add up to exactly +868,878.06.
2. **14 orders changed status from `1` to `P`** after deliveries: 69090003, 040, 049, 060, 110, 114, 115, 120, 136, 137, 197, 198, 207, 211.
3. **3 orders changed customer** (same amounts): 69090203 sอ.236→อ.340, 69090196 ร.115→ก.089, 69090210 sค.112→บป.029.
4. **16 lines had their product code changed** (same price and quantity). Mostly placeholder codes 2240/2210/2130 replaced with real products: 69090063, 064, 116, 117, 143 ×2, 159 ×4, 194 ×2, 195 ×2, 210, 217.
5. **41 extra delivery-note/invoice rows.** These are documents dated 29/09–03/10, or older DO/DO02 documents linked to the orders on 29–30/09. Every delivery-note row in the sample is in the database.

## Not mapped yet
`depcode` / `depamt` (deposit receipts, e.g. R6908018, on 12 orders). They don't affect the totals.

## Files
- `psaleord.sql`: the query (Q1 headers, Q2 lines, Q3 delivery notes, Q4 totals)
- `db_q*.csv`: database results
- `sample_PSALEORD_cleaned.csv`: the sample re-parsed. Formula leaves `"` inch marks unescaped, so Excel misreads about 30 rows of the original.
- `sample_no_to_docno.csv`: report row number → order number (FCCODE)
