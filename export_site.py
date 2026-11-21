"""Export the numbers the website shows into docs/data.js (one entry per dataset).

Usage:  uv run export_site.py NAME [posts.parquet glob] [min_posts] [resolution]
  uv run export_site.py telegram data/posts.parquet 20 0.2
  uv run export_site.py x data/posts_x.parquet 20 5

Runs detect.py on the data, then writes summary statistics only. No user IDs leave this
script: network nodes are renumbered, and evidence text is cut to 120 chars. Other datasets
already in docs/data.js are kept, so run it once per dataset.

Two kinds of ground truth are supported, whichever the data has:
  label    (True/False per account, e.g. Telegram ru_pa)  -> share labeled, signal lift
  category (group name per account, e.g. IRA categories) -> group purity vs random groups
"""
import datetime as dt
import json
import os
import sys

import numpy as np

import detect

OUT = "docs/data.js"
TOP_GROUPS = 12
NET_GROUPS = 3
NET_MAX_NODES = 60
NET_MAX_EDGES = 250
SCATTER_GROUPS = 400
NAMES = {"telegram": "Telegram: Russian channel comments", "x": "X: Russian IRA troll tweets",
         "bluesky": "Bluesky: live firehose"}


def q(con, sql):
    return con.sql(sql).fetchall()


def has_col(con, col):
    return col in con.sql("select * from raw limit 0").columns


def categories(con):
    if not has_col(con, "category"):
        return {}
    return dict(q(con, "select user_id, any_value(category) from p group by 1 having any_value(category) is not null"))


def overview(con, lab):
    posts, users, t0, t1, threads = q(con, """select count(*), count(distinct user_id), min(ts), max(ts),
                                                     count(distinct thread) from raw""")[0]
    active = q(con, "select count(distinct user_id) from p")[0][0]
    out = dict(posts=posts, users=users, start=str(t0)[:10], end=str(t1)[:10], threads=threads or None,
               active_users=active, labeled_users=None, base_rate=None)
    if lab:
        out["labeled_users"] = q(con, "select count(*) from (select user_id from raw group by 1 having bool_or(label))")[0][0]
        out["base_rate"] = float(np.mean(list(lab.values())))
    if has_col(con, "category"):
        out["categories"] = q(con, "select count(distinct category) from raw")[0][0] or None
    return out


def monthly(con, lab):
    if lab:
        rows = q(con, """with ul as (select user_id, bool_or(coalesce(label, false)) l from raw group by 1)
                         select strftime(date_trunc('month', ts), '%Y-%m'), count(*), count(*) filter (where ul.l)
                         from raw join ul using (user_id) group by 1 order by 1""")
        return [dict(month=m, posts=n, labeled_posts=nl) for m, n, nl in rows]
    rows = q(con, "select strftime(date_trunc('month', ts), '%Y-%m'), count(*) from raw group by 1 order by 1")
    return [dict(month=m, posts=n) for m, n in rows]


def breakdown(con, lab, k=13):
    """Posts per channel (thread) when the data has channels, else per account category."""
    by = "thread" if q(con, "select count(distinct thread) from raw")[0][0] > 1 else \
         ("category" if has_col(con, "category") else None)
    if not by:
        return None
    lab_sql = "avg(ul.l::int)" if lab else "null"
    rows = q(con, f"""with ul as (select user_id, bool_or(coalesce(label, false)) l from raw group by 1)
                      select coalesce({by}::varchar, '(none)'), count(*), {lab_sql}, count(distinct user_id)
                      from raw join ul using (user_id) group by 1 order by 2 desc limit {k}""")
    return dict(by="channel" if by == "thread" else "category",
                rows=[dict(name=str(t)[:40], posts=n, labeled_share=s, users=u) for t, n, s, u in rows])


def schedules(con, lab, cats):
    """Mean weekly profile (168 hours, Mon 00:00 first), each account normalized, for up to two account groups."""
    if lab:
        group_sql, names = "case when bool_or(coalesce(label, false)) then 'Labeled propaganda accounts' else 'Other accounts' end", None
    elif cats:
        top = [c for c, in q(con, """select category from (select user_id, any_value(category) category from p group by 1)
                                    where category is not null group by 1 order by count(*) desc limit 2""")]
        group_sql, names = "any_value(category)", top
    else:
        group_sql, names = "'All scored accounts'", None
    rows = q(con, f"""with g as (select user_id, {group_sql} grp from p group by 1),
                     h as (select user_id, (isodow(ts)-1)*24 + hour(ts) h, count(*) c from p group by 1, 2),
                     t as (select user_id, sum(c) tot from h group by 1),
                     n as (select grp, count(*) n from g group by 1)
                     select g.grp, h.h, sum(h.c / t.tot) / any_value(n.n)
                     from h join t using (user_id) join g using (user_id) join n on n.grp = g.grp
                     group by 1, 2""")
    prof = {}
    for grp, hr, v in rows:
        prof.setdefault(grp, [0.0] * 168)[int(hr)] = float(v)
    order = names or sorted(prof)
    return [dict(name=g, values=prof[g]) for g in order if g in prof][:2]


def signal_lift(con, lab):
    if not lab:
        return None
    pairs = con.sql("select * from pairs").df()
    both = pairs.u.map(lambda u: lab.get(u, False)) & pairs.v.map(lambda v: lab.get(v, False))
    base = float(both.mean()) if len(both) else 0  # baseline: any pair detect.py scored
    out = []
    for key, name in [("dup", "Same template text"), ("item", "Same link or hashtag"),
                      ("tgt", "Same reply targets"), ("fast", "Within 60 seconds")]:
        m = pairs[key] > 0
        rate = float(both[m].mean()) if m.any() else 0.0
        out.append(dict(signal=key, name=name, pairs=int(m.sum()), both_labeled=rate, lift=rate / base if base else None))
    return dict(random_pair=base, signals=out)


def by_cluster(member):
    out = {}
    for u, c in member.items():
        out.setdefault(c, []).append(u)
    return out


def purity_of(groups_users, cat):
    tot = hit = 0
    for users in groups_users:
        vals = [cat[u] for u in users if u in cat]
        if vals:
            tot += len(vals)
            hit += max(vals.count(v) for v in set(vals))
    return hit / tot if tot else None, tot


def precision(cl, member, lab, cats, ks=(10, 25, 50, 100, 200, 500)):
    g = by_cluster(member)
    out = []
    if cats:
        users = [u for u in member if u in cats]
        shuffled = dict(zip(users, np.random.default_rng(0).permutation([cats[u] for u in users])))
    for k in ks:
        if k > len(cl):
            break
        top = [g[c] for c in cl.index[:k]]
        n = sum(len(x) for x in top)
        row = dict(k=k, users=n)
        if lab:
            row["labeled"] = float(np.mean([lab.get(u, False) for x in top for u in x]))
        if cats:
            row["purity"], _ = purity_of(top, cats)
            row["random"], _ = purity_of(top, shuffled)
        out.append(row)
    return out or None


def top_cat(users, cats):
    vals = [cats[u] for u in users if u in cats]
    if not vals:
        return None, None
    best = max(set(vals), key=vals.count)
    return best, vals.count(best) / len(vals)


def groups(con, cl, member, lab, cats):
    g = by_cluster(member)
    out = []
    for rank, (c, r) in enumerate(cl.head(TOP_GROUPS).iterrows(), 1):
        users = g[c]
        ev = []
        for kind, key, n, sample in detect.evidence(con, c, k=3):
            text = sample if kind == "dup" else key
            if kind == "tgt":
                text = "reply target …" + str(key)[-10:]
            ev.append(dict(kind=kind, users=n, text=str(text or "")[:120]))
        cat, share = top_cat(users, cats)
        out.append(dict(rank=rank, size=int(r["size"]), score=float(r.score), density=float(r.density),
                        sched=float(r.sched), labeled=int(sum(lab.get(u, False) for u in users)) if lab else None,
                        top_category=cat, category_share=share, evidence=ev))
    return out


def scatter(cl, member, lab, cats):
    g = by_cluster(member)
    out = []
    for rank, (c, r) in enumerate(cl.head(SCATTER_GROUPS).iterrows(), 1):
        users = g[c]
        y = float(np.mean([lab.get(u, False) for u in users])) if lab else top_cat(users, cats)[1]
        out.append(dict(rank=rank, size=int(r["size"]), score=float(r.score), y=y))
    return out


def networks(con, cl, member, lab, cats):
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
        main = lambda row: max(("dup", 10 * row.dup), ("item", 3 * row.item), ("tgt", min(row.tgt, 3)),
                               ("fast", min(row.fast, 1)), key=lambda x: x[1])[0]
        out.append(dict(rank=rank, size=int(cl.loc[c, "size"]),
                        nodes=[dict(id=idx[u], labeled=bool(lab.get(u, False)) if lab else None,
                                    category=cats.get(u)) for u in nodes],
                        edges=[dict(s=idx[r.u], t=idx[r.v], w=float(r.w), kind=main(r)) for r in e.itertuples()]))
    return out


def load_existing():
    if not os.path.exists(OUT):
        return {}
    s = open(OUT).read()
    start, end = s.find("{", s.find("window.DATASETS")), s.rfind("};")
    try:
        return json.loads(s[start:end + 1])
    except ValueError:
        return {}


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "telegram"
    src = sys.argv[2] if len(sys.argv) > 2 else "data/posts.parquet"
    min_posts = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    resolution = float(sys.argv[4]) if len(sys.argv) > 4 else 0.2   # same as detect.py
    con, cl, member = detect.detect(src, min_posts, resolution)
    lab, cats = detect.labels(con), categories(con)
    data = dict(
        name=NAMES.get(name, name), seed=False, truth="labels" if lab else ("categories" if cats else None),
        generated=dt.datetime.now().isoformat(timespec="minutes"), source=src, min_posts=min_posts, resolution=resolution,
        platform=q(con, "select any_value(platform) from raw")[0][0],
        overview=overview(con, lab), monthly=monthly(con, lab), breakdown=breakdown(con, lab),
        schedule=schedules(con, lab, cats), lift=signal_lift(con, lab), precision=precision(cl, member, lab, cats),
        n_groups=int(len(cl)), groups=groups(con, cl, member, lab, cats), scatter=scatter(cl, member, lab, cats),
        networks=networks(con, cl, member, lab, cats),
    )
    all_data = load_existing()
    all_data[name] = data
    os.makedirs("docs", exist_ok=True)
    with open(OUT, "w") as f:
        f.write("// Written by export_site.py. One entry per dataset; the site's dropdown lists them.\n")
        f.write("window.DATASETS = " + json.dumps(all_data, default=str) + ";\n")
    print(f"wrote {OUT}: {name} ({len(cl)} groups); datasets now: {', '.join(all_data)}")


if __name__ == "__main__":
    main()
