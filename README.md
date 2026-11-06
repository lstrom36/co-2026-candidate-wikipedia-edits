# Edits Before the Vote: Colorado Candidates' Wikipedia Pages in 2026

**Author:** Liku Strom

## Summary

Do Wikipedia pages for Colorado's 2026 candidates get edited more as Election Day gets close? This project covers the governor's race, the US Senate race and all eight US House seats. Using the public MediaWiki Action API and the Wikimedia Pageviews API, I compare edits per day in the last seven weeks of the campaign (September 15 – November 3, 2026) with a summer baseline after the June primary (July 14 – September 14). I also ask whether the increase is larger in competitive races (CO-3, CO-5, CO-8) than in safe ones, what share of edits come from registered versus unregistered (temporary-account) editors, and whether editing simply follows page views. The completed 2022 cycle serves as a pilot and fallback.

Full proposal: [`proposal.md`](proposal.md)

## Data

### Sources

| What | Where it comes from | License |
| --- | --- | --- |
| Edits to each page (time, editor, page size, tags, comment) | MediaWiki Action API, `https://en.wikipedia.org/w/api.php?action=query&prop=revisions` | Wikipedia text is CC BY-SA; I only use edit metadata |
| Daily page views by people (not bots) | Wikimedia Pageviews API, `https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{title}/daily/{start}/{end}` | CC0 |
| When a page was locked (protected) | MediaWiki Action API, `action=query&list=logevents&letype=protect` | CC BY-SA |
| Bot accounts | MediaWiki Action API, `action=query&list=users&usprop=groups` | CC BY-SA |
| Candidates, page titles, Cook ratings | Typed in by hand from each race's Wikipedia article ([`data/candidates_2026.csv`](data/candidates_2026.csv), [`data/candidates_2022.csv`](data/candidates_2022.csv)), checked with `src/check_pages.py` | |

Every request sends a User-Agent with my contact email, waits one second after each request, and never runs two requests at once. Action API calls add `maxlag=5`, and the code waits whenever it gets a 429 with `Retry-After` (see [`src/wiki_http.py`](src/wiki_http.py)).

### When I collected it

| Cycle | Collected | Window covered | Note |
| --- | --- | --- | --- |
| 2022 (pilot) | [DATE] | Jul 12 – Nov 22, 2022 | Finished cycle, complete |
| 2026 | [DATE] | Jul 14 – [END], 2026 | Snapshot. The post-election window (Nov 4–17) isn't over yet, so I'll run it again after Nov 17 |

All dates are UTC days.

### How many records

| Table | 2022 | 2026 | One row is |
| --- | --- | --- | --- |
| `pages` | 14 | 15 | a candidate page |
| `edits` | [N] | [N] | one edit |
| `page_days` | 1,876 | [N] | one page on one day (edits, views, protection) |
| `protection` | [N] | [N] | one protection log event |

The 2022 cycle has 20 nominees and 14 with pages. 2026 has 21 nominees and 15 with pages. Six House challengers in each cycle have no Wikipedia page, so they aren't in the data. Full per-page counts are in the cleaning logs: [`docs/cleaning_log_2022.md`](docs/cleaning_log_2022.md) and [`docs/cleaning_log_2026.md`](docs/cleaning_log_2026.md).

### What's in the repo

- [`data/sample/`](data/sample/): a 50-row sample of `edits` and a 40-row sample of `page_days` for each cycle, plus the full `pages` and `protection` tables (they're small and have no personal data).
- [`docs/data_dictionary.md`](docs/data_dictionary.md): every field and what it means.
- [`data/page_check_2022.csv`](data/page_check_2022.csv), [`data/page_check_2026.csv`](data/page_check_2026.csv): output of `check_pages.py` (does each page exist, when it was created, is it a redirect).

### What I left out and why

- **Raw API output (`data/raw/`).** It has usernames, IP addresses, temporary-account names and edit comments. Wikipedia shows these publicly, but they are still personal data, and my proposal says raw output never leaves my computer.
- **The full cleaned tables (`data/clean/`).** They have no usernames, but the full `edits` table still has revision IDs and exact timestamps, which link straight back to a username on Wikipedia, and an editor hash, which would let someone follow one editor across pages. The `edits` sample drops all three. I report editors only as counts by type.
- **The hashing salt (`salt.txt`) and my email (`.env`).** Anyone with the salt could re-hash known usernames and match them. My email stays out of the public code; you set your own in `.env`.
- **Size and terms are not the problem here.** The data is small (a few MB) and the licenses allow sharing. The only reason for leaving things out is personal information.

### Things to know about the data

- **Joe O'Dea (2022)** is now a redirect to the 2022 Senate race article. The code collects the history of the `Joe_O'Dea` title itself, not the race article, and uses page size to tell article days from redirect days (`article_live`).
- **Adam Frisch (2022)** got his page on July 27, 2022, after the baseline started. Rates for his page should use the days the page existed (`live_days_*` in `pages`), not calendar days.
- **Lauren Boebert's page** has been semi-protected (`autoconfirmed`) for years, and **Melat Kiros's** page is semi-protected now. Temporary-account and IP editors can't edit a protected page, so these pages will show few unregistered edits no matter what. `edit_protection` in `page_days` marks every protected day.
- **Logged-out editors changed in the middle of my comparison.** In 2022 they show up as IP addresses. Since November 4, 2025, English Wikipedia gives them temporary accounts (names starting with `~`). Both count as "unregistered."
- **Bot status is current, not historical.** It comes from each account's user groups at collection time.

## Methods

*Placeholder.* Planned: the campaign-to-baseline ratio of edits per day for each page, compared across competitive and safe races and across incumbents and challengers.

## Findings

*Placeholder.* To be added after the final data run (after November 17, 2026).

## How to reproduce

You need Python 3.10 or newer.

```
pip install -r requirements.txt
cp .env.example .env        # then put your own email in .env
```

Run everything from the repo root:

| Step | Command | What it does |
| --- | --- | --- |
| 1 | `python src/check_pages.py 2022` (and `2026`) | Confirms each page title exists and when it was created |
| 2 | `python src/collect.py 2022` (and `2026`) | Downloads raw JSON into `data/raw/` (about 75 requests and 2 minutes per cycle) |
| 3 | `python src/clean.py 2022` (and `2026`) | Builds the tables in `data/clean/`, the samples in `data/sample/`, and the cleaning log in `docs/` |

If the 2026 window isn't over when you run step 2, the data stops at yesterday and is saved as a snapshot. Running `python src/collect.py 2026 --force` after November 17 gets the full window. Your hashes won't match mine, because `clean.py` makes a new random salt the first time it runs.

| File | What it does |
| --- | --- |
| [`src/config.py`](src/config.py) | Study windows, endpoints, pauses, competitive-race cutoff, keyword list |
| [`src/wiki_http.py`](src/wiki_http.py) | The only place requests are made: User-Agent, 1 s pause, maxlag, 429 handling |
| [`src/check_pages.py`](src/check_pages.py) | Checks page titles before collecting |
| [`src/collect.py`](src/collect.py) | Saves raw revisions, page views, protection logs and bot flags |
| [`src/clean.py`](src/clean.py) | Turns raw JSON into tidy, de-identified tables |
