#!/usr/bin/env python
"""Probe NSW Planning Portal: onlineDA SPA + CKAN opendata."""
import json
import re
import sys
import time

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*", "Accept-Language": "en-AU,en;q=0.9"})

def get(url, **kw):
    try:
        r = S.get(url, timeout=30, **kw)
        print(f"\n=== GET {url} -> {r.status_code} ({len(r.content)} bytes)")
        return r
    except Exception as e:
        print(f"\n=== GET {url} -> ERROR {e}")
        return None

# 1. Home page
r = get("https://www.planningportal.nsw.gov.au/")
if r:
    m = r.text[:5000]
    print(m[:2000])

# 2. onlineDA SPA page
r = get("https://www.planningportal.nsw.gov.au/onlineDA")
if r is not None:
    scripts = re.findall(r'src="([^"]+\.js[^"]*)"', r.text)
    print("\nSCRIPTS:", scripts[:20])
    # also look for inline fetch patterns
    fetches = re.findall(r'(?:fetch|axios|XMLHttpRequest|\.ajax)\s*[\(\s]*[\'" ]([^\'"\)\s,;]+)', r.text)
    print("INLINE FETCH HINTS:", fetches[:20])
    # look for any api-like strings
    apis = re.findall(r'[\'"/][a-zA-Z0-9_\-/]*api[a-zA-Z0-9_\-/.]*', r.text, re.I)
    print("API-LIKE STRINGS:", sorted(set(apis))[:40])
    with open("/tmp/onlineDA.html", "w") as f:
        f.write(r.text)

# 3. CKAN opendata
get("https://www.planningportal.nsw.gov.au/opendata/api/3/action/site_read")
get("https://www.planningportal.nsw.gov.au/opendata/api/3/action/package_list?limit=100")
