# data/

This folder will hold only **de-identified, aggregated** data derived from the MediaWiki Action API and the Wikimedia Pageviews API.

- Raw API output (with usernames, temporary-account names, IPs, and edit comments) stays on my computer and is **not** committed. `data/raw/` is listed in `.gitignore`.
- Committed files will use editor types and salted hashes instead of usernames, and a yes/no keyword flag instead of edit comments.
- Page-view counts come from the Wikimedia Pageviews API (CC0).

*Planned files (to be added):* per-edit table (page, timestamp, period, editor type, size change, reverted flag), daily page views per page, and the candidate/race-rating lookup table.
