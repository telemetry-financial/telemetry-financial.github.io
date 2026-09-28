#!/usr/bin/env python3
"""
fetch_tsp.py  --  runs inside GitHub Actions (on GitHub's servers, where there
is NO browser CORS limit). Pulls the public TSP fund share-price feed and writes
prices.json. GitHub then serves that file with permissive CORS headers, so the
Telemetry Financial app can read it from anywhere -- even a double-clicked
(file://) copy -- with no proxies.

No login, no passwords: TSP share prices are public data.
"""
import datetime as dt
import json
import os
import sys
import urllib.request
import urllib.error

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prices.json")

FUND_KEYS = ["G", "F", "C", "S", "I", "LIncome",
             "L2030", "L2035", "L2040", "L2045", "L2050",
             "L2055", "L2060", "L2065", "L2070", "L2075"]

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Accept": "text/csv,text/plain,*/*",
    "Referer": "https://www.tsp.gov/share-price-history/",
}


def endpoints():
    end = dt.date.today()
    start = end - dt.timedelta(days=20)
    return [
        "https://www.tsp.gov/data/fund-price-history.csv",
        ("https://www.tsp.gov/data/fund-price-history.csv"
         "?startdate=%s&enddate=%s&Lfunds=1&InvFunds=1&download=1"
         % (start.isoformat(), end.isoformat())),
        ("https://secure.tsp.gov/components/CORS/getSharePricesRaw.html"
         "?startdate=%s&enddate=%s&Lfunds=1&InvFunds=1&download=1"
         % (start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))),
    ]


def fund_key(name):
    u = str(name).upper().replace(" ", "").replace("FUND", "")
    if u in ("G", "F", "C", "S", "I"):
        return u
    if u in ("LINCOME", "LINC"):
        return "LIncome"
    if len(u) == 5 and u.startswith("L20") and u[3:].isdigit():
        return u
    return None


def parse_date(s):
    """Parse a TSP date cell into a date for comparison. Handles ISO
    (YYYY-MM-DD), US (MM/DD/YYYY), and 'Mon DD, YYYY'. Returns date.min on
    failure so it never wins the 'most recent' pick."""
    s = (s or "").strip().strip('"')
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y", "%B %d, %Y", "%m-%d-%Y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return dt.date.min


def parse_csv(text):
    """Return (prices, date_str) for the MOST RECENT row. The TSP feed is not
    guaranteed to be sorted oldest-last, so we pick by max date rather than by
    position (a bottom/top row could be the oldest day in the history)."""
    lines = [ln for ln in text.replace("\r", "").split("\n") if ln.strip()]
    if len(lines) < 2:
        return None, None
    hdr = [h.strip().strip('"') for h in lines[0].split(",")]
    best = None  # (date_obj, date_str, prices)
    for row in lines[1:]:
        cells = [c.strip().strip('"') for c in row.split(",")]
        if not cells:
            continue
        prices = {}
        for i, h in enumerate(hdr):
            if i == 0 or i >= len(cells):
                continue
            k = fund_key(h)
            if k is None:
                continue
            try:
                prices[k] = round(float(cells[i].replace("$", "").replace(",", "")), 4)
            except ValueError:
                pass
        if not prices:
            continue
        dstr = cells[0]
        dobj = parse_date(dstr)
        if best is None or dobj > best[0]:
            best = (dobj, dstr, prices)
    if best:
        return best[2], best[1]
    return None, None


def fetch():
    last = None
    for url in endpoints():
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                text = r.read().decode("utf-8", "replace")
            prices, date = parse_csv(text)
            if prices:
                return prices, date, url
            last = "no parseable rows from " + url
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            last = "%s -> %s" % (url, e)
    raise RuntimeError(last or "all endpoints failed")


def main():
    prices, date, url = fetch()
    out = {
        "as_of": date or dt.date.today().isoformat(),
        "updated_utc": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "source": "tsp.gov public share-price feed",
        "prices": {k: prices.get(k) for k in FUND_KEYS},
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    got = [k for k in FUND_KEYS if prices.get(k) is not None]
    print("Wrote %s  (as_of %s, %d/%d funds) from %s"
          % (OUT, out["as_of"], len(got), len(FUND_KEYS), url.split("?")[0]))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(1)
