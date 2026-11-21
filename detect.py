"""Find groups of users who act together. Works on any posts table from ingest.py or monitor.py.

Usage:  uv run detect.py [posts.parquet glob] [min_posts] [resolution]
        higher resolution = smaller, tighter groups (0.2 for Telegram, 5 for the all-troll X data)

No text model. Signals for each pair of users, each weighted 1/(users-1) so popular
things count less:
  tgt   - replied to the same message
  fast  - replied to / posted the same thing within 60 s of each other
  item  - shared the same link, #hashtag or @mention
  dup   - posted the same text after normalizing (case, links, digits, punctuation, emoji)
  sched - cosine of 168-hour weekly activity profiles (multiplies the others)
After detection, kinds() labels each top group political / scam / porn / other with a small embedding model.
"""
import html
import sys

import duckdb
import igraph as ig
import numpy as np
import pandas as pd

MAX_FAN = 100     # skip keys shared by more users than this (too popular to mean anything)
MIN_EVENTS = 3    # a pair needs at least this many shared keys
WINDOW_S = 60


def detect(src, min_posts=20, resolution=0.2):
    con = duckdb.connect()
    con.sql(f"create view raw as select * from read_parquet('{src}', union_by_name=true)")
    con.sql(f"""create table p as select * from raw where user_id in
                (select user_id from raw group by 1 having count(*) >= {min_posts})""")

    # one row per (signal kind, key, user)
    con.sql(r"""
    create table ev as
    with n as (
      select *, trim(regexp_replace(lower(regexp_replace(coalesce(text, ''), 'https?://\S+|@\S+', '', 'g')),
                                    '[^\p{L}]+', ' ', 'g')) norm
      from p)
    select 'tgt' kind, coalesce(thread, '') || ':' || reply_to key, user_id, min(ts) t0, null sample
      from n where reply_to is not null group by all
    union all
    select 'item', it, user_id, min(ts), null from (select user_id, ts, unnest(items) it from n) group by all
    union all
    select 'dup', md5(norm), user_id, min(ts), any_value(text) from n where length(norm) >= 30 group by all
    """)
    con.sql(f"""create table ev2 as select * from
                (select *, count(*) over (partition by kind, key) fan from ev) where fan between 2 and {MAX_FAN}""")

    pairs = con.sql(f"""
    select a.user_id u, b.user_id v, count(*) n,
      sum(case when a.kind='tgt'  then 1.0/(a.fan-1) else 0 end) tgt,
      sum(case when a.kind='item' then 1.0/(a.fan-1) else 0 end) item,
      sum(case when a.kind='dup'  then 1.0/(a.fan-1) else 0 end) dup,
      sum(case when abs(epoch(a.t0) - epoch(b.t0)) <= {WINDOW_S} then 1.0/(a.fan-1) else 0 end) fast
    from ev2 a join ev2 b on a.kind=b.kind and a.key=b.key and a.user_id < b.user_id
    group by 1, 2 having count(*) >= {MIN_EVENTS} or bool_or(a.kind in ('dup', 'item'))
    """).df()

    # weekly schedule profile per user
    prof = con.sql("select user_id, (isodow(ts)-1)*24 + hour(ts) h, count(*) c from p group by 1, 2").fetchnumpy()
    uids, inv = np.unique(prof["user_id"], return_inverse=True)
    M = np.zeros((len(uids), 168), np.float32)
    np.add.at(M, (inv, prof["h"].astype(int)), prof["c"].astype(np.float32))
    M /= np.linalg.norm(M, axis=1, keepdims=True)
    iu, iv = np.searchsorted(uids, pairs.u), np.searchsorted(uids, pairs.v)
    pairs["sched"] = (M[iu] * M[iv]).sum(1)
    con.register("pairs", pairs)
    member, cl = cluster(pairs, resolution)
    con.register("members", pd.DataFrame({"user_id": list(member), "c": list(member.values())}))
    return con, cl, member


def cluster(pairs, resolution=0.2):
    """Weight edges by measured lift on the Telegram labels, then find tight groups with Leiden (CPM)."""
    # lift vs random pair: dup ~94x, item ~9x, tgt ~5x at moderate values; huge tgt/fast = chatty regulars, so cap
    w = 10 * pairs.dup + 3 * pairs["item"] + np.minimum(pairs.tgt, 3) + np.minimum(pairs.fast, 1)
    pairs = pairs.assign(w=w * pairs.sched)
    g = ig.Graph.TupleList(pairs[["u", "v", "w"]].itertuples(index=False), weights=True)
    comm = g.community_leiden(objective_function="CPM", resolution=resolution, weights="weight", n_iterations=5)
    member = dict(zip(g.vs["name"], comm.membership))
    cu, cv = pairs.u.map(member), pairs.v.map(member)
    inside = pairs[cu == cv].assign(c=cu[cu == cv])
    cl = inside.groupby("c").agg(edges=("w", "size"), w=("w", "sum"), tgt=("tgt", "sum"), item=("item", "sum"),
                                 dup=("dup", "sum"), fast=("fast", "sum"), sched=("sched", "mean"))
    cl["size"] = [comm.size(c) for c in cl.index]
    cl = cl[cl["size"] >= 3]
    cl["density"] = cl.edges / (cl["size"] * (cl["size"] - 1) / 2)
    # rank by shared content per member; shared reply targets alone mostly find chat regulars
    cl["score"] = (10 * cl.dup + 3 * cl["item"]) / cl["size"]
    return member, cl.sort_values("score", ascending=False)


def evidence(con, c, k=3):
    """Keys shared by the most members of cluster c."""
    return con.sql(f"""select kind, key, count(*) users, any_value(sample) sample from ev2
                       join members m using (user_id) where m.c = {c}
                       group by 1, 2 order by 3 desc limit {k}""").fetchall()


# Group type: each sampled post votes for the class of its closest prototype sentence (only when it is clearly
# closer to one class than to the others). A group is the class with the largest vote share, if that share is
# at least MIN_SHARE; links to porn or scam hosts add to the share. The text gives the topic only: a "political"
# group can be real activists. Evidence for a state operator is the schedule signal and the labels.
PROTOTYPES = {
    "political": ["elections, the government, the president and parliament", "war in Ukraine, NATO, Russia, sanctions",
                  "immigrants, the border, police, protests, the left and the right", "Trump, Hillary, Obama, Democrats, Republicans",
                  "racism, black lives matter, police shooting, civil rights", "guns, abortion, taxes, the media lies",
                  "выборы, власть, президент, правительство", "война, НАТО, Украина, Запад, санкции, Путин",
                  "либералы, оппозиция, Навальный, Зеленский, ВСУ"],
    "scam": ["crypto giveaway, send coins and double your money", "invest now, guaranteed profit, trading signals, DM me",
             "you won a prize, claim your reward, click the link", "free followers, promo code, buy now, limited offer",
             "earn money from home, passive income, join my team", "криптовалюта, заработок, инвестиции, пиши в личку",
             "казино, ставки, бонус за регистрацию, выигрыш", "deal, discount price, affiliate link, buy it on Amazon",
             "please help my family, we are starving, donate to our gofundme, every dollar helps"],
    "porn": ["hot girls, nudes, link in bio, onlyfans", "sexy content, horny, 18+, adult videos, cam girls",
             "lonely singles near you want to meet tonight", "big cock, daddy, cum, cuck, sweet cheeks, bulge",
             "интим, знакомства, голые девушки 18+", "야동, 성인, 무료 영상, 유부녀, 자위", "エロ動画, 裏垢, 無料, 18禁"],
    "other": ["good morning, have a nice day, love this", "music, art, games, books, movies, sports",
              "my cat, food, weather, coffee, work today", "lol this is so funny, same, me too",
              "local news: accident, fire, weather, traffic", "football match, goal, the team wins the league",
              "привет, как дела, спасибо, хорошего дня", "футбол, матч, гол, команда выиграла"],
}
DOMAINS = {
    "porn": ["onlyfans", "fansly", "pornhub", "xvideos", "chaturbate", "stripchat", "fanvue", "manyvids", "loyalfans"],
    "scam": ["airdrop", "claim", "bonus", "casino", "1xbet", "betway", "promo", "giveaway", "reward", "gofundme", "amzn.to"],
}  # matched against the link host only; shorteners and link-in-bio hosts are left out, everyone uses them
MARGIN = 0.05     # a post votes only if its best class beats the second class by this cosine
MIN_SHARE = 0.15  # below this share for every flagged class, the group is "other"


def kinds(con, cl, top=200, per_group=200):
    """Return {group: (kind, {class: vote share})} for the top groups."""
    from model2vec import StaticModel  # lazy: detect works without it
    ids = ",".join(str(c) for c in cl.index[:top])
    if not ids:
        return {}
    model = StaticModel.from_pretrained("minishlab/potion-multilingual-128M")
    txt = con.sql(f"""select c, text from (select m.c, p.text, row_number() over (partition by m.c order by hash(p.post_id)) r
                      from p join members m using (user_id) where m.c in ({ids}) and length(p.text) >= 20) where r <= {per_group}""").df()
    url = con.sql(f"""select m.c, string_agg(it, ' ') urls from (select user_id, unnest(items) it from p) join members m using (user_id)
                      where m.c in ({ids}) and starts_with(it, 'url:') group by 1""").df().set_index("c").urls

    def unit(x):
        return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-9)
    names = list(PROTOTYPES)
    protos = [unit(model.encode(PROTOTYPES[k])) for k in names]
    E = unit(model.encode(txt.text.tolist())) if len(txt) else np.zeros((0, protos[0].shape[1]))
    S = np.stack([(E @ p.T).max(1) for p in protos], 1)  # best prototype sentence per class
    top2 = np.sort(S, 1)
    vote = np.where(top2[:, -1] - top2[:, -2] >= MARGIN, S.argmax(1), names.index("other"))
    out = {}
    for c in cl.index[:top]:
        v = vote[(txt.c == c).to_numpy()]
        s = dict(zip(names, (np.bincount(v, minlength=len(names)) / max(len(v), 1)).round(2)))
        links = url.get(c, "").split()
        for k, doms in DOMAINS.items():
            if links:
                s[k] = round(s[k] + sum(any(d in u[4:].split("/")[0] for d in doms) for u in links) / len(links), 2)
        flag = max((k for k in names if k != "other"), key=s.get)
        out[c] = (flag if s[flag] >= MIN_SHARE else "other", s)
    return out


def labels(con):
    return dict(con.sql("select user_id, any_value(label) from p group by 1 having any_value(label) is not null").fetchall())


def _grams(t):
    t = " ".join(t.lower().split())
    return {t[i:i + 3] for i in range(len(t) - 2)}


def _jaccard_mean(texts):
    g = [_grams(t) for t in texts if len(t) >= 10]
    pairs = [(a, b) for i, a in enumerate(g) for b in g[i + 1:]]
    return np.mean([len(a & b) / len(a | b) for a, b in pairs]) if pairs else None


def tags(cl, member, top=100, today=None):
    """Bluesky only: tag the top groups from public account facts and re-rank them.
    same-name / new-accounts / template-bio / blank-profiles / gone-accounts push a group up;
    likely-community (old accounts with real, varied bios) pushes it down."""
    import profiles
    by_c = {}
    for u, c in member.items():
        if c in set(cl.index[:top]) and u.startswith("did:"):
            by_c.setdefault(c, []).append(u)
    if not by_c:
        return cl
    prof = profiles.get([u for us in by_c.values() for u in us[:50]])
    today = pd.Timestamp(today or pd.Timestamp.utcnow().date())
    cl = cl.copy()
    cl["tags"] = ""
    for c, users in by_c.items():
        sample = users[:50]
        ps = [prof[u] for u in sample if u in prof]
        t = []
        if len(sample) - len(ps) >= 0.3 * len(sample):  # deleted, suspended or taken down since they posted
            t.append("gone-accounts")
        if len(ps) < 3:
            cl.loc[c, "tags"] = " ".join(t)
            cl.loc[c, "score"] *= 1.5 ** len(t)
            continue
        if sum(1 for p in ps if not p["name"] and not p["bio"]) >= 0.5 * len(ps):
            t.append("blank-profiles")
        names = [p["name"] for p in ps if p["name"]]
        if names and max(names.count(n) for n in set(names)) >= 0.5 * len(ps):
            t.append("same-name")
        days = sorted(pd.Timestamp(p["created"]) for p in ps if p["created"])
        batch = max((sum(1 for d in days if a <= d <= a + pd.Timedelta(days=14)) for a in days), default=0)
        recent = days and (today - days[len(days) // 2]).days <= 180
        if recent and batch >= 0.5 * len(ps):  # Bluesky had a big real sign-up wave in Nov 2024, so only recent batches
            t.append("new-accounts")
        bio = _jaccard_mean([p["bio"] for p in ps])
        if bio is not None and bio >= 0.6:
            t.append("template-bio")
        old = days and (today - days[len(days) // 2]).days > 365
        has_bio = sum(1 for p in ps if len(p["bio"]) >= 10) >= 0.5 * len(ps)
        if old and not t and has_bio and bio < 0.2:
            t.append("likely-community")
        cl.loc[c, "tags"] = " ".join(t)
        cl.loc[c, "score"] *= 0.3 if "likely-community" in t else 1.5 ** len(t)
    return cl.sort_values("score", ascending=False)


def report(con, cl, member, out="data/report.html", top=30, platform_url=None, refresh=None, kd=None):
    lab = labels(con)
    kd = kd if kd is not None else kinds(con, cl, top)
    by_c = {}
    for u, c in member.items():
        by_c.setdefault(c, []).append(u)
    rows = []
    for c, r in cl.head(top).iterrows():
        users = by_c[c]
        if platform_url:
            links = " ".join(f'<a href="{platform_url.format(html.escape(u))}">{html.escape(u[-8:])}</a>' for u in users[:15])
        else:
            links = " ".join(html.escape(u) for u in users[:15])
        more = f" +{len(users) - 15}" if len(users) > 15 else ""
        lab_txt = f"{sum(lab.get(u, False) for u in users)}/{len(users)}" if lab else ""
        ev = "<br>".join(f"<b>{k}</b> ×{n}: {html.escape((s or key)[:140])}" for k, key, n, s in evidence(con, c))
        kind, ks = kd.get(c, ("", {}))
        ktip = html.escape(" ".join(f"{k}={v:.2f}" for k, v in ks.items()))
        tg = html.escape(r.get("tags", "") or "")
        rows.append(f"<tr><td title=\"{ktip}\">{kind}<br><small>{tg}</small></td><td>{r['size']}</td><td>{r.score:.2f}</td><td>{r.density:.2f}</td><td>{r.sched:.2f}</td>"
                    f"<td>{r.tgt:.1f} / {r.fast:.1f} / {r["item"]:.1f} / {r.dup:.1f}</td><td>{lab_txt}</td>"
                    f"<td>{links}{more}</td><td>{ev}</td></tr>")
    meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    stats = con.sql("select count(*), count(distinct user_id), min(ts), max(ts) from p").fetchall()[0]
    open(out, "w").write(f"""<!doctype html><meta charset="utf-8">{meta}<title>Coordination report</title>
<style>body{{font:14px system-ui;margin:24px}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:4px 8px;vertical-align:top}}th{{background:#eee}}</style>
<h2>Coordinated groups</h2><p>{stats[0]:,} posts from {stats[1]:,} active users, {stats[2]} to {stats[3]}. {len(cl)} groups found.</p>
<table><tr><th>kind</th><th>size</th><th>score</th><th>density</th><th>schedule</th><th>targets / fast / items / dup</th><th>labeled</th><th>members</th><th>top shared evidence</th></tr>
{''.join(rows)}</table>""")


def evaluate(con, cl, member):
    cats = dict(con.sql("select user_id, any_value(category) from p group by 1 having any_value(category) is not null").fetchall()
                if "category" in con.sql("select * from p limit 0").columns else [])
    if cats:  # known account groups: are found groups pure? compare with random groups of the same sizes
        users = [u for u in member if u in cats]
        shuffled = dict(zip(users, np.random.default_rng(0).permutation([cats[u] for u in users])))
        def purity(k, cat):
            top, tot, hit = set(cl.index[:k]), 0, 0
            by_c = {}
            for u, c in member.items():
                if c in top and u in cat:
                    by_c.setdefault(c, []).append(cat[u])
            for vals in by_c.values():
                tot += len(vals); hit += max(vals.count(v) for v in set(vals))
            return hit / max(tot, 1), tot
        for k in sorted({10, 50, len(cl)}):
            p, n = purity(k, cats)
            print(f"top {k:>4} groups: {n:>5} users, purity {p:.1%} (random groups: {purity(k, shuffled)[0]:.1%})")
    lab = labels(con)
    if not lab:
        return
    base = np.mean(list(lab.values()))
    print(f"base rate (active users labeled): {base:.1%}")
    for k in (10, 50, 200):
        users = [u for u, c in member.items() if c in set(cl.index[:k])]
        print(f"top {k:>3} groups: {len(users):>6} users, {np.mean([lab.get(u, False) for u in users]):.1%} labeled")


def kind_summary(con, member, kd):
    """Users per group kind, split by known category or label when the data has one."""
    cols = con.sql("select * from p limit 0").columns
    col = "category" if "category" in cols and con.sql("select count(category) from p").fetchall()[0][0] else "label"
    truth = dict(con.sql(f"select user_id, any_value({col})::varchar from p group by 1").fetchall())
    df = pd.DataFrame([(kd[c][0], truth.get(u)) for u, c in member.items() if c in kd], columns=["kind", col])
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(pd.crosstab(df.kind, df[col].fillna("-"), margins=True))


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "data/posts.parquet"
    con, cl, member = detect(src, int(sys.argv[2]) if len(sys.argv) > 2 else 20,
                            float(sys.argv[3]) if len(sys.argv) > 3 else 0.2)
    evaluate(con, cl, member)
    out = src.replace("posts", "report").replace(".parquet", ".html")
    kd = kinds(con, cl)
    kind_summary(con, member, kd)
    report(con, cl, member, out=out, kd=kd)
    print("wrote", out)
