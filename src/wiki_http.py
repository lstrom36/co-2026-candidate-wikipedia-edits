"""One polite HTTP helper used by every script that talks to Wikimedia.

- Sends the project User-Agent (with contact info) on every request.
- Makes one request at a time and pauses PAUSE_SECONDS after each.
- Adds maxlag to Action API calls and backs off when the servers are busy.
- Honors Retry-After on HTTP 429 and retries 5xx errors a few times.
"""

import time

import requests

import config

_session = requests.Session()
_session.headers.update({
    "User-Agent": f"{config.USER_AGENT} python-requests/{requests.__version__}",
    "Accept-Encoding": "gzip",
})

REQUEST_COUNT = 0  # collect.py reports this at the end


def get_json(url, params=None):
    """GET a URL and return (status_code, json_or_None, final_url)."""
    global REQUEST_COUNT
    params = dict(params or {})
    if url == config.ACTION_API:
        params.setdefault("format", "json")
        params.setdefault("formatversion", "2")
        params.setdefault("maxlag", config.MAXLAG)

    for attempt in range(1, config.MAX_RETRIES + 1):
        resp = _session.get(url, params=params, timeout=config.TIMEOUT_SECONDS)
        REQUEST_COUNT += 1
        time.sleep(config.PAUSE_SECONDS)

        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 30))
            print(f"  429 rate limited; waiting {wait}s (attempt {attempt})")
            time.sleep(wait)
            continue
        if 500 <= resp.status_code < 600:
            wait = 5 * attempt
            print(f"  {resp.status_code} server error; waiting {wait}s")
            time.sleep(wait)
            continue

        try:
            data = resp.json()
        except ValueError:
            return resp.status_code, None, resp.url

        # The Action API reports maxlag as an error inside a 200 response
        if isinstance(data, dict) and data.get("error", {}).get("code") == "maxlag":
            wait = int(resp.headers.get("Retry-After", 5))
            print(f"  maxlag; waiting {wait}s")
            time.sleep(wait)
            continue

        return resp.status_code, data, resp.url

    raise RuntimeError(f"Gave up after {config.MAX_RETRIES} attempts: {url}")
