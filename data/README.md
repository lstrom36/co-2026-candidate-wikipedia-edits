# data/

| Path | In the repo? | What it is |
| --- | --- | --- |
| `candidates_2022.csv`, `candidates_2026.csv` | yes | Every nominee, their page title (blank if none) and Cook rating |
| `page_check_2022.csv`, `page_check_2026.csv` | yes | Output of `src/check_pages.py` |
| `sample/` | yes | Small samples of the cleaned tables, plus the full `pages` and `protection` tables |
| `raw/` | **no** | Raw API JSON from `src/collect.py`. Has usernames, IPs and edit comments |
| `clean/` | **no** | Full cleaned tables from `src/clean.py`. No usernames, but revision IDs, exact times and editor hashes could be linked back to editors |

Every field is described in [`../docs/data_dictionary.md`](../docs/data_dictionary.md). Page-view counts come from the Wikimedia Pageviews API (CC0). Edit metadata comes from the MediaWiki Action API (Wikipedia content is CC BY-SA).
