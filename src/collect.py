"""Download raw data for one election cycle and save it as JSON.

Run (from the repo root):
    python src/collect.py 2022            pilot cycle (finished)
    python src/collect.py 2026            2026 cycle
    python src/collect.py 2026 --force    re-download files that already exist

For every candidate page in data/candidates_<cycle>.csv it saves:
    revisions/<title>.json   every edit in the study window, plus the last
                             edit before the window (to get the starting size)
    pageviews/<title>.json   daily page views by people (not bots)
    protection/<title>.json  the page's protection log, up to the window end
and once per cycle:
    bot_flags.json           {username: is a bot?} for registered editors
    collection_info.json     when it ran, what window it covered, counts

Output goes to data/raw/<cycle>/. If the study window is not over yet, the end
date is clipped to yesterday and the files go to
data/raw/<cycle>_snapshot_<today>/ instead.

data/raw/ is git-ignored: it holds usernames, IPs and edit comments, which
never leave this computer. clean.py turns it into de-identified tables.
"""

import csv
import datetime as dt
import json
import os
import sys
import urllib.parse

import config
import wiki_http
from wiki_http import get_json


def iso(day, end=False):
    return f"{day.isoformat()}T{'23:59:59' if end else '00:00:00'}Z"


def safe(title):
    """File-name-safe version of a page title (also used in the pageviews URL)."""
    return urllib.parse.quote(title, safe="")


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)


def first_page(data):
    """Return the one page in an Action API answer, or {} if there is none."""
    if not data or "query" not in data:
        return {}
    pages = data["query"].get("pages", [])
    return pages[0] if pages else {}


def collect_revisions(title, start, end):
    """All revisions in [start, end] plus the one just before start.

    No `redirects` parameter: if the title is now a redirect (Joe O'Dea in
    2022), we still get that title's own history, including the article
    revisions from before it was turned into a redirect.
    """
    revs, errors = [], []
    params = {
        "action": "query", "prop": "revisions", "titles": title,
        "rvprop": "ids|timestamp|user|userid|size|tags|comment|flags",
        "rvlimit": "max", "rvdir": "older",
        "rvstart": iso(end, end=True), "rvend": iso(start),
    }
    status = None
    while True:
        status, data, _ = get_json(config.ACTION_API, params)
        if data and "error" in data:
            errors.append(data["error"])
            break
        page = first_page(data)
        revs.extend(page.get("revisions", []))
        if not data or "continue" not in data:
            break
        params.update(data["continue"])

    # one earlier revision, so the first edit in the window has a size change
    # and we know whether the page was an article or a redirect at the start
    _, prev, _ = get_json(config.ACTION_API, {
        "action": "query", "prop": "revisions", "titles": title,
        "rvprop": "ids|timestamp|size", "rvlimit": 1, "rvdir": "older",
        "rvstart": iso(start - dt.timedelta(days=1), end=True),
    })
    before = first_page(prev).get("revisions", [])
    return {"title": title, "status": status, "errors": errors,
            "page_missing": bool(first_page(data).get("missing")) if data else None,
            "revisions": revs,
            "revision_before_window": before[0] if before else None}


def collect_pageviews(title, start, end):
    url = config.PAGEVIEWS_API.format(
        title=safe(title), start=start.strftime("%Y%m%d"),
        end=end.strftime("%Y%m%d"))
    status, data, final = get_json(url)
    # 404 here means "no views recorded", e.g. the page did not exist yet
    return {"title": title, "status": status, "url": final,
            "items": (data or {}).get("items", [])}


def collect_protection(title, start, end):
    """Every protection log event for the title up to the window end.

    The full history (not just the window) is needed to know whether the page
    was already protected on the first day. Admin usernames and log comments
    are not requested (no `user` or `comment` in leprop).
    """
    events = []
    params = {
        "action": "query", "list": "logevents", "letype": "protect",
        "letitle": title, "lelimit": "max", "ledir": "newer",
        "leend": iso(end, end=True),
        "leprop": "ids|title|type|timestamp|details",
    }
    status = None
    while True:
        status, data, _ = get_json(config.ACTION_API, params)
        if not data or "query" not in data:
            break
        events.extend(data["query"].get("logevents", []))
        if "continue" not in data:
            break
        params.update(data["continue"])
    return {"title": title, "status": status, "events": events}


def collect_bot_flags(names):
    """Return {username: is_bot} using list=users, 50 names per request."""
    flags = {}
    names = sorted(names)
    for i in range(0, len(names), 50):
        batch = names[i:i + 50]
        _, data, _ = get_json(config.ACTION_API, {
            "action": "query", "list": "users", "ususers": "|".join(batch),
            "usprop": "groups",
        })
        for u in (data or {}).get("query", {}).get("users", []):
            flags[u["name"]] = "bot" in u.get("groups", [])
    return flags


def load_titles(cycle):
    with open(config.CYCLES[cycle]["candidates_file"], newline="",
              encoding="utf-8") as f:
        return [r["title"] for r in csv.DictReader(f) if r["title"].strip()]


def main(cycle, force=False):
    config.check_contact()
    start, end = config.window_for(cycle)
    today = dt.datetime.now(dt.timezone.utc).date()
    snapshot = end >= today
    if snapshot:
        end = today - dt.timedelta(days=1)
        base = os.path.join(config.RAW_DIR, f"{cycle}_snapshot_{today}")
        print(f"Window not finished; saving a snapshot up to {end} in {base}")
    else:
        base = os.path.join(config.RAW_DIR, str(cycle))

    started = dt.datetime.now(dt.timezone.utc)
    titles = load_titles(cycle)
    registered = set()
    counts = {}
    for n, title in enumerate(titles, 1):
        print(f"[{n}/{len(titles)}] {title}")
        counts[title] = {}
        jobs = [("revisions", collect_revisions),
                ("pageviews", collect_pageviews),
                ("protection", collect_protection)]
        for kind, fn in jobs:
            path = os.path.join(base, kind, safe(title) + ".json")
            if os.path.exists(path) and not force:
                with open(path, encoding="utf-8") as f:
                    obj = json.load(f)
                print(f"   {kind}: already have it")
            else:
                obj = fn(title, start, end)
                obj["saved_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(
                    timespec="seconds")
                save(path, obj)
            count = len(obj.get("revisions", obj.get("items",
                                obj.get("events", []))))
            counts[title][kind] = {"status": obj["status"], "records": count,
                                   "saved_utc": obj.get("saved_utc", "")}
            print(f"   {kind}: status {obj['status']}, {count} records")
            if kind == "revisions":
                for r in obj["revisions"]:
                    u = r.get("user", "")
                    if u and not r.get("anon") and not r.get("temp") \
                            and not u.startswith("~"):
                        registered.add(u)

    print(f"Checking bot flags for {len(registered)} registered editors")
    save(os.path.join(base, "bot_flags.json"), collect_bot_flags(registered))

    finished = dt.datetime.now(dt.timezone.utc)
    info = {
        "cycle": cycle,
        "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": finished.isoformat(timespec="seconds"),
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "snapshot": snapshot,
        "user_agent_product": f"{config.PROJECT_NAME}/{config.PROJECT_VERSION}",
        "requests_made": wiki_http.REQUEST_COUNT,
        "pages": counts,
    }
    save(os.path.join(base, "collection_info.json"), info)
    print(f"done: {base} ({wiki_http.REQUEST_COUNT} requests)")


if __name__ == "__main__":
    cyc = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 2026
    main(cyc, force="--force" in sys.argv)
