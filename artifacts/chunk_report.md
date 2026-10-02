# Chunk report

chunks: 5280
over_limit: 0
unsplittable: 0

## Per document

| doc_id | chunks | min | median | max |
|---|---|---|---|---|
| amfi_cas | 13 | 7 | 181 | 200 |
| sbimf_elss_campaign | 11 | 23 | 37 | 138 |
| sbimf_factsheet_2026_01 | 1037 | 15 | 57 | 250 |
| sbimf_factsheet_2026_06 | 439 | 15 | 58 | 245 |
| sbimf_factsheet_bluechip_2025_08 | 51 | 21 | 55 | 169 |
| sbimf_factsheet_lte_2024_07 | 49 | 17 | 47 | 237 |
| sbimf_kim_flexicap | 302 | 20 | 56.5 | 244 |
| sbimf_sid_bluechip | 1314 | 19 | 70.0 | 248 |
| sbimf_sid_lte | 650 | 16 | 102.0 | 248 |
| sbimf_sid_smallcap | 1212 | 11 | 82.0 | 248 |
| sbimf_tax_reckoner_fy2026_27 | 60 | 8 | 42.5 | 239 |
| sbimf_ter_notice_2025_05_30 | 7 | 41 | 124 | 203 |
| sbimf_ways_to_invest | 36 | 13 | 82.0 | 229 |
| sebi_exit_load | 8 | 9 | 76.5 | 181 |
| sebi_mf_faq_2024_09 | 91 | 18 | 132 | 226 |

## Unsplittable

None.

## Parse flags

None.

## Chunking rationale

Factsheets are grouped by scheme section, and fee rows (TER, exit load, SIP, benchmark, riskometer, lock-in) stay one chunk per row so a label is not separated from its value. SID, KIM, and the tax reckoner split on headings, then window prose at 900 characters with 120 characters of overlap, snapping the cut to a sentence boundary in the final 15% of the window. Guides and regulator pages keep a heading together with the list items that follow it. Table rows are never split mid-row. Every chunk is measured with the MiniLM tokenizer and re-split, or withheld, if it would exceed 250 tokens. Multi-scheme factsheets keep only the four in-scope schemes, and each chunk carries that scheme rather than the document-level label.

## Review verdict

Passed on 2026-10-01 after reading `artifacts/chunks.txt`.

- Expense-ratio: `sbimf_factsheet_2026_06__bluechip__motherson-sumi-wiring-0-37-0-37__001` is labelled SBI Bluechip Fund and keeps `Expense ratio (Regular Plan): 1.50%`, `Expense ratio (Direct Plan): 0.86%`, and `TER | 1.50 | 0.86` in one chunk. A neighbouring portfolio name still shares the source line; the label and both values stay together.
- ELSS lock-in: `sbimf_elss_campaign__long-term-equity__tax__000` is labelled SBI Long Term Equity Fund and states the 3-year lock-in. The SID states the same statutory 3-year period.
- Statements: `sbimf_ways_to_invest__all-schemes__get-started-with-these-simple-steps-to-begin-inv__000` keeps Step 1 through Step 4 in order, and the statement-of-account chunk keeps the Get Statements path (Account Statement, Capital Gains Statement, Smart Statement).
- Scheme labels on those chunks match the scheme in the text (Bluechip, Long Term Equity, Flexicap, Small Cap).

Median token length is below 120 for several long SIDs. That is over-fragmentation to revisit in Phase 8, not a token-cap failure. `over_limit` is 0 and `unsplittable` is empty.
