# Data dictionary

`src/clean.py` builds four tables per cycle. The full tables live in `data/clean/` on my computer. The repo has samples of `edits` and `page_days` and the full `pages` and `protection` tables in [`data/sample/`](../data/sample/).

Every table has `cycle` and `title`, so they join on those two columns. Dates are UTC calendar days (`YYYY-MM-DD`). True/false columns are written as `True` / `False`.

## Study periods (`period`)

| Value | 2022 | 2026 |
| --- | --- | --- |
| `baseline` | Jul 12 – Sep 19 (70 days) | Jul 14 – Sep 14 (63 days) |
| `campaign` | Sep 20 – Nov 8 (50 days) | Sep 15 – Nov 3 (50 days) |
| `post` | Nov 9 – Nov 22 (14 days) | Nov 4 – Nov 17 (14 days) |

The baseline starts two weeks after each primary. The 2022 baseline is longer, so compare edits **per day**, not totals.

## `pages_<cycle>.csv`: one row per candidate page

| Field | Type | Meaning |
| --- | --- | --- |
| `cycle` | int | Election year (2022 or 2026) |
| `title` | text | Wikipedia page title, with underscores (e.g. `Gabe_Evans`) |
| `candidate` | text | Candidate's name |
| `race` | text | `Governor`, `Senate`, or House district `CO-1` to `CO-8` |
| `party` | text | `D`, `R`, or `I` (independent) |
| `incumbent` | Y/N | Whether the candidate held this seat going into the election |
| `cook_rating` | text | Cook Political Report rating for the race (`Solid D`, `Likely R`, `Tossup`, ...) |
| `rating_as_of` | date | Date of that rating, as listed on the race's Wikipedia article |
| `competitive` | bool | `True` if the rating is Likely or closer (Tossup, Lean, Likely). Set in `src/config.py` |
| `page_created` | date | Date of the page's first revision, from `check_pages.py`. Blank if the title is now a redirect |
| `redirect_now` | bool | `True` if the title redirects somewhere else today (Joe O'Dea, 2022) |
| `live_days_baseline`, `live_days_campaign`, `live_days_post` | int | Days in each period when the page was a real article, not missing or a redirect. Use these as the denominator for edits per day |
| `edits_total` | int | Edits to the page in the whole window |

## `edits_<cycle>.csv`: one row per edit

| Field | Type | Meaning |
| --- | --- | --- |
| `cycle`, `title` | | See above |
| `rev_id` | int | Wikipedia revision ID. **Full table only** |
| `timestamp_utc` | datetime | Exact time of the edit. **Full table only** |
| `date` | date | Day of the edit (UTC) |
| `period` | text | `baseline`, `campaign` or `post` |
| `editor_type` | text | `registered` (normal account), `bot` (account in the bot user group), `temporary` (logged-out editor with a temporary account, name starts with `~`, since Nov 4, 2025), `ip` (logged-out editor shown as an IP address, before that change), `hidden` (username removed by admins) |
| `unregistered` | bool | `True` if `editor_type` is `temporary` or `ip` |
| `editor_hash` | text | First 12 characters of SHA-256(salt + username). The same editor gets the same hash, so I can count distinct editors without storing names. **Full table only** |
| `minor` | bool | The editor marked it as a minor edit |
| `size` | int | Page size in bytes after the edit |
| `size_delta` | int | Bytes added (+) or removed (−) by this edit. Blank if the previous size is unknown. For the edit that created a page, it equals `size` |
| `page_was_article` | bool | `True` if the page was 300 bytes or more after the edit. Smaller pages are redirects |
| `was_reverted` | bool | The edit has the `mw-reverted` tag: someone undid it later |
| `is_revert` | bool | The edit undid someone else (tag `mw-undo`, `mw-rollback` or `mw-manual-revert`) |
| `event_keyword` | bool | The edit comment mentions a campaign event word: poll, endorse, debate, ad, advert, fundrais, result, won, defeat, elected, concede. The comment itself is not kept |
| `comment_hidden` | bool | Admins hid the edit comment |

## `page_days_<cycle>.csv`: one row per page per day

Every page has a row for every day in the window, including days with no edits.

| Field | Type | Meaning |
| --- | --- | --- |
| `cycle`, `title`, `date`, `period` | | See above |
| `article_live` | bool | The page was a real article at the end of that day (it existed and was 300 bytes or more) |
| `edit_protection` | text | Strongest edit protection at any point that day: `none`, `autoconfirmed` (semi-protected: no temporary or IP editors, no brand-new accounts), `extendedconfirmed`, `templateeditor` or `sysop` |
| `views` | int | Page views by people that day (Pageviews API, `agent=user`). `0` when the API returned nothing but the page was live. Blank when the page wasn't an article |
| `edits` | int | Number of edits that day |
| `edits_registered` | int | Edits by registered, non-bot accounts |
| `edits_unregistered` | int | Edits by temporary accounts and IP addresses |
| `edits_bot` | int | Edits by bot accounts |
| `edits_hidden` | int | Edits whose username was hidden |
| `edits_reverted` | int | Edits that were later reverted |
| `distinct_editors` | int | Different editors (distinct hashes) that day |

`edits` = `edits_registered` + `edits_unregistered` + `edits_bot` + `edits_hidden`.

## `protection_<cycle>.csv`: one row per protection log event

Includes events from before the window, so the starting protection level is known. Admin usernames and log comments are not collected.

| Field | Type | Meaning |
| --- | --- | --- |
| `cycle`, `title` | | See above |
| `timestamp_utc` | datetime | When the protection changed |
| `date` | date | Day of the change |
| `period` | text | `baseline`, `campaign`, `post`, or `before_window` |
| `action` | text | `protect` (new), `modify` (changed), `unprotect` (removed), or `move_prot` (carried over from a page move) |
| `edit_level` | text | Who can edit after this event (`autoconfirmed`, `extendedconfirmed`, `sysop`, ...). Blank means no edit protection |
| `edit_expiry` | text | When the edit protection ends: a timestamp, or `infinite` |
| `move_level` | text | Who can rename (move) the page. Not used in the analysis |

## Input files

| File | Meaning |
| --- | --- |
| `data/candidates_<cycle>.csv` | Every nominee: `cycle`, `race`, `candidate`, `party`, `incumbent`, `title` (blank if no page), `cook_rating`, `rating_as_of`, `note` |
| `data/page_check_<cycle>.csv` | Output of `check_pages.py`: `exists`, `redirects_to`, `disambiguation`, `pageid`, current `protection`, `created`, `covers_baseline` (page existed on the first baseline day) |
