"""Confirm each candidate page exists and is the right kind of page.

For every title in the cycle's candidate list it reports: does the page
exist, is it a redirect (e.g. to the race article) or a disambiguation page,
when it was created, and whether it existed for the whole baseline.

Run:  python check_pages.py 2026      (or 2022)
Out:  data/page_check_<cycle>.csv   (analyze.py reads the creation dates)
"""

import csv
import datetime as dt
import os
import sys

import config
from wiki_http import get_json


def load_titles(cycle):
    with open(config.CYCLES[cycle]["candidates_file"], newline="",
              encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if r["title"].strip()]


def main(cycle):
    config.check_contact()
    rows = load_titles(cycle)
    titles = [r["title"] for r in rows]
    baseline_start = config.CYCLES[cycle]["baseline"][0]

    status, data, _ = get_json(config.ACTION_API, {
        "action": "query", "titles": "|".join(titles),
        "prop": "info|pageprops", "ppprop": "disambiguation",
        "inprop": "protection",
        "redirects": 1,  # without this the API never fills q["redirects"]
    })
    print("info query status:", status)
    q = data["query"]
    norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
    redir = {r["from"]: r["to"] for r in q.get("redirects", [])}
    pages = {p["title"]: p for p in q["pages"]}

    out = []
    for r in rows:
        t = norm.get(r["title"], r["title"].replace("_", " "))
        target = redir.get(t, t)
        p = pages.get(target, {})
        exists = "missing" not in p and bool(p)
        rec = {
            "candidate": r["candidate"], "race": r["race"], "title": r["title"],
            "exists": exists, "redirects_to": redir.get(t, ""),
            "disambiguation": "disambiguation" in p.get("pageprops", {}),
            "pageid": p.get("pageid", ""),
            "protection": ";".join(f'{x["type"]}={x["level"]}'
                                   for x in p.get("protection", [])),
            "created": "", "covers_baseline": "",
        }
        # A redirect's target is a different page (often the race article), so
        # its creation date says nothing about the candidate page. Set an
        # `article_from` date in the candidates file by hand instead.
        if exists and not rec["redirects_to"]:
            s, d, _ = get_json(config.ACTION_API, {
                "action": "query", "prop": "revisions", "pageids": p["pageid"],
                "rvprop": "timestamp", "rvlimit": 1, "rvdir": "newer",
            })
            ts = d["query"]["pages"][0]["revisions"][0]["timestamp"]
            created = dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
            rec["created"] = created.isoformat()
            rec["covers_baseline"] = created <= baseline_start
        out.append(rec)
        flag = ""
        if not exists:
            flag = "  <-- MISSING"
        elif rec["redirects_to"]:
            flag = f"  <-- REDIRECT to {rec['redirects_to']}"
        elif rec["disambiguation"]:
            flag = "  <-- DISAMBIGUATION"
        elif rec["covers_baseline"] is False:
            flag = "  <-- created after baseline start"
        print(f"{r['candidate']:<22} {r['title']:<24} created {rec['created']}{flag}")

    os.makedirs(config.PAGE_CHECK_DIR, exist_ok=True)
    path = os.path.join(config.PAGE_CHECK_DIR, f"page_check_{cycle}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print("wrote", path)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2026)
