"""Turn the raw JSON from collect.py into tidy, de-identified tables.

Run (from the repo root):
    python src/clean.py 2022
    python src/clean.py 2026     (uses data/raw/2026, or the newest snapshot)

Writes the full tables to data/clean/ (git-ignored):
    edits_<cycle>.csv       one row per edit
    page_days_<cycle>.csv   one row per page per day (edits, views, protection)
    protection_<cycle>.csv  one row per protection log event
    pages_<cycle>.csv       one row per candidate page

and the files that ARE committed:
    data/sample/edits_<cycle>_sample.csv      50 random edits, coarsened
    data/sample/page_days_<cycle>_sample.csv  40 random page-days
    data/sample/pages_<cycle>.csv             full (one row per page)
    data/sample/protection_<cycle>.csv        full (no usernames in it)
    docs/cleaning_log_<cycle>.md              what this script did, with counts

Privacy: usernames, user IDs, IPs and edit comments never reach data/clean/.
Each editor becomes an editor type plus a salted hash (so distinct editors can
be counted), and each comment becomes a yes/no "event keyword" flag.
"""

import csv
import datetime as dt
import glob
import hashlib
import json
import os
import random
import secrets
import sys
import urllib.parse
from collections import Counter, defaultdict

import config

REVERT_TAGS = {"mw-undo", "mw-rollback", "mw-manual-revert"}
LEVEL_RANK = {"none": 0, "autoconfirmed": 1, "extendedconfirmed": 2,
              "templateeditor": 3, "sysop": 4}
UTC = dt.timezone.utc


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def parse_ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def days_between(start, end):
    d = start
    while d <= end:
        yield d
        d += dt.timedelta(days=1)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_csv(path, rows, fields):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {os.path.relpath(path, config.ROOT)} ({len(rows)} rows)")


def raw_base(cycle):
    full = os.path.join(config.RAW_DIR, str(cycle))
    if os.path.isdir(full):
        return full
    snaps = sorted(glob.glob(os.path.join(config.RAW_DIR, f"{cycle}_snapshot_*")))
    if not snaps:
        sys.exit(f"No raw data for {cycle}. Run: python src/collect.py {cycle}")
    print("Using snapshot", os.path.relpath(snaps[-1], config.ROOT))
    return snaps[-1]


def get_salt():
    """Secret salt for hashing editor names. Created once, never committed."""
    env = os.environ.get("COEDITS_SALT")
    if env:
        return env
    if not os.path.exists(config.SALT_FILE):
        with open(config.SALT_FILE, "w") as f:
            f.write(secrets.token_hex(16))
        print("  created salt.txt (git-ignored; keep it so hashes stay stable)")
    with open(config.SALT_FILE) as f:
        return f.read().strip()


def editor_type(rev, bot_flags):
    if rev.get("userhidden"):
        return "hidden"
    if rev.get("anon"):
        return "ip"
    user = rev.get("user", "")
    if rev.get("temp") or user.startswith("~"):
        return "temporary"
    if bot_flags.get(user):
        return "bot"
    return "registered"


def load_candidates(cycle):
    with open(config.CYCLES[cycle]["candidates_file"], newline="",
              encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["title"].strip()]
    for r in rows:
        r["competitive"] = r["cook_rating"] in config.COMPETITIVE_RATINGS
    return rows


def load_page_check(cycle):
    path = os.path.join(config.PAGE_CHECK_DIR, f"page_check_{cycle}.csv")
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {r["title"]: r for r in csv.DictReader(f)}


# ---------------------------------------------------------------------------
# protection: replay the log to get the edit-protection level on each day
# ---------------------------------------------------------------------------
def protection_timeline(events):
    """Return a list of (time, level, expiry) states, oldest first."""
    states = []
    for e in sorted(events, key=lambda e: e["timestamp"]):
        action = e.get("action", "")
        t = parse_ts(e["timestamp"])
        if action == "unprotect":
            states.append((t, "none", None))
        elif action in ("protect", "modify"):
            level, expiry = "none", None
            for d in e.get("params", {}).get("details", []):
                if d.get("type") == "edit":
                    level = d.get("level", "none")
                    exp = d.get("expiry", "infinite")
                    expiry = None if exp in ("infinite", "infinity", "") else parse_ts(exp)
            states.append((t, level, expiry))
        # move_prot (protection carried over in a page move) is ignored
    return states


def level_at(states, t):
    level = "none"
    for (st, lv, exp) in states:
        if st > t:
            break
        level = lv if (exp is None or exp > t) else "none"
    return level


def day_level(states, day):
    """Strongest edit protection in effect at any point during a UTC day."""
    start = dt.datetime.combine(day, dt.time(0, 0, 0), UTC)
    end = dt.datetime.combine(day, dt.time(23, 59, 59), UTC)
    checks = [start, end] + [st for (st, _, _) in states if start <= st <= end]
    return max((level_at(states, t) for t in checks),
               key=lambda lv: LEVEL_RANK.get(lv, 0))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main(cycle):
    base = raw_base(cycle)
    info_path = os.path.join(base, "collection_info.json")
    info = load_json(info_path) if os.path.exists(info_path) else {}
    win_start = config.window_for(cycle)[0]
    win_end = (dt.date.fromisoformat(info["window_end"]) if info.get("window_end")
               else config.window_for(cycle)[1])
    all_days = list(days_between(win_start, win_end))

    cands = load_candidates(cycle)
    page_check = load_page_check(cycle)
    bot_flags = load_json(os.path.join(base, "bot_flags.json"))
    salt = get_salt()
    keywords = [k.lower() for k in config.EVENT_KEYWORDS]

    edit_rows, day_rows, prot_rows, page_rows = [], [], [], []
    log = []   # per-page lines for the cleaning log
    totals = Counter()

    for c in cands:
        title = c["title"]
        fname = urllib.parse.quote(title, safe="") + ".json"
        key = {"cycle": cycle, "title": title}

        # ---- revisions -----------------------------------------------------
        raw = load_json(os.path.join(base, "revisions", fname))
        raw_revs = raw["revisions"]
        seen, revs, n_dup, n_out = set(), [], 0, 0
        for r in raw_revs:
            if r["revid"] in seen:
                n_dup += 1
                continue
            seen.add(r["revid"])
            day = parse_ts(r["timestamp"]).date()
            if not (win_start <= day <= win_end):
                n_out += 1
                continue
            revs.append(r)
        revs.sort(key=lambda r: (r["timestamp"], r["revid"]))

        before = raw.get("revision_before_window") or {}
        prev_size = before.get("size")
        size_by_day = {}  # page size at the end of each day that had edits
        page_edits = []
        for r in revs:
            ts = parse_ts(r["timestamp"])
            tags = set(r.get("tags", []))
            user = r.get("user", "")
            size = r.get("size")
            if r.get("parentid") == 0:
                delta = size            # this edit created the page
            elif prev_size is not None and size is not None:
                delta = size - prev_size
            else:
                delta = ""
            comment = f" {(r.get('comment') or '').lower()} "
            etype = editor_type(r, bot_flags)
            row = {
                **key,
                "rev_id": r["revid"],
                "timestamp_utc": r["timestamp"],
                "date": ts.date().isoformat(),
                "period": config.period_of(ts.date(), cycle),
                "editor_type": etype,
                "unregistered": etype in ("ip", "temporary"),
                "editor_hash": (hashlib.sha256((salt + user).encode()).hexdigest()[:12]
                                if user else ""),
                "minor": bool(r.get("minor")),
                "size": size if size is not None else "",
                "size_delta": delta,
                "page_was_article": (size is not None
                                     and size >= config.REDIRECT_MAX_BYTES),
                "was_reverted": "mw-reverted" in tags,
                "is_revert": bool(tags & REVERT_TAGS),
                "event_keyword": any(k in comment for k in keywords),
                "comment_hidden": bool(r.get("commenthidden")),
            }
            page_edits.append(row)
            if size is not None:
                prev_size = size
                size_by_day[ts.date()] = size

        # ---- page views ------------------------------------------------------
        pv = load_json(os.path.join(base, "pageviews", fname))
        views = {}
        for item in pv.get("items", []):
            views[dt.datetime.strptime(item["timestamp"][:8], "%Y%m%d").date()] = item["views"]

        # ---- protection log --------------------------------------------------
        prot = load_json(os.path.join(base, "protection", fname))
        states = protection_timeline(prot.get("events", []))
        for e in prot.get("events", []):
            ts = parse_ts(e["timestamp"])
            details = e.get("params", {}).get("details", [])
            by_type = {d.get("type"): d for d in details}
            prot_rows.append({
                **key,
                "timestamp_utc": e["timestamp"],
                "date": ts.date().isoformat(),
                "period": config.period_of(ts.date(), cycle) or "before_window",
                "action": e.get("action", ""),
                "edit_level": by_type.get("edit", {}).get("level", ""),
                "edit_expiry": by_type.get("edit", {}).get("expiry", ""),
                "move_level": by_type.get("move", {}).get("level", ""),
            })

        # ---- one row per page per day -----------------------------------------
        by_day = defaultdict(list)
        for row in page_edits:
            by_day[row["date"]].append(row)
        size_now = before.get("size")
        zero_filled = live_days = protected_days = 0
        live_by_period = Counter()
        for day in all_days:
            size_now = size_by_day.get(day, size_now)
            live = size_now is not None and size_now >= config.REDIRECT_MAX_BYTES
            todays = by_day.get(day.isoformat(), [])
            types = Counter(r["editor_type"] for r in todays)
            if day in views:
                v = views[day]
            elif live:
                v = 0             # the API leaves out days with zero views
                zero_filled += 1
            else:
                v = ""            # page was not an article that day
            level = day_level(states, day)
            period = config.period_of(day, cycle)
            live_days += live
            live_by_period[period] += live
            protected_days += level != "none"
            day_rows.append({
                **key,
                "date": day.isoformat(),
                "period": period,
                "article_live": live,
                "edit_protection": level,
                "views": v,
                "edits": len(todays),
                "edits_registered": types["registered"],
                "edits_unregistered": types["temporary"] + types["ip"],
                "edits_bot": types["bot"],
                "edits_hidden": types["hidden"],
                "edits_reverted": sum(r["was_reverted"] for r in todays),
                "distinct_editors": len({r["editor_hash"] for r in todays
                                         if r["editor_hash"]}),
            })

        pc = page_check.get(title, {})
        page_rows.append({
            **key,
            "candidate": c["candidate"], "race": c["race"], "party": c["party"],
            "incumbent": c["incumbent"], "cook_rating": c["cook_rating"],
            "rating_as_of": c["rating_as_of"], "competitive": c["competitive"],
            "page_created": pc.get("created", ""),
            "redirect_now": bool(pc.get("redirects_to")),
            "live_days_baseline": live_by_period["baseline"],
            "live_days_campaign": live_by_period["campaign"],
            "live_days_post": live_by_period["post"],
            "edits_total": len(page_edits),
        })

        edit_rows.extend(page_edits)
        totals.update({"raw_revisions": len(raw_revs), "duplicates": n_dup,
                       "outside_window": n_out, "kept": len(page_edits),
                       "zero_filled_view_days": zero_filled})
        log.append({
            "title": title, "rev_status": raw.get("status"),
            "pv_status": pv.get("status"), "raw": len(raw_revs), "dup": n_dup,
            "out": n_out, "kept": len(page_edits),
            "pv_days": len(views), "zero_filled": zero_filled,
            "live_days": live_days, "protected_days": protected_days,
            "prot_events": len(prot.get("events", [])),
            "errors": raw.get("errors") or [],
        })

    # ---- consistency checks ----------------------------------------------------
    assert sum(r["edits"] for r in day_rows) == len(edit_rows), \
        "page_days edit counts do not add up to the edits table"
    assert len(day_rows) == len(cands) * len(all_days)

    # ---- write full tables (git-ignored) ----------------------------------------
    print("Full tables:")
    edit_fields = list(edit_rows[0].keys()) if edit_rows else ["cycle", "title"]
    day_fields = list(day_rows[0].keys())
    prot_fields = ["cycle", "title", "timestamp_utc", "date", "period", "action",
                   "edit_level", "edit_expiry", "move_level"]
    page_fields = list(page_rows[0].keys())
    write_csv(os.path.join(config.CLEAN_DIR, f"edits_{cycle}.csv"), edit_rows, edit_fields)
    write_csv(os.path.join(config.CLEAN_DIR, f"page_days_{cycle}.csv"), day_rows, day_fields)
    write_csv(os.path.join(config.CLEAN_DIR, f"protection_{cycle}.csv"), prot_rows, prot_fields)
    write_csv(os.path.join(config.CLEAN_DIR, f"pages_{cycle}.csv"), page_rows, page_fields)

    # ---- committed samples ---------------------------------------------------------
    # The edits sample leaves out rev_id, timestamp_utc and editor_hash: any one
    # of them lets a reader look the edit up on Wikipedia and see the username.
    print("Samples for the repo:")
    rng = random.Random(config.SAMPLE_SEED)
    sample_edit_fields = [f for f in edit_fields
                          if f not in ("rev_id", "timestamp_utc", "editor_hash")]
    e_sample = rng.sample(edit_rows, min(config.SAMPLE_EDITS, len(edit_rows)))
    e_sample.sort(key=lambda r: (r["title"], r["timestamp_utc"]))
    write_csv(os.path.join(config.SAMPLE_DIR, f"edits_{cycle}_sample.csv"),
              e_sample, sample_edit_fields)

    half = config.SAMPLE_PAGE_DAYS // 2
    with_edits = [r for r in day_rows if r["edits"] > 0]
    without = [r for r in day_rows if r["edits"] == 0]
    d_sample = (rng.sample(with_edits, min(half, len(with_edits)))
                + rng.sample(without, min(config.SAMPLE_PAGE_DAYS - half, len(without))))
    d_sample.sort(key=lambda r: (r["title"], r["date"]))
    write_csv(os.path.join(config.SAMPLE_DIR, f"page_days_{cycle}_sample.csv"),
              d_sample, day_fields)
    write_csv(os.path.join(config.SAMPLE_DIR, f"pages_{cycle}.csv"), page_rows, page_fields)
    write_csv(os.path.join(config.SAMPLE_DIR, f"protection_{cycle}.csv"), prot_rows, prot_fields)

    write_log(cycle, base, info, win_start, win_end, cands, log, totals,
              edit_rows, day_rows, prot_rows)


def write_log(cycle, base, info, win_start, win_end, cands, log, totals,
              edit_rows, day_rows, prot_rows):
    now = dt.datetime.now(UTC).isoformat(timespec="seconds")
    by_period = Counter(r["period"] for r in edit_rows)
    by_type = Counter(r["editor_type"] for r in edit_rows)
    L = []
    L.append(f"# Cleaning log: {cycle} cycle\n")
    L.append(f"Generated by `src/clean.py {cycle}` on {now}.\n")
    L.append("## Input\n")
    L.append(f"- Raw folder: `{os.path.relpath(base, config.ROOT)}` (not in the repo)")
    if info:
        L.append(f"- Collected: {info.get('started_utc')} to {info.get('finished_utc')} UTC "
                 f"({info.get('requests_made')} requests)")
        if info.get("snapshot"):
            L.append("- **Snapshot:** the study window was not over when this was "
                     "collected, so the data stops early.")
    L.append(f"- Window covered: {win_start} to {win_end} "
             f"({(win_end - win_start).days + 1} days, UTC dates)")
    L.append(f"- Candidate pages: {len(cands)}\n")

    L.append("## What the cleaning did\n")
    L.append(f"1. Read {totals['raw_revisions']} raw revisions. Dropped "
             f"{totals['duplicates']} duplicate revision IDs and "
             f"{totals['outside_window']} revisions outside the window. "
             f"Kept **{totals['kept']} edits**.")
    L.append("2. Replaced every username, IP and temporary-account name with an "
             "editor type and a 12-character salted hash. Dropped user IDs.")
    L.append("3. Replaced each edit comment with a yes/no `event_keyword` flag, "
             "then dropped the comment.")
    L.append("4. Computed `size_delta` from the previous revision (including the "
             "last revision before the window).")
    L.append(f"5. Built one row per page per day ({len(day_rows)} rows = "
             f"{len(cands)} pages x {len(day_rows) // max(len(cands), 1)} days). "
             f"Filled {totals['zero_filled_view_days']} missing page-view days with "
             "0, because the Pageviews API leaves out days with no views. Days "
             "when the page was missing or only a redirect get a blank `views` "
             "and `article_live = False`.")
    L.append("6. Replayed each page's protection log to get the edit-protection "
             "level on every day.")
    L.append("7. Checked that the daily edit counts add up to the edits table "
             "(they do; the script stops if not).\n")

    L.append("## Result\n")
    L.append("| Table | Rows | In repo? |")
    L.append("| --- | --- | --- |")
    L.append(f"| edits_{cycle} | {len(edit_rows)} | {config.SAMPLE_EDITS}-row sample |")
    L.append(f"| page_days_{cycle} | {len(day_rows)} | {config.SAMPLE_PAGE_DAYS}-row sample |")
    L.append(f"| protection_{cycle} | {len(prot_rows)} | full |")
    L.append(f"| pages_{cycle} | {len(cands)} | full |\n")
    L.append("Edits by period: " + ", ".join(
        f"{p or 'none'} {by_period[p]}" for p in ("baseline", "campaign", "post")))
    L.append("\nEdits by editor type: " + ", ".join(
        f"{t} {n}" for t, n in by_type.most_common()) + "\n")

    L.append("## Per page\n")
    L.append("| Page | Status (edits / views) | Raw | Dup | Outside | Kept "
             "| View days returned | Zero-filled | Days live | Days protected "
             "| Protect events |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for p in log:
        L.append(f"| {p['title']} | {p['rev_status']} / {p['pv_status']} | {p['raw']} "
                 f"| {p['dup']} | {p['out']} | {p['kept']} | {p['pv_days']} "
                 f"| {p['zero_filled']} | {p['live_days']} | {p['protected_days']} "
                 f"| {p['prot_events']} |")

    n_days = len(day_rows) // max(len(cands), 1)
    warn = []
    for p in log:
        if p["errors"]:
            warn.append(f"- {p['title']}: API error {p['errors']}")
        if p["rev_status"] != 200:
            warn.append(f"- {p['title']}: revisions request returned {p['rev_status']}")
        if p["live_days"] < n_days:
            warn.append(f"- {p['title']}: an article on only {p['live_days']} of "
                        f"{n_days} days (created or redirected during the window). "
                        "Use live days, not calendar days, for its rates.")
        if p["protected_days"]:
            warn.append(f"- {p['title']}: edit-protected on {p['protected_days']} days. "
                        "Temporary-account and IP editors could not edit then.")
    L.append("\n## Things to watch\n")
    L.extend(warn or ["- None."])

    path = os.path.join(config.DOCS_DIR, f"cleaning_log_{cycle}.md")
    os.makedirs(config.DOCS_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"  wrote {os.path.relpath(path, config.ROOT)}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2026)
