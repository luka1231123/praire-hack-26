"""Download past Bluesky posts and reposts of chosen accounts. Free, no login.

Usage:  uv run backfill.py 2026-10-27 2026-11-10 [max_accounts]

Seed accounts come from the live data (data/live/): users who posted about elections, US politics or
Iowa, plus the authors they reposted. For each account, the public author feed is read back to the
start date. Output: data/backfill/<start>_<end>_NNN.parquet (one file per 100 accounts), same columns as monitor.py.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from monitor import SCHEMA

TERMS = (r"(?i)\b(election|elections|midterms?|ballots?|voters?|voting|polls?|gop|democrats?|republicans?|senate|"
         r"congress|governor|maga|trump|vance|recount|turnout|iowa|iowans?|des moines|cedar rapids|grassley|reynolds|#iapolitics)\b")
API = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"
MAX_PAGES = 300  # 100 items per page; very active accounts post about 100 items per 1.5 hours


def seeds(limit):
    con = duckdb.connect()
    pol = [u for (u,) in con.sql(f"""select user_id from 'data/live/*.parquet' where regexp_matches(text, '{TERMS}')
                                     group by 1 order by count(*) desc""").fetchall()]
    rt = [u for (u,) in con.sql(f"""select split_part(substr(it, 9), '/', 1) did from
             (select unnest(items) it from 'data/live/*.parquet' where user_id in (select unnest(?)))
             where starts_with(it, 'rt:at://') group by 1 having count(*) >= 2 order by count(*) desc""", params=[pol]).fetchall()]
    return list(dict.fromkeys(pol + rt))[:limit]


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):  # deleted or suspended account
                return None
            time.sleep(2 ** i * 3)    # 429 rate limit or server error: back off
        except Exception:
            time.sleep(2 ** i)
    return None


def items_of(rec):
    items = set()
    for f in rec.get("facets") or []:
        for ft in f.get("features") or []:
            t = ft.get("$type", "")
            if t.endswith("#link") and ft.get("uri"):
                items.add("url:" + ft["uri"].split("://", 1)[-1].split("?")[0].lower())
            elif t.endswith("#tag") and ft.get("tag"):
                items.add("#" + ft["tag"].lower())
            elif t.endswith("#mention") and ft.get("did"):
                items.add("@" + ft["did"])
    ext = ((rec.get("embed") or {}).get("external") or {}).get("uri")
    if ext:
        items.add("url:" + ext.split("://", 1)[-1].split("?")[0].lower())
    return sorted(items)


def ts_us(iso):
    return int(time.mktime(time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone) * 1_000_000


def account(did, start, end):
    rows, cursor = [], None
    for _ in range(MAX_PAGES):
        q = {"actor": did, "limit": 100, "filter": "posts_with_replies"}
        if cursor:
            q["cursor"] = cursor
        page = get(API + "?" + urllib.parse.urlencode(q))
        if not page or not page.get("feed"):
            break
        oldest = None
        for it in page["feed"]:
            post, reason = it["post"], it.get("reason") or {}
            if reason.get("$type", "").endswith("reasonRepost"):
                if (reason.get("by") or {}).get("did") != did:
                    continue
                t = reason["indexedAt"]
                row = dict(post_id="repost:" + post["uri"], text="", reply_to=None, thread=None, items=["rt:" + post["uri"]])
            elif post["author"]["did"] == did:
                t, rec = post["indexedAt"], post["record"]  # server time, not client createdAt
                reply = rec.get("reply") or {}
                row = dict(post_id=post["uri"], text=rec.get("text", ""), items=items_of(rec),
                           reply_to=(reply.get("parent") or {}).get("uri"), thread=(reply.get("root") or {}).get("uri"))
            else:
                continue
            oldest = t
            if start <= t[:10] <= end:
                row.update(platform="bluesky", user_id=did, ts=ts_us(t), label=None)
                rows.append(row)
        cursor = page.get("cursor")
        if not cursor or (oldest and oldest[:10] < start):
            break
    return rows


if __name__ == "__main__":
    start, end = sys.argv[1], sys.argv[2]
    dids = seeds(int(sys.argv[3]) if len(sys.argv) > 3 else 3000)
    print(len(dids), "seed accounts", flush=True)
    os.makedirs("data/backfill", exist_ok=True)
    rows, total, part, t0 = [], 0, 0, time.time()
    with ThreadPoolExecutor(8) as pool:
        for i, r in enumerate(pool.map(lambda d: account(d, start, end), dids), 1):
            rows += r
            if i % 100 == 0 or i == len(dids):  # save every 100 accounts, so a crash loses little
                pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), f"data/backfill/{start}_{end}_{part:03d}.parquet")
                total, part, rows = total + len(rows), part + 1, []
                print(f"{i}/{len(dids)} accounts, {total} posts, {time.time() - t0:.0f} s", flush=True)
