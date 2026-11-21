"""Export the numbers the slide deck shows: docs/data.js.

Usage:  uv run export_site.py [posts.parquet glob] [min_posts] [resolution]

Runs detect.py on the same data, then writes summary statistics only. No user IDs
leave this script: network nodes are renumbered, and evidence text is cut to 120 chars.
The deck (docs/index.html) reads window.DATA from docs/data.js.
"""
import datetime as dt
import json
import sys

import numpy as np

import detect

TOP_GROUPS = 12        # groups listed in the table slide
NET_GROUPS = 3         # groups drawn in the network slide
NET_MAX_NODES = 60     # per group
NET_MAX_EDGES = 250    # per group
SCATTER_GROUPS = 400


def q(con, sql):
    return con.sql(sql).fetchall()


def overview(con):
    posts, users, t0, t1, threads = q(con, """select count(*), count(distinct user_id), min(ts), max(ts),
                                                     count(distinct thread) from raw""")[0]
    labeled = q(con, "select count(*) from (select user_id from raw group by 1 having bool_or(label))")[0][0]
    active, active_lab = q(con, """select count(*), count(*) filter (where l) from
                                   (select user_id, bool_or(coalesce(label, false)) l from p group by 1)""")[0]
    has_labels = q(con, "select count(*) from raw where label is not null")[0][0] > 0
    return dict(posts=posts, users=users, start=str(t0)[:10], end=str(t1)[:10], threads=threads,
                labeled_users=labeled if has_labels else None, active_users=active,
                active_labeled=active_lab if has_labels else None,
                base_rate=(active_lab / active) if has_labels and active else None)


def monthly(con):
    rows = q(con, """with ul as (select user_id, bool_or(coalesce(label, false)) l from raw group by 1)
                     select strftime(date_trunc('month', ts), '%Y-%m') m, count(*) n,
                            count(*) filter (where ul.l) nl
                     from raw join ul using (user_id) group by 1 order by 1""")
    return [dict(month=m, posts=n, labeled_posts=nl) for m, n, nl in rows]


def channels(con, k=15):
    rows = q(con, f"""with ul as (select user_id, bool_or(coalesce(label, false)) l from raw group by 1)
                      select coalesce(thread, '(none)') t, count(*) n, avg(ul.l::int) share,
                             count(distinct user_id) u
                      from raw join ul using (user_id) group by 1 order by 2 desc limit {k}""")
    return [dict(name=str(t)[:40], posts=n, labeled_share=s, users=u) for t, n, s, u in rows]


def schedules(con):
    """Mean weekly profile (168 hours, Mon 00:00 first) for labeled vs other active users, each user normalized."""
    rows = q(con, """with ul as (select user_id, bool_or(coalesce(label, false)) l from p group by 1),
                     h as (select user_id, (isodow(ts)-1)*24 + hour(ts) h, count(*) c from p group by 1, 2),
                     t as (select user_id, sum(c) tot from h group by 1)
                     select ul.l, h.h, avg(h.c / t.tot) * count(*) / any_value(g.n)
                     from h join t using (user_id) join ul using (user_id)
                     join (select l, count(*) n from ul group by 1) g on g.l = ul.l
                     group by 1, 2""")
    out = {"labeled": [0.0] * 168, "other": [0.0] * 168}
    for l, hr, v in rows:
        out["labeled" if l else "other"][int(hr)] = float(v)
    if not any(out["labeled"]):
        out["labeled"] = None
    return out


def signal_lift(con, lab):
    pairs = con.sql("select * from pairs").df()
    if not lab:
        return None
    vals = np.array(list(lab.values()))
    both = pairs.u.map(lambda u: lab.get(u, False)) & pairs.v.map(lambda v: lab.get(v, False))
    base = float(both.mean()) if len(both) else 0  # baseline: any pair detect.py scored
    out = []
    for key, name in [("dup", "Same template text"), ("item", "Same link or hashtag"),
                      ("tgt", "Same reply targets"), ("fast", "Within 60 seconds")]:
        m = pairs[key] > 0
        rate = float(both[m].mean()) if m.any() else 0.0
        out.append(dict(signal=key, name=name, pairs=int(m.sum()), both_labeled=rate,
                        lift=rate / base if base else None))
    return dict(random_pair=base, signals=out, labeled_share=float(vals.mean()))


def precision(cl, member, lab, ks=(10, 25, 50, 100, 200, 500)):
    if not lab:
        return None
    out = []
    for k in ks:
        if k > len(cl):
            break
        keep = set(cl.index[:k])
        users = [u for u, c in member.items() if c in keep]
        out.append(dict(k=k, users=len(users), labeled=float(np.mean([lab.get(u, False) for u in users]))))
    return out


def groups(con, cl, member, lab):
    by_c = {}
    for u, c in member.items():
        by_c.setdefault(c, []).append(u)
    out = []
    for rank, (c, r) in enumerate(cl.head(TOP_GROUPS).iterrows(), 1):
        users = by_c[c]
        ev = []
        for kind, key, n, sample in detect.evidence(con, c, k=3):
            text = sample if kind == "dup" else (key.split(":", 1)[1] if kind == "tgt" else key)
            if kind == "tgt":
                text = "reply target " + str(text)[-12:]
            ev.append(dict(kind=kind, users=n, text=str(text or "")[:120]))
        out.append(dict(rank=rank, size=int(r["size"]), score=float(r.score), density=float(r.density),
                        sched=float(r.sched), dup=float(r.dup), item=float(r["item"]), tgt=float(r.tgt),
                        fast=float(r.fast),
                        labeled=int(sum(lab.get(u, False) for u in users)) if lab else None, evidence=ev))
    return out


def scatter(cl, member, lab):
    by_c = {}
    for u, c in member.items():
        by_c.setdefault(c, []).append(u)
    out = []
    for rank, (c, r) in enumerate(cl.head(SCATTER_GROUPS).iterrows(), 1):
        users = by_c[c]
        out.append(dict(rank=rank, size=int(r["size"]), score=float(r.score),
                        labeled=float(np.mean([lab.get(u, False) for u in users])) if lab else None))
    return out


def networks(con, cl, member, lab):
    pairs = con.sql("select u, v, dup, item, tgt, fast, sched from pairs").df()
    pairs["w"] = (10 * pairs.dup + 3 * pairs["item"] + np.minimum(pairs.tgt, 3) + np.minimum(pairs.fast, 1)) * pairs.sched
    pairs["cu"], pairs["cv"] = pairs.u.map(member), pairs.v.map(member)
    out = []
    for rank, c in enumerate(cl.index[:NET_GROUPS], 1):
        e = pairs[(pairs.cu == c) & (pairs.cv == c)].sort_values("w", ascending=False)
        deg = {}
        for u, v in zip(e.u, e.v):
            deg[u] = deg.get(u, 0) + 1
            deg[v] = deg.get(v, 0) + 1
        nodes = sorted(deg, key=deg.get, reverse=True)[:NET_MAX_NODES]
        idx = {u: i for i, u in enumerate(nodes)}
        e = e[e.u.isin(idx) & e.v.isin(idx)].head(NET_MAX_EDGES)
        main = lambda row: max(("dup", 10 * row.dup), ("item", 3 * row.item),
                               ("tgt", min(row.tgt, 3)), ("fast", min(row.fast, 1)), key=lambda x: x[1])[0]
        out.append(dict(rank=rank, size=int(cl.loc[c, "size"]),
                        nodes=[dict(id=idx[u], labeled=bool(lab.get(u, False)) if lab else None) for u in nodes],
                        edges=[dict(s=idx[r.u], t=idx[r.v], w=float(r.w), kind=main(r)) for r in e.itertuples()]))
    return out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "data/posts.parquet"
    min_posts = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    resolution = float(sys.argv[3]) if len(sys.argv) > 3 else 0.2   # same as detect.py
    con, cl, member = detect.detect(src, min_posts, resolution)
    lab = detect.labels(con)
    data = dict(
        generated=dt.datetime.now().isoformat(timespec="minutes"), source=src, min_posts=min_posts,
        platform=q(con, "select any_value(platform) from raw")[0][0],
        overview=overview(con), monthly=monthly(con), channels=channels(con), schedule=schedules(con),
        lift=signal_lift(con, lab), precision=precision(cl, member, lab),
        n_groups=int(len(cl)), groups=groups(con, cl, member, lab), scatter=scatter(cl, member, lab),
        networks=networks(con, cl, member, lab),
    )
    with open("docs/data.js", "w") as f:
        f.write("window.DATA = " + json.dumps(data, default=str) + ";\n")
    print(f"wrote docs/data.js ({len(cl)} groups)")


if __name__ == "__main__":
    main()
