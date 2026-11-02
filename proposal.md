# Edits Before the Vote: Colorado Candidates' Wikipedia Pages in 2026

**Author:** Liku Strom

*Proposal, October 19, 2026. Repository copy, wording revised November 1, 2026.*

## 1. Research question

How much more often do people edit the English Wikipedia pages of Colorado candidates in the seven weeks before the November 3, 2026 election than in the summer after the June primary? Is the jump bigger in competitive races than in safe ones? And what percent of the edits come from logged-out users rather than logged-in ones?

### What would prove me wrong

Editing during the campaign runs slower than it did over the summer, or competitive and safe races rise by the same amount.

### Who would care

Many voters look candidates up on Wikipedia. The people who watch election pages for vandalism would want to know when the spikes hit and on which pages.

### What I expect

Edits per day at least double during the campaign, with bigger jumps in the races rated competitive (CO-8 Toss-up, CO-3 and CO-5 Likely R). I also expect unregistered editors to be more active in the fall than in the summer.

### What would surprise me

Safe-seat pages going up as much as competitive ones. No increase at all. Or editing that just follows page views.

## 2. Data sources and method

### Sources

Everything is public; no login needed.

- **Edits:** MediaWiki Action API, `https://en.wikipedia.org/w/api.php?action=query&prop=revisions&rvprop=ids|timestamp|user|size|tags|comment|flags`. Gives each edit's time, editor, page size and tags like `mw-reverted`.
- **Page views:** Wikimedia Pageviews API, `https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{title}/daily/{start}/{end}`. Daily views from people, not bots.
- **Protection:** Action API, `action=query&list=logevents&letype=protect`. Shows when a page got locked.
- **Race ratings:** Cook Political Report ratings, listed with dates on each race's Wikipedia article.

### How I'll collect

I'll call the APIs with Python `requests`, with no web scraping. Past edits and past page views stay available, so nothing has to be collected live. I'll do one complete run after November 17 and save a backup copy before Election Day.

### Scope

- **Candidates:** major-party nominees for governor (open seat), US Senate, and all eight House seats, and an independent nominee for governor (Greg Lopez). This gives 21 candidates, and 15 of these have Wikipedia pages. The six House challengers who don't are Peterson (CO-1), Dennison (CO-2), Romero (CO-3), Killin (CO-5), Clark (CO-6) and Bennett (CO-7).
- **Records:** ~1,900 page-view records in total (15 pages × 127 days), as well as all edits in this period. My first guess was 50 edits, but the 2022 pilot returned 686 across 14 pages (median 27 per page), so I now expect a total in the hundreds.
- **Pilot and fallback:** same design, on the completed 2022 cycle (20 nominees, 14 have pages). I'll do the pilot on this first.

| Period | 2026 dates | Days |
|---|---|---|
| Baseline | July 14 to September 14 | 63 |
| Campaign (last seven weeks) | September 15 to November 3 | 50 |
| Post-election | November 4 to 17 | 14 |

The baseline begins two weeks after the June 30 primary so the primary spike doesn't inflate it.

### What answers the question

1. **Main number:** for each page, campaign edits per day divided by baseline edits per day. Then I compare the median for competitive races (rated Likely or closer: CO-3, CO-5, CO-8) with the median for safe races (rated Solid). Same thing for incumbents vs. challengers.
2. **Weekly timeline:** edits per page each week, competitive vs. safe, with ballots going out (October 2), the CO-8 debate (October 7) and Election Day marked.
3. **Editor types by period:** shares from registered accounts, temporary accounts, IPs and bots, plus how many got reverted.
4. **Page views vs. edits:** does editing just follow attention?

## 3. Ethics and feasibility

### Terms of service and robots.txt

Wikimedia's Terms of Use allow reuse of content under CC BY-SA, and page view statistics are CC0. Wikimedia's Robot Policy asks bots to identify themselves and send requests one at a time. I'm requesting edit metadata, not page text.

Wikipedia's [robots.txt](https://en.wikipedia.org/robots.txt) tells general crawlers `Disallow: /w/`, and its only exception for `/w/api.php` is `action=mobileview`, so the `action=query` calls I plan to make fall under the disallowed path. Wikimedia's [Robot Policy](https://wikitech.wikimedia.org/wiki/Robot_policy) says to honor robots.txt, but it also has rules written for this exact URL that allow logged-out clients one request at a time and under five per second, so I read the `Disallow` line as aimed at crawlers and stay within those API limits.

### Staying within limits

- Every request sends a User-Agent with my contact info, which Wikimedia requires: `COElectionEditsBot/0.1 ([my contact info]; student course project, read-only) python-requests`.
- One request at a time, with a one-second wait after each. That's 60 a minute at most, way under the rate limits Wikimedia added in spring 2026.
- Action API calls include `maxlag=5`, so the script backs off when Wikipedia's servers are busy. If it gets a 429, it waits as long as `Retry-After` says.

### Personal data

Usernames and IP addresses count as personal data even though anyone can look them up. Since November 4, 2025, English Wikipedia has treated unregistered users as temporary accounts rather than IPs. Raw API output never leaves my computer and isn't hosted on GitHub. In my database, each username becomes an editor type plus a salted hash, so I can tell editors apart without using their names. Edit comments become a yes/no keyword flag, I won't collect admin usernames, and I'll report only editor counts.

### One retrieved record

User-Agent sent: `COElectionEditsBot/0.1 ([email omitted in public copy]; student course project, read-only) python-requests/2.34.2`

**Request 1: MediaWiki Action API, `prop=revisions`**

```
GET https://en.wikipedia.org/w/api.php?action=query&prop=revisions&titles=Gabe_Evans&rvprop=ids%7Ctimestamp%7Cuser%7Cuserid%7Csize%7Ctags%7Ccomment%7Cflags&rvlimit=1&rvdir=older&rvstart=2026-10-15T23%3A59%3A59Z&format=json&formatversion=2&maxlag=5
Status code: 200
```

```json
{
  "pageid": 72348764,
  "title": "Gabe Evans",
  "revision": {
    "revid": 1377828882,
    "parentid": 1375488686,
    "minor": false,
    "user": "[masked: registered]",
    "timestamp": "2026-10-01T10:30:39Z",
    "size": 21618,
    "comment": "/* AI data centers */ Bill failed in the Senate.",
    "tags": [
      "visualeditor",
      "editcheck-newreference"
    ]
  }
}
```

Fields used: `timestamp`, `user` → editor type (registered), `size`, `tags` (`mw-reverted` etc.), `comment`, `parentid`

**Request 2: Wikimedia Pageviews API**

```
GET https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/Gabe_Evans/daily/20261015/20261015
Status code: 200
```

```json
{
  "project": "en.wikipedia",
  "article": "Gabe_Evans",
  "granularity": "daily",
  "timestamp": "2026101500",
  "access": "all-access",
  "agent": "user",
  "views": 494
}
```

Fields used: `timestamp`, `views`

### Fields I'll use

- `timestamp`: which period an edit falls in
- `user`: turned into an editor type, then dropped
- `size`: how big each change was
- `tags`: `mw-reverted` means it got undone later
- `comment`: only for the keyword flag
- `timestamp` and `views` from page views

### Biggest risk and fallback

Not enough data in the competitive group. Romero and Killin don't have pages, so I only get four competitive pages in 2026, and safe-seat pages might barely get edited. My fallback is 2022, which I'm running first as a pilot anyway. CO-8 was a Toss-up that year with both candidates on Wikipedia, so adding 2022 roughly doubles my pages. If daily counts are too small, I'll switch to weekly totals.

## AI-use disclosure

I used Claude (Anthropic). It found the candidate list, page titles, and Cook ratings; `check_pages.py` double-checks the page titles only. It summarized Wikimedia's User-Agent policy, Robot policy, the 2026 rate limits, and the temporary-accounts change, which I then read myself. It drafted the Python scripts, which I ran, tested, and can explain. It also drafted the proposal skeleton/outline, and it formatted this repository copy of the proposal as Markdown and set up the repository's placeholder files. It also read Wikipedia's robots.txt and the Robot Policy, wrote the passage about them in section 3, revised the wording of the prose in this copy and in the README, and ran `check_pages.py`, the 2022 pilot download, and the 2026 backup download. The scripts aren't in this repository yet; I'll add them with the data.
