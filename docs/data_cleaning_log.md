# Data cleaning log

Source files: nhrdf_onion_maharashtra.csv



| Step | Rows affected |
|---|---:|
| Raw rows loaded | 7,426 |
| Non-numeric / blank values in min_price set to missing | 0 |
| Non-numeric / blank values in max_price set to missing | 0 |
| Non-numeric / blank values in modal_price set to missing | 0 |
| Non-numeric / blank values in arrivals_qtl set to missing | 0 |
| Unparseable dates dropped | 0 |
| Rows with missing / zero modal price dropped | 0 |
| Rows where min_price > max_price (swapped back) | 0 |
| Rows where modal price outside min-max range (clamped) | 0 |
| Duplicate market-day-commodity-variety rows removed | 0 |
| Rows flagged as price outliers (kept, flag column added) | 2 |
| Final clean rows | 7,426 |
