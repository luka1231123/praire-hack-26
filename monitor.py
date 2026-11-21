"""Live monitor for Bluesky. Free, no key.

Usage:  uv run monitor.py

- Reads the Bluesky Jetstream firehose (all new posts and reposts).
- Writes one Parquet file per minute to data/live/, same columns as ingest.py.
- Deletes files older than WINDOW_H hours (rolling window).
- Every DETECT_EVERY seconds runs detect.py on the window and writes data/live_report.html and data/site/.
A repost is stored as a post with the item "rt:<post uri>", so shared amplification counts as a shared item.
"""
import asyncio
import glob
import json
import os
import time
import traceback

import pyarrow as pa
import pyarrow.parquet as pq
import websockets

import detect
import osint_site

URL = ("wss://jetstream2.us-east.bsky.network/subscribe"
       "?wantedCollections=app.bsky.feed.post&wantedCollections=app.bsky.feed.repost")
LIVE = "data/live"
WINDOW_H = int(os.environ.get("WINDOW_H", 24))  # hours of data to keep
DETECT_EVERY = 300
MIN_POSTS = 3   # posts+reposts a user needs inside the window to be scored

SCHEMA = pa.schema([("platform", pa.string()), ("post_id", pa.string()), ("user_id", pa.string()),
                    ("ts", pa.timestamp("us")), ("text", pa.string()), ("reply_to", pa.string()),
                    ("thread", pa.string()), ("label", pa.bool_()), ("items", pa.list_(pa.string()))])


def to_row(e):
    c = e.get("commit") or {}
    if e.get("kind") != "commit" or c.get("operation") != "create":
        return None
    r = c.get("record") or {}
    uri = f"at://{e['did']}/{c['collection']}/{c['rkey']}"
    row = dict(platform="bluesky", post_id=uri, user_id=e["did"], ts=e["time_us"],  # server time, not client createdAt
               text="", reply_to=None, thread=None, label=None, items=[])
    if c["collection"] == "app.bsky.feed.repost":
        row["items"] = ["rt:" + ((r.get("subject") or {}).get("uri") or "")]
        return row
    items = set()
    for f in r.get("facets") or []:
        for ft in f.get("features") or []:
            t = ft.get("$type", "")
            if t.endswith("#link") and ft.get("uri"):
                items.add("url:" + ft["uri"].split("://", 1)[-1].split("?")[0].lower())
            elif t.endswith("#tag") and ft.get("tag"):
                items.add("#" + ft["tag"].lower())
            elif t.endswith("#mention") and ft.get("did"):
                items.add("@" + ft["did"])
    ext = ((r.get("embed") or {}).get("external") or {}).get("uri")
    if ext:
        items.add("url:" + ext.split("://", 1)[-1].split("?")[0].lower())
    reply = r.get("reply") or {}
    row.update(text=r.get("text", ""), items=sorted(items),
               reply_to=(reply.get("parent") or {}).get("uri"), thread=(reply.get("root") or {}).get("uri"))
    return row


def flush(buf):
    if buf:
        pq.write_table(pa.Table.from_pylist(buf, schema=SCHEMA), f"{LIVE}/{int(time.time())}.parquet")
    cutoff = time.time() - WINDOW_H * 3600
    for f in glob.glob(f"{LIVE}/*.parquet"):
        if int(os.path.basename(f).split(".")[0]) < cutoff:
            os.remove(f)


async def stream():
    buf, last, n = [], time.time(), 0
    while True:
        try:
            async with websockets.connect(URL, max_size=2**22, open_timeout=15) as ws:
                async for msg in ws:
                    row = to_row(json.loads(msg))
                    if row:
                        buf.append(row)
                        n += 1
                    if time.time() - last >= 60:
                        flush(buf)
                        print(f"{time.strftime('%H:%M')} +{len(buf)} posts ({n} total)", flush=True)
                        buf, last = [], time.time()
        except Exception as ex:  # network drop: reconnect after a short wait
            print("stream error, reconnecting:", ex, flush=True)
            await asyncio.sleep(5)


def run_detect():
    con, cl, member = detect.detect(f"{LIVE}/*.parquet", MIN_POSTS)
    cl = detect.tags(cl, member)  # account facts from the public API
    kd = detect.kinds(con, cl)
    detect.report(con, cl, member, out="data/live_report.html",
                  platform_url="https://bsky.app/profile/{}", refresh=60, kd=kd)
    osint_site.write(con, cl, member, "bluesky", f"{LIVE}/*.parquet", kd=kd)  # data/site/, the investigator site
    print(f"{time.strftime('%H:%M')} report: {len(cl)} groups -> data/live_report.html", flush=True)


async def detect_loop():
    while True:
        await asyncio.sleep(DETECT_EVERY)
        try:
            await asyncio.to_thread(run_detect)
        except Exception:
            traceback.print_exc()


async def main():
    os.makedirs(LIVE, exist_ok=True)
    await asyncio.gather(stream(), detect_loop())


if __name__ == "__main__":
    asyncio.run(main())
