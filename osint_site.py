"""Write the investigator site: one page per group, with the evidence, real post links, search and exports.

Usage:  uv run osint_site.py NAME [posts.parquet glob] [min_posts] [resolution] [top_groups]
  uv run osint_site.py bluesky "data/live/*.parquet" 3
  uv run osint_site.py iowa "data/backfill/*.parquet" 5
  uv run osint_site.py x data/posts_x.parquet 20 5

Output goes to data/site/ (not in git: it holds real account IDs). Open data/site/index.html.
Each run writes data/site/NAME.js and keeps the other datasets. monitor.py calls write() every 5 min.
The page itself is osint/index.html, copied next to the data.
"""
import datetime as dt
import glob
import json
import os
import shutil
import sys

import numpy as np
import pandas as pd

import detect

OUT = "data/site"
TOP = 100            # groups written
MAX_KEYS = 300       # shared keys per group (for search and pivots)
POST_KEYS = 25       # of these, keys that also list their posts
POSTS_PER_KEY = 20
MAX_TIMELINE = 3000  # posts per group on the timeline
MAX_EDGES = 1000     # account pairs per group


def q(con, sql):
    return con.sql(sql).df()


def write(con, cl, member, name, src="", top=TOP, kd=None):
    platform = con.sql("select any_value(platform) from p").fetchall()[0][0]
    cols = set(con.sql("select * from p limit 0").columns)
    n_groups = len(cl)
    cl = cl.head(top)
    rank = {c: i + 1 for i, c in enumerate(cl.index)}
    gm = pd.DataFrame([(u, rank[c]) for u, c in member.items() if c in rank], columns=["user_id", "g"])
    con.register("gm", gm)

    # every key that 2 or more members of the same group share
    con.sql("""create or replace temp table gk as
               select g, kind, key, count(*) users, any_value(sample) sample, min(t0) t0, max(t0) t1,
                      max(fan) fan from ev2 join gm using (user_id) group by all having count(*) >= 2""")
    con.sql(f"""create or replace temp table gk2 as select * from gk
                qualify row_number() over (partition by g order by users desc, kind = 'dup' desc, key) <= {MAX_KEYS}""")
    # the posts behind each key (members only)
    con.sql(f"""create or replace temp table evp as
      with n as (select p.*, gm.g, {detect.NORM} norm from p join gm using (user_id))
      select g, 'tgt' kind, coalesce(thread, '') || ':' || reply_to key, user_id, post_id, ts, text from n where reply_to is not null
      union all select g, 'item', unnest(items), user_id, post_id, ts, text from n
      union all select g, 'dup', md5(norm), user_id, post_id, ts, text from n where length(norm) >= 30""")
    posts = q(con, f"""with k as (select * from gk2 qualify row_number() over (partition by g order by users desc,
                                  kind = 'dup' desc, key) <= {POST_KEYS})
                       select e.g, e.kind, e.key, e.user_id, e.post_id, epoch(e.ts)::bigint ts, left(e.text, 500) text
                       from evp e semi join k using (g, kind, key)
                       qualify row_number() over (partition by e.g, e.kind, e.key order by e.ts) <= {POSTS_PER_KEY}""")
    keys = q(con, "select g, kind, key, users, fan, sample, epoch(t0)::bigint t0, epoch(t1)::bigint t1 from gk2")
    counts = q(con, "select g, kind, count(*) n from gk group by all")
    timeline = q(con, f"""with s as (select distinct e.post_id from evp e semi join gk using (g, kind, key))
        select gm.g, p.user_id, epoch(p.ts)::bigint ts, s.post_id is not null shared from p join gm using (user_id)
        left join s using (post_id)
        qualify row_number() over (partition by gm.g order by s.post_id is null, hash(p.post_id)) <= {MAX_TIMELINE}""")
    sched = q(con, "select g, (isodow(ts) - 1) * 24 + hour(ts) h, count(*) n from p join gm using (user_id) group by all")
    extra = ", any_value(label) label" if "label" in cols else ""
    extra += ", any_value(category) category" if "category" in cols else ""
    users = q(con, f"""select user_id, count(*) posts, epoch(min(ts))::bigint first, epoch(max(ts))::bigint last {extra}
                       from p semi join gm using (user_id) group by 1""").set_index("user_id")

    pairs = con.sql("select * from pairs").df()
    gmap = dict(zip(gm.user_id, gm.g))
    pairs["g"], gv = pairs.u.map(gmap), pairs.v.map(gmap)
    pairs = pairs[pairs.g.notna() & (pairs.g == gv)].astype({"g": int})
    pairs["w"] = (10 * pairs.dup + 3 * pairs["item"] + np.minimum(pairs.tgt, 3) + np.minimum(pairs.fast, 1)) * pairs.sched

    prof = {}
    if platform == "bluesky":
        import profiles
        prof = profiles.get(list(gm.user_id))
    kd = kd or {}

    by = {k: dict(list(df.groupby("g"))) for k, df in
          dict(posts=posts, keys=keys, timeline=timeline, sched=sched, pairs=pairs).items()}
    groups = []
    for c, r in cl.iterrows():
        g = rank[c]
        mem = list(gm[gm.g == g].user_id)
        members = []
        for u in mem:
            row = dict(id=u, posts=int(users.at[u, "posts"]), first=int(users.at[u, "first"]), last=int(users.at[u, "last"]))
            if "label" in users.columns and pd.notna(users.at[u, "label"]):
                row["label"] = bool(users.at[u, "label"])
            if "category" in users.columns and pd.notna(users.at[u, "category"]):
                row["category"] = str(users.at[u, "category"])
            p = prof.get(u)
            if p:
                row.update(handle=p["handle"], name=p["name"], bio=p["bio"][:300], created=p["created"],
                           followers=int(p["followers"]), total_posts=int(p["posts"]))
            elif prof:
                row["gone"] = True  # not returned by the public API: deleted, deactivated or taken down
            members.append(row)
        kp = by["posts"].get(g, posts.head(0))
        kp = {k: df for k, df in kp.groupby(["kind", "key"])}
        ks = []
        for k in by["keys"].get(g, keys.head(0)).itertuples():
            ps = kp.get((k.kind, k.key))
            ks.append(dict(kind=k.kind, key=k.key, users=int(k.users), fan=int(k.fan),
                           sample=k.sample[:300] if isinstance(k.sample, str) else None, t0=int(k.t0), t1=int(k.t1),
                           posts=None if ps is None else [dict(u=x.user_id, id=x.post_id, ts=int(x.ts), text=x.text)
                                                           for x in ps.itertuples()]))
        tl = by["timeline"].get(g, timeline.head(0))
        idx = {u: i for i, u in enumerate(mem)}
        h = [0] * 168
        for x in by["sched"].get(g, sched.head(0)).itertuples():
            h[int(x.h)] = int(x.n)
        e = by["pairs"].get(g, pairs.head(0)).sort_values("w", ascending=False).head(MAX_EDGES)
        n_kind = {x.kind: int(x.n) for x in counts[counts.g == g].itertuples()}
        tags = (r.get("tags", "") or "").split()
        kind, shares = kd.get(c, ("", {}))
        groups.append(dict(
            g=g, size=int(r["size"]), score=round(float(r.score), 3), density=round(float(r.density), 3),
            sched_sim=round(float(r.sched), 3), kind=kind, kind_shares={k: float(v) for k, v in shares.items()},
            tags=tags, shared=n_kind, why=why(len(mem), n_kind, float(r.sched), float(r.density), tags, members),
            members=members, keys=ks, schedule=h,
            timeline=[[idx[x.user_id], int(x.ts), int(bool(x.shared))] for x in tl.itertuples()],
            edges=[dict(u=x.u, v=x.v, w=round(float(x.w), 3), dup=round(float(x.dup), 3), item=round(float(x.item), 3),
                        tgt=round(float(x.tgt), 3), fast=round(float(x.fast), 3), sched=round(float(x.sched), 3))
                   for x in e.itertuples()]))

    stats = con.sql("select count(*), count(distinct user_id), epoch(min(ts))::bigint, epoch(max(ts))::bigint from p").fetchall()[0]
    data = dict(name=name, platform=platform, source=src, generated=dt.datetime.now().isoformat(timespec="minutes"),
                posts=stats[0], active_users=stats[1], start=stats[2], end=stats[3], n_groups=n_groups,
                groups=groups)
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/{name}.js.tmp", "w") as f:
        f.write(f"(window.SITE = window.SITE || {{}})[{json.dumps(name)}] = ")
        json.dump(data, f, default=str, separators=(",", ":"))
        f.write(";\n")
    os.replace(f"{OUT}/{name}.js.tmp", f"{OUT}/{name}.js")  # never serve half a file
    names = sorted(os.path.basename(p)[:-3] for p in glob.glob(f"{OUT}/*.js") if not p.endswith("datasets.js"))
    with open(f"{OUT}/datasets.js", "w") as f:
        f.write("window.DATASETS = " + json.dumps(names) + ";\n")
    shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), "osint", "index.html"), f"{OUT}/index.html")
    return f"{OUT}/{name}.js"


def why(n, k, sched, density, tags, members):
    """Two or three plain sentences: which shared traces put these accounts together."""
    parts = []
    if k.get("dup"):
        parts.append(f"{k['dup']} texts posted word for word by 2 or more members")
    if k.get("item"):
        parts.append(f"{k['item']} shared links, hashtags, mentions or reposts")
    if k.get("tgt"):
        parts.append(f"{k['tgt']} posts that 2 or more members replied to")
    s = f"{n} accounts share {', '.join(parts) or 'few traces'}."
    s += f" Their weekly schedules are {'very ' if sched >= 0.8 else ''}{'similar' if sched >= 0.5 else 'different'} " \
         f"(cosine {sched:.2f}), and {density:.0%} of member pairs are linked."
    notes = dict(**{"same-name": "most members use the same display name",
                    "new-accounts": "most accounts were created in the same 2 weeks",
                    "template-bio": "the bios are near-identical",
                    "blank-profiles": "most profiles have no name and no bio",
                    "gone-accounts": "many accounts are now deleted or taken down",
                    "likely-community": "old accounts with varied bios: this looks like a real community",
                    "own-domain": "most links go to one site that almost no one else links",
                    "no-sleep": "the accounts post through the night, with no quiet hours",
                    "high-volume": "the accounts post 50 or more times a day and have few followers",
                    "disclosed": "most bios say the accounts are bots or automated feeds",
                    "hidden": "3 or more bot signs, and the bios do not say they are bots"})
    t = [notes[x] for x in tags if x in notes]
    if t:
        s += " Account facts: " + "; ".join(t) + "."
    return s


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "bluesky"
    src = sys.argv[2] if len(sys.argv) > 2 else "data/live/*.parquet"
    min_posts = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    resolution = float(sys.argv[4]) if len(sys.argv) > 4 else 0.2
    top = int(sys.argv[5]) if len(sys.argv) > 5 else TOP
    con, cl, member = detect.detect(src, min_posts, resolution)
    if any(str(u).startswith("did:") for u in list(member)[:100]):
        cl = detect.tags(cl, member, top, con=con)
    kd = detect.kinds(con, cl, top)
    print("wrote", write(con, cl, member, name, src, top, kd))


if __name__ == "__main__":
    main()
