# Parse report

| doc_id | tier | ingest | blocks | chars | pages | parser | flag | error |
|---|---|---|---|---|---|---|---|---|
| sbimf_ter_page | 1 | no | — | — | — | — | NOT_INGESTED | — |
| sbimf_disclosure_hub | 2 | no | — | — | — | — | NOT_INGESTED | — |
| sbimf_factsheets_hub | 2 | no | — | — | — | — | NOT_INGESTED | — |
| cams_capital_gain_statement | 3 | no | — | — | — | — | NOT_INGESTED | — |
| cams_single_folio_statement | 3 | no | — | — | — | — | NOT_INGESTED | — |
| mfcentral | 4 | no | — | — | — | — | NOT_INGESTED | — |
| sebi_riskometer_mirror | 5 | no | — | — | — | — | NOT_INGESTED | — |
| amfi_categorization | 4 | no | — | — | — | — | NOT_INGESTED | — |
| amfi_scheme_types | 4 | no | — | — | — | — | NOT_INGESTED | — |
| sbimf_factsheet_2026_06 | 1 | yes | 6729 | 531996 | 104 | pdf_table | - | — |
| sbimf_factsheet_2026_01 | 1 | yes | 5917 | 606468 | 108 | pdf_table | - | — |
| sbimf_sid_bluechip | 1 | yes | 1394 | 351487 | 133 | pdf_text | - | — |
| sbimf_sid_lte | 1 | yes | 598 | 202708 | 73 | pdf_text | - | — |
| sbimf_factsheet_bluechip_2025_08 | 2 | yes | 79 | 6207 | 1 | pdf_table | - | — |
| sbimf_factsheet_lte_2024_07 | 2 | yes | 83 | 5895 | 1 | pdf_table | - | — |
| sbimf_kim_flexicap | 2 | yes | 401 | 67332 | 30 | pdf_text | - | — |
| sbimf_sid_smallcap | 2 | yes | 1217 | 363773 | 137 | pdf_text | - | — |
| sbimf_elss_campaign | 2 | yes | 21 | 1741 | 1 | html_sections | - | — |
| sbimf_ter_notice_2025_05_30 | 2 | yes | 5 | 1727 | 1 | pdf_text | - | — |
| sbimf_ways_to_invest | 2 | yes | 94 | 14332 | 1 | html_sections | - | — |
| sbimf_tax_reckoner_fy2026_27 | 2 | yes | 85 | 12538 | 5 | pdf_text | - | — |
| amfi_cas | 3 | yes | 72 | 7221 | 1 | html_sections | - | — |
| sebi_mf_faq_2024_09 | 3 | yes | 115 | 44932 | 17 | pdf_text | - | — |
| sebi_exit_load | 3 | yes | 24 | 2503 | 1 | html_sections | - | — |

## Mandatory-topic coverage

| topic | documents | count | gate |
|---|---|---|---|
| expense_ratio | sbimf_factsheet_2026_01, sbimf_factsheet_2026_06, sbimf_kim_flexicap, sbimf_sid_bluechip, sbimf_sid_lte, sbimf_sid_smallcap, sbimf_ter_notice_2025_05_30, sebi_mf_faq_2024_09 | 8 | pass |
| exit_load | sbimf_factsheet_2026_01, sbimf_factsheet_2026_06, sbimf_factsheet_bluechip_2025_08, sbimf_factsheet_lte_2024_07, sbimf_kim_flexicap, sbimf_sid_bluechip, sbimf_sid_lte, sbimf_sid_smallcap, sebi_exit_load, sebi_mf_faq_2024_09 | 10 | pass |
| minimum_sip | amfi_cas, sbimf_factsheet_2026_01, sbimf_factsheet_2026_06, sbimf_factsheet_bluechip_2025_08, sbimf_factsheet_lte_2024_07, sbimf_kim_flexicap, sbimf_sid_bluechip, sbimf_sid_lte, sbimf_sid_smallcap, sbimf_ways_to_invest, sebi_mf_faq_2024_09 | 11 | pass |
| elss_lockin | sbimf_elss_campaign, sbimf_factsheet_2026_01, sbimf_factsheet_2026_06, sbimf_factsheet_lte_2024_07, sbimf_kim_flexicap, sbimf_sid_bluechip, sbimf_sid_lte, sbimf_sid_smallcap, sebi_mf_faq_2024_09 | 9 | pass |
| riskometer | sbimf_factsheet_2026_01, sbimf_factsheet_2026_06, sbimf_kim_flexicap, sbimf_sid_bluechip, sbimf_sid_lte, sbimf_sid_smallcap, sebi_mf_faq_2024_09 | 7 | pass |
| benchmark | sbimf_factsheet_2026_01, sbimf_factsheet_2026_06, sbimf_factsheet_bluechip_2025_08, sbimf_factsheet_lte_2024_07, sbimf_kim_flexicap, sbimf_sid_bluechip, sbimf_sid_lte, sbimf_sid_smallcap, sebi_mf_faq_2024_09 | 9 | pass |
| statement_download | amfi_cas, sbimf_elss_campaign, sbimf_factsheet_2026_01, sbimf_factsheet_2026_06, sbimf_kim_flexicap, sbimf_sid_bluechip, sbimf_sid_lte, sbimf_sid_smallcap, sbimf_tax_reckoner_fy2026_27, sbimf_ways_to_invest, sebi_mf_faq_2024_09 | 11 | pass |
