"""Shared settings for every script in this project.

Your contact email is NOT stored here, because this repo is public. Put it in
a file called `.env` in the repo root (it is git-ignored):

    COEDITS_CONTACT=you@example.edu

Wikimedia asks every client to send a User-Agent that says who you are and
how to reach you, so the scripts refuse to run until this is set.
"""

import datetime as dt
import os

# ---------------------------------------------------------------------------
# Paths (everything is relative to the repo root, so scripts work from any
# folder: `python src/collect.py 2022` or `cd src && python collect.py 2022`)
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")        # git-ignored: has usernames
CLEAN_DIR = os.path.join(DATA_DIR, "clean")    # git-ignored: full clean tables
SAMPLE_DIR = os.path.join(DATA_DIR, "sample")  # committed: small samples
PAGE_CHECK_DIR = DATA_DIR                      # check_pages.py writes here
DOCS_DIR = os.path.join(ROOT, "docs")          # cleaning logs go here
SALT_FILE = os.path.join(ROOT, "salt.txt")     # git-ignored


def _read_env_file():
    """Load KEY=value lines from ROOT/.env into os.environ (if not set)."""
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"\''))


_read_env_file()

# ---------------------------------------------------------------------------
# Who is asking (Wikimedia User-Agent policy)
# ---------------------------------------------------------------------------
CONTACT = os.environ.get("COEDITS_CONTACT", "")
PROJECT_NAME = "COElectionEditsBot"
PROJECT_VERSION = "0.2"

# wiki_http.py adds the requests version, e.g. "python-requests/2.34.2"
USER_AGENT = (
    f"{PROJECT_NAME}/{PROJECT_VERSION} "
    f"({CONTACT}; student course project, read-only)"
)

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
ACTION_API = "https://en.wikipedia.org/w/api.php"
PAGEVIEWS_API = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "en.wikipedia/all-access/user/{title}/daily/{start}/{end}"
)

# ---------------------------------------------------------------------------
# Politeness
# ---------------------------------------------------------------------------
PAUSE_SECONDS = 1.0       # wait after every request; requests are never parallel
MAXLAG = 5                # Action API: back off when database replicas lag
MAX_RETRIES = 5
TIMEOUT_SECONDS = 30

# ---------------------------------------------------------------------------
# Study windows (inclusive dates, UTC)
#   baseline  = from two weeks after the primary to the day before the campaign
#   campaign  = the final 7 weeks, ending on election day
#   post      = the two weeks after election day
# ---------------------------------------------------------------------------
CYCLES = {
    2026: {
        "primary": dt.date(2026, 6, 30),
        "election": dt.date(2026, 11, 3),
        "baseline": (dt.date(2026, 7, 14), dt.date(2026, 9, 14)),
        "campaign": (dt.date(2026, 9, 15), dt.date(2026, 11, 3)),
        "post": (dt.date(2026, 11, 4), dt.date(2026, 11, 17)),
        "candidates_file": os.path.join(DATA_DIR, "candidates_2026.csv"),
    },
    2022: {
        "primary": dt.date(2022, 6, 28),
        "election": dt.date(2022, 11, 8),
        "baseline": (dt.date(2022, 7, 12), dt.date(2022, 9, 19)),
        "campaign": (dt.date(2022, 9, 20), dt.date(2022, 11, 8)),
        "post": (dt.date(2022, 11, 9), dt.date(2022, 11, 22)),
        "candidates_file": os.path.join(DATA_DIR, "candidates_2022.csv"),
    },
}

# ---------------------------------------------------------------------------
# What counts as a competitive race (Cook Political Report labels).
# Default: Likely or closer, which makes CO-3, CO-5 and CO-8 competitive in
# 2026. Use {"Tossup", "Lean D", "Lean R"} for the strict version.
# ---------------------------------------------------------------------------
COMPETITIVE_RATINGS = {"Tossup", "Lean D", "Lean R", "Likely D", "Likely R"}

# Edit-comment keywords counted as "event-linked" edits (case-insensitive).
# The comment itself is never saved in the clean data, only this yes/no flag.
EVENT_KEYWORDS = ["poll", "endorse", "debate", " ad ", "advert", "fundrais",
                  "result", "won", "defeat", "elected", "concede"]

# A revision smaller than this many bytes is treated as a redirect, not an
# article (a redirect page is one line, usually under 100 bytes).
REDIRECT_MAX_BYTES = 300

# Sample sizes for the committed sample files (fixed seed = same rows each run)
SAMPLE_SEED = 2026
SAMPLE_EDITS = 50
SAMPLE_PAGE_DAYS = 40


def window_for(cycle):
    """Full collection range for a cycle: baseline start to post end."""
    c = CYCLES[cycle]
    return c["baseline"][0], c["post"][1]


def period_of(day, cycle):
    """Return 'baseline', 'campaign', 'post' or '' for a date."""
    c = CYCLES[cycle]
    for name in ("baseline", "campaign", "post"):
        start, end = c[name]
        if start <= day <= end:
            return name
    return ""


def check_contact():
    if "@" not in CONTACT and "http" not in CONTACT:
        raise SystemExit(
            "No contact set. Create a file called .env in the repo root with\n"
            "    COEDITS_CONTACT=your_email@colorado.edu\n"
            "(see .env.example). Wikimedia's User-Agent policy requires it."
        )
