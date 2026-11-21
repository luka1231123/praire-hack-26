"""Public Bluesky account facts, cached in data/profiles.parquet. Free, no login."""
import json
import os
import time
import urllib.parse
import urllib.request

import pandas as pd

CACHE = "data/profiles.parquet"
API = "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfiles"
MAX_AGE_S = 24 * 3600


def get(dids):
    """Return {did: {handle, name, bio, created, followers, posts}} and refresh old or missing entries."""
    cache = pd.read_parquet(CACHE) if os.path.exists(CACHE) else pd.DataFrame(columns=["did", "fetched"])
    fresh = cache[cache.fetched > time.time() - MAX_AGE_S]
    need = [d for d in dict.fromkeys(dids) if d not in set(fresh.did)]
    rows = []
    for i in range(0, len(need), 25):
        url = API + "?" + urllib.parse.urlencode([("actors", d) for d in need[i:i + 25]])
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                for p in json.load(r)["profiles"]:
                    rows.append(dict(did=p["did"], handle=p.get("handle"), name=(p.get("displayName") or "").strip(),
                                     bio=(p.get("description") or "").strip(), created=(p.get("createdAt") or "")[:10],
                                     followers=p.get("followersCount", 0), posts=p.get("postsCount", 0), fetched=time.time()))
        except Exception as ex:  # skip a failed batch; it is fetched again next run
            print("profiles: batch failed:", ex)
    if rows:
        new = pd.DataFrame(rows)
        cache = pd.concat([cache[~cache.did.isin(new.did)], new], ignore_index=True)
        cache.to_parquet(CACHE)
    return {r.did: r._asdict() for r in cache[cache.did.isin(dids)].itertuples(index=False)}
