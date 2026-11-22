"""Detect coordinated political influence networks with explainable behavioral forensics."""

import argparse
import ast
from collections import Counter, defaultdict
from datetime import UTC
from html import escape
import json
from pathlib import Path
from random import Random
import re
from statistics import median
from tempfile import TemporaryDirectory
from threading import Lock

import duckdb
import igraph


SOURCES = {
    "x_ira": ("x", "Russian troll archive (X)"),
    "telegram_research": ("telegram", "Telegram war chats (researcher-labeled)"),
    "bluesky": ("bluesky", "Bluesky public posts"),
}

# Verified raw record totals from the source archives prior to political/spam filtering.
RAW_ARCHIVE_TOTALS = {
    ("telegram", "telegram_research"): 17_310_897,
    ("x", "x_ira"): 2_946_207,
    ("bluesky", "bluesky"): 2_274_195,
}

MAX_FAN = 100
MIN_SIGNAL_EVENTS = 2
MIN_TELEGRAM_TEMPLATE_LENGTH = 60
REPOST_WINDOW_SECONDS = 15
MIN_GROUP_SIZE = 3
MAX_EXHIBITS = 6
MAX_EDGE_WEIGHT = 8
LEIDEN_RESOLUTION = 0.25
LEIDEN_LOCK = Lock()

SHORTENER_DOMAINS = frozenset({
    "t.co", "bit.ly", "tinyurl.com", "ow.ly", "buff.ly", "lnkd.in", "fb.me", "goo.gl",
    "dlvr.it", "ift.tt", "trib.al", "reut.rs", "nyti.ms", "politi.co", "cnn.it", "vk.cc",
    "youtu.be", "youtube.com", "twitter.com", "x.com", "bsky.app", "t.me", "share.google",
    "ebx.sh", "mrf.lu", "ln.is", "wp.me", "shar.es", "is.gd", "amzn.to",
})

# Documented state-funded or IRA-affiliated media outlets (reference annotation only).
STATE_MEDIA_DOMAINS = frozenset({
    "riafan.ru", "fapnews.ru", "newinform.com", "nation-news.ru", "rueconomics.ru",
    "inforeactor.ru", "politexpert.net", "slovodel.com", "nevnov.ru", "nahnews.org",
    "russian.rt.com", "rt.com", "sputniknews.com", "ria.ru", "tass.ru", "vesti.ru",
    "crimea-24.com", "boeing-is-back.livejournal.com", "pravda.ru", "podrobnosti.biz",
})

# Mainstream news and syndication hosts (used to separate RSS/news mirrors from covert ops).
MAINSTREAM_NEWS_DOMAINS = frozenset({
    "nytimes.com", "theguardian.com", "washingtonpost.com", "politico.com", "reuters.com",
    "apnews.com", "bbc.com", "bbc.co.uk", "cnn.com", "motherjones.com", "kyivindependent.com",
    "en.interfax.com.ua", "theatlantic.com", "rawstory.com", "democracydocket.com",
    "demdock.com", "open.substack.com", "npr.org", "abcnews.go.com", "cbsnews.com",
    "nbcnews.com", "wsj.com", "bloomberg.com", "forbes.com", "thehill.com", "axios.com",
    "newsweek.com", "usatoday.com", "propublica.org", "alternet.org", "chicagotribune.com",
    "triblive.com", "wtae.com", "cnnbrasil.com.br", "memeorandum.com", "politicalwire.com",
    "radaronline.com", "irishstar.com", "the-hear.com", "meduza.io", "rbc.ru", "gazeta.ru",
    "lenta.ru", "kp.ru", "vz.ru", "izvestia.ru", "tvrain.ru", "ntv.ru", "kommersant.ru",
    "huffpost.com", "slate.com", "vox.com", "salon.com", "thedailybeast.com",
    "thegatewaypundit.com", "breitbart.com", "foxnews.com", "msnbc.com",
})


def _word_pattern(terms):
    return r"(?:^|[^\p{L}\p{N}])(?:" + "|".join(terms) + r")(?:$|[^\p{L}\p{N}])"


POLITICAL = _word_pattern((
    # English
    r"elections?|electoral|ballots?|voter(?:s| fraud| suppression)?|voting|voted",
    r"democrats?|republicans?|democratic party|gop|maga|brexit|blm|black lives matter",
    r"trump|biden|harris|clinton|obama|zelensky[yi]?|putin|kremlin|navalny|lukashenko",
    r"parliaments?|congress|senate|senators?|legislatur\w*|government\w*|president\w*",
    r"white house|prime minister|foreign policy|diploma\w*|public policy|politic\w*",
    r"nato|ukrain\w*|russia\w*|donbas\w*|crimea\w*|gaza|palestin\w*|hamas|hezbollah",
    r"sanctions?|invasions?|ceasefires?|war crimes?|military aid|armed forces",
    r"disinformation|propaganda|information war(?:fare)?|influence operation(?:s)?",
    r"gun control|abortion|immigration|deport\w*|civil rights|voting rights",
    # Russian and Ukrainian (inflected stems)
    r"выбор\p{L}*|вибор\p{L}*|голосован\p{L}*|голосуван\p{L}*|партия|парті\p{L}*",
    r"парламент\p{L}*|госдум\p{L}*|сенат\p{L}*|правительств\p{L}*|уряд\p{L}*",
    r"президент\p{L}*|политик\p{L}*|політик\p{L}*|оппозици\p{L}*|опозиці\p{L}*",
    r"путин\p{L}*|путін\p{L}*|зеленск\p{L}*|зеленськ\p{L}*|кремл\p{L}*|навальн\p{L}*",
    r"лукашенк\p{L}*|нато|украин\p{L}*|україн\p{L}*|росси\p{L}*|росі\p{L}*",
    r"донбасс?\p{L}*|крым\p{L}*|крим\p{L}*|всу|зсу|сво|киев\p{L}*|київ\p{L}*",
    r"войн\p{L}*|війн\p{L}*|военн\p{L}*|військов\p{L}*|санкци\p{L}*|санкці\p{L}*",
    r"вторжени\p{L}*|вторгнен\p{L}*|оккупац\p{L}*|окупац\p{L}*|перемири\p{L}*",
    r"дезинформаци\p{L}*|дезінформаці\p{L}*|пропаганд\p{L}*",
))

OFF_TOPIC = _word_pattern((
    r"nudes? in (?:my )?(?:bio|dms)|(?:dm|message) me for nudes?|nude pics? (?:in bio|for sale)",
    r"porn videos?|explicit videos? (?:in bio|for sale)|watch (?:free )?porn|sex cams?|camgirl\w*",
    r"(?:watch|buy) (?:my )?adult videos?|adult videos? (?:sale|for sale)|nsfw content (?:for sale|in (?:bio|dms))",
    r"sexting for (?:cash|tips)|(?:subscribe to|join) my (?:onlyfans|fansly|fanvue)",
    r"купить интим\p{L}*|интимные услуги|порно видео|порновидео|порно ролик\p{L}*|порно чат\p{L}*",
    r"야동|성인 영상|エロ動画|アダルト動画",
    r"buy now|coupon code|promo code|affiliate link|click to claim|giveaway rules",
    r"crypto airdrop|guaranteed profit|free spins|limited time offer|sale ends today",
    r"casino (?:crypto )?giveaway|claim (?:your|the) (?:casino )?bonus|bet now|sign.up bonus",
    r"промокод\p{L}*|бесплатные фриспины|криптораздач\p{L}*|гарантированная прибыль",
))

ADULT_HOSTS = (
    r"onlyfans[.]com|fansly[.]com|pornhub[.]com|xvideos[.]com|xnxx[.]com|"
    r"chaturbate[.]com|stripchat[.]com|fanvue[.]com|manyvids[.]com|loyalfans[.]com|"
    r"xhamster[.]com|redtube[.]com|youporn[.]com|adultfriendfinder[.]com|"
    r"brazzers[.]com|spankbang[.]com|pornhubpremium[.]com"
)

URL_RE = r"https?://[^\s<>]+"
MENTION_RE = r"@[\p{L}\p{N}_.:-]+"
REPOST_RE = r"rt:(at://did:[A-Za-z0-9:._%-]+/app[.]bsky[.]feed[.]post/[A-Za-z0-9._~-]+)"
BODY = rf"""nfc_normalize(lower(regexp_replace(coalesce(text, ''), '{URL_RE}|{MENTION_RE}', ' ', 'gi')))"""
NORMALIZED = "trim(regexp_replace(body, '[^\\p{L}\\p{N}]+', ' ', 'g'))"
POST_THREAD = "case when platform = 'telegram' then coalesce(thread, '') else '' end"
POST_IDENTITY = f"platform, {POST_THREAD}, user_id, post_id"

_WORD_SPLIT_RE = re.compile(r"[^\w]+", re.UNICODE)
_URL_STRIP_RE = re.compile(r"https?://\S+|@\S+", re.IGNORECASE)


def unpack_telegram_text(raw):
    """Unpack Telegram JSON-like entity arrays ([{'type': 'bold', 'text': '...'}, ...]) into plain text."""
    if not raw:
        return ""
    s = raw.strip()
    if not (s.startswith("[") and s.endswith("]")):
        return raw
    try:
        parts = ast.literal_eval(s)
    except (SyntaxError, ValueError):
        return raw
    if not isinstance(parts, list):
        return raw
    out = []
    for part in parts:
        if isinstance(part, str):
            out.append(part)
        elif isinstance(part, dict) and isinstance(part.get("text"), str):
            out.append(part["text"])
    return "".join(out) if out else raw


def _content_words(text):
    """Return normalized content words (>= 3 chars) with URLs and mentions stripped."""
    if not text:
        return set()
    cleaned = _URL_STRIP_RE.sub(" ", text).lower()
    return {w for w in _WORD_SPLIT_RE.split(cleaned) if len(w) >= 3 and not w.isdigit()}


def _paraphrase_similarity(left_text, right_text):
    """Return Jaccard word overlap if two posts use different wording for the same story, else None."""
    lw = _content_words(left_text)
    rw = _content_words(right_text)
    if len(lw) < 6 or len(rw) < 6:
        return None
    left_norm = " ".join(w for w in _WORD_SPLIT_RE.split(_URL_STRIP_RE.sub(" ", left_text).lower()) if w)
    right_norm = " ".join(w for w in _WORD_SPLIT_RE.split(_URL_STRIP_RE.sub(" ", right_text).lower()) if w)
    if left_norm == right_norm:
        return None
    union = lw | rw
    if not union:
        return None
    jaccard = len(lw & rw) / len(union)
    if 0.10 <= jaccard <= 0.82:
        return round(jaccard, 2)
    return None


def political_posts(con, src=None):
    """Filter supplied Parquet files (or existing raw_posts view) to political/info-war content."""
    if src is not None:
        raw = con.from_parquet(src, union_by_name=True)
        con.execute(f"create or replace temp view raw_posts as {raw.sql_query()}")
    con.execute(rf"""
        create or replace temp view political_originals as
        select * exclude (body)
        from (select *, {BODY} body from raw_posts)
        where nullif(trim(platform), '') is not null
          and nullif(trim(user_id), '') is not null
          and nullif(trim(post_id), '') is not null
          and isfinite(ts)
          and regexp_matches(body, '{POLITICAL}')
          and not regexp_matches(body, '{OFF_TOPIC}')
          and not regexp_matches(
              lower(text),
              'https?://(?:[a-z0-9-]+[.])*(?:{ADULT_HOSTS})(?:[^a-z0-9.-]|$)'
          )
          and not coalesce(list_has_any(
              list_transform(items, lambda item: regexp_matches(lower(item),
                  '^url:(?:https?://)?(?:[a-z0-9-]+[.])*(?:{ADULT_HOSTS})(?:[^a-z0-9.-]|$)')
              ), [true]), false)
    """)
    con.execute(rf"""
        create or replace temp view political_posts as
        select * from political_originals
        union all
        select r.*
        from raw_posts r
        where r.platform = 'bluesky'
          and nullif(trim(r.user_id), '') is not null
          and nullif(trim(r.post_id), '') is not null
          and isfinite(r.ts)
          and coalesce(trim(r.text), '') = ''
          and len(r.items) = 1
          and regexp_extract(r.items[1], '^{REPOST_RE}$', 1) in (
              select p.post_id
              from political_originals p
              where p.platform = 'bluesky'
          )
    """)


def _rows(con, query, params=None):
    result = con.execute(query, params) if params is not None else con.execute(query)
    fields = [column[0] for column in result.description]
    return [dict(zip(fields, row)) for row in result.fetchall()]


def _prepare(con, source, min_posts):
    cols = set(con.sql("from political_posts limit 0").columns)
    provenance_cases = [
        f"when platform = '{platform}' and provenance = '{name}' then '{name}'"
        for name, (platform, _) in SOURCES.items()
    ]
    recorded_source = "source" if "source" in cols else "null::varchar"
    labels = ", ".join(
        name if name in cols else f"null::{dtype} as {name}"
        for name, dtype in (("label", "boolean"), ("label_ua", "boolean"), ("category", "varchar"))
    )
    con.execute(f"""
        create temp table posts as
        with raw as (
            select platform, user_id, post_id, thread, ts, coalesce(text, '') text, items, {labels},
                {POST_THREAD} post_thread,
                coalesce(?, {recorded_source}) provenance
            from political_posts
        ), identified as (
            select *, case {' '.join(provenance_cases)}
                else 'unverified' end as source
            from raw
        )
        select * exclude (provenance),
            row_number() over (order by platform, source, user_id, post_thread, post_id) as record_id
        from identified
        qualify row_number() over (
            partition by platform, source, user_id, post_thread, post_id
            order by ts, text, thread, items, label, label_ua, category
        ) = 1
    """, [source])
    # Unpack any legacy Telegram rich-text entity arrays ([{'type': 'bold', 'text': '...'}]) losslessly.
    rich_rows = con.execute("""
        select record_id, text from posts
        where platform = 'telegram'
          and starts_with(ltrim(text), '[')
          and ends_with(rtrim(text), ']')
    """).fetchall()
    if rich_rows:
        cleaned = [(rid, unpack_telegram_text(txt)) for rid, txt in rich_rows]
        con.execute("create temp table cleaned_tg (record_id bigint, clean_text varchar)")
        con.executemany("insert into cleaned_tg values (?, ?)", cleaned)
        con.execute("""
            update posts set text = c.clean_text
            from cleaned_tg c where posts.record_id = c.record_id
        """)
    con.execute(f"alter table posts add column body varchar")
    con.execute(f"update posts set body = {BODY}")
    con.execute("""
        create temp table active_accounts as
        select platform, source, user_id
        from posts
        group by all
        having count(*) >= ?
    """, [min_posts])


def _matching_pairs(con, window_seconds, repost_window_seconds=REPOST_WINDOW_SECONDS):
    con.execute(rf"""
        create temp macro clean_url(url) as (
            regexp_replace(
                regexp_replace(regexp_replace(url, '^(?:url:)?(?:https?://)?(?:www[.])?', '', 'i'),
                    '#.*$', ''), '[),.;!\]}}]+$', '')
        )
    """)
    con.execute(r"""
        create temp macro url_key(url) as (
            lower(regexp_extract(url, '^([^/?]+)', 1))
            || regexp_replace(regexp_replace(url, '^[^/?]+', ''), '/+(\?|$)', '\1')
        )
    """)
    con.execute(rf"""
        create temp table signals as
        with active_posts as (
            select p.*, {NORMALIZED} normalized
            from posts p join active_accounts a using (platform, source, user_id)
        ), shared as (
            select platform, source, user_id, ts, record_id,
                'reused text' kind, md5(normalized) signal
            from active_posts
            where length(normalized) >= 35 and len(string_split(normalized, ' ')) >= 5
            union all
            select platform, source, user_id, ts, record_id, 'shared URL' kind, signal
            from (
                select platform, source, user_id, ts, record_id,
                    unnest(list_distinct(text_urls || list_filter(item_urls, lambda url:
                        not list_has_any(
                            list_transform(text_urls, lambda original: lower(split_part(original, '?', 1))),
                            [lower(split_part(url, '?', 1))])
                    ))) signal
                from (
                    select *, list_transform(regexp_extract_all(text, '{URL_RE}', 0, 'i'),
                               lambda url: url_key(clean_url(url))) text_urls,
                        list_transform(
                            list_filter(coalesce(items, []::varchar[]), lambda item: starts_with(lower(item), 'url:')),
                            lambda url: url_key(clean_url(url))) item_urls
                    from active_posts
                )
            )
            where regexp_matches(signal, '^[a-z0-9.-]+(?::[0-9]+)?/[^/]', 'i')
              and not regexp_matches(lower(signal),
                  '^(?:t[.]co|bit[.]ly|tinyurl[.]com|ow[.]ly|buff[.]ly|lnkd[.]in|fb[.]me|goo[.]gl)/')
              and not regexp_matches(lower(signal),
                  '^(?:(?:m[.])?youtube[.]com/watch|facebook[.]com/sharer[.]php|google[.]com/url|t[.]me/share/url)$')
            union all
            select platform, source, user_id, ts, record_id, 'shared repost' kind,
                regexp_extract(item, '^{REPOST_RE}$', 1) signal
            from active_posts, unnest(items) as target(item)
            where platform = 'bluesky' and coalesce(trim(text), '') = ''
              and regexp_full_match(item, '{REPOST_RE}')
        ), bounded as (
            select platform, source, kind, signal
            from shared group by all having count(distinct user_id) between 2 and {MAX_FAN}
        )
        select s.* from shared s join bounded using (platform, source, kind, signal)
    """)
    con.execute("""
        create temp table timed_hits as
        select a.platform, a.source, a.user_id left_user, b.user_id right_user,
            a.kind, a.signal, a.record_id left_record, b.record_id right_record,
            abs(epoch(a.ts) - epoch(b.ts)) gap_seconds
        from signals a join signals b using (platform, source, kind, signal)
        where a.user_id < b.user_id
          and b.ts between a.ts - to_seconds(?) and a.ts + to_seconds(?)
          and (a.kind <> 'shared repost' or abs(epoch(a.ts) - epoch(b.ts)) <= ?)
        qualify row_number() over (
            partition by a.platform, a.source, a.user_id, b.user_id, a.kind, a.signal
            order by gap_seconds, least(a.ts, b.ts), a.record_id, b.record_id
        ) = 1
    """, [window_seconds, window_seconds, repost_window_seconds])
    con.execute(f"""
        create temp table corroborated_hits as
        with channel_posts as (
            select s.platform, s.source, s.signal, s.user_id, p.thread,
                arg_min(s.record_id, (s.ts, s.record_id)) record_id, min(s.ts) ts
            from signals s join posts p using (record_id)
            where s.platform = 'telegram' and s.kind = 'reused text'
              and nullif(trim(p.thread), '') is not null
              and length({NORMALIZED}) >= {MIN_TELEGRAM_TEMPLATE_LENGTH}
              and len(string_split({NORMALIZED}, ' ')) >= 6
            group by all
        ), cross_channel_hits as (
            select a.platform, a.source, a.user_id left_user, b.user_id right_user,
                'cross-channel text' kind, a.signal, a.record_id left_record, b.record_id right_record,
                abs(epoch(a.ts) - epoch(b.ts)) gap_seconds
            from channel_posts a join channel_posts b using (platform, source, signal)
            where a.user_id < b.user_id and a.thread <> b.thread
            qualify row_number() over (
                partition by a.platform, a.source, a.user_id, b.user_id, a.signal
                order by gap_seconds, a.record_id, b.record_id
            ) = 1
        ), hits as (
            select *, false cross_channel from timed_hits
            union all
            select *, true cross_channel from cross_channel_hits
        ), supported as (
            select * from hits
            window pair as (partition by platform, source, left_user, right_user, cross_channel)
            qualify count(*) over pair >= {MIN_SIGNAL_EVENTS}
                and count(distinct left_record) over pair >= {MIN_SIGNAL_EVENTS}
                and count(distinct right_record) over pair >= {MIN_SIGNAL_EVENTS}
        )
        select * exclude (cross_channel)
        from supported
        qualify row_number() over (
            partition by platform, source, left_user, right_user,
                case when cross_channel then 'reused text' else kind end, signal
            order by cross_channel desc
        ) = 1
    """)
    con.execute("""
        create temp table corroborated_pairs as
        select platform, source, left_user, right_user, count(*) matching_signals
        from corroborated_hits group by all
    """)


def _groups(con, resolution=LEIDEN_RESOLUTION):
    """Cluster linked accounts with Leiden (CPM) and record all group memberships."""
    edges_by_dataset = defaultdict(list)
    for platform, source, left, right, count in con.execute(
        "select * from corroborated_pairs order by platform, source, left_user, right_user"
    ).fetchall():
        edges_by_dataset[platform, source].append((left, right, count))

    groups = []
    members = []
    for (platform, source), edges in edges_by_dataset.items():
        graph = igraph.Graph.TupleList(edges, directed=False, edge_attrs=["matching_signals"])
        weights = [min(count, MAX_EDGE_WEIGHT) for count in graph.es["matching_signals"]]
        with LEIDEN_LOCK:
            igraph.set_random_number_generator(Random(0))
            try:
                partition = graph.community_leiden(
                    objective_function="CPM",
                    weights=weights,
                    resolution=resolution,
                    n_iterations=5,
                )
            finally:
                igraph.set_random_number_generator(None)
        membership = partition.membership
        counts = defaultdict(lambda: [0, 0])
        for edge in graph.es:
            left, right = edge.tuple
            left_group = membership[left]
            if left_group == membership[right]:
                counts[left_group][0] += 1
                counts[left_group][1] += edge["matching_signals"]
        names = graph.vs["name"]
        for cluster_index, cluster in enumerate(partition):
            accounts = sorted(names[vertex] for vertex in cluster)
            if len(accounts) < MIN_GROUP_SIZE:
                continue
            group_id = len(groups) + 1
            pair_count, matching_signals = counts[cluster_index]
            groups.append({
                "id": group_id,
                "platform": platform,
                "source": source,
                "accounts": accounts,
                "corroborated_pairs": pair_count,
                "pair_density": pair_count / (len(accounts) * (len(accounts) - 1) / 2),
                "matching_signals": matching_signals,
                "signals_per_account": matching_signals / len(accounts),
            })
            members.extend((platform, source, account, group_id) for account in accounts)

    con.execute("create temp table members (platform varchar, source varchar, user_id varchar, group_id integer)")
    if members:
        con.executemany("insert into members values (?, ?, ?, ?)", members)
    return groups


def _validation(con, groups):
    """Compute honest dataset-wide ground-truth validation across ALL detected groups."""
    val = {}
    # Telegram validation against independent EPFL USENIX Security 2025 labels
    tg_base = con.execute("""
        with a as (
            select p.user_id, bool_or(p.label) is_ru, bool_or(p.label_ua) is_ua
            from posts p join active_accounts aa using (platform, source, user_id)
            where p.source = 'telegram_research'
            group by 1
        )
        select count(*), count(*) filter (where is_ru), count(*) filter (where is_ua),
               count(*) filter (where is_ru or is_ua)
        from a
    """).fetchone()
    if tg_base and tg_base[0] > 0:
        tg_det = con.execute("""
            with u as (
                select distinct m.user_id
                from members m where m.source = 'telegram_research'
            ), lab as (
                select p.user_id, bool_or(p.label) is_ru, bool_or(p.label_ua) is_ua
                from posts p where p.source = 'telegram_research'
                group by 1
            )
            select count(*), count(*) filter (where is_ru), count(*) filter (where is_ua),
                   count(*) filter (where is_ru or is_ua)
            from u join lab using (user_id)
        """).fetchone()
        base_rate = tg_base[3] / tg_base[0]
        precision = tg_det[3] / tg_det[0] if tg_det[0] else 0.0
        val["telegram_research"] = {
            "active_accounts": tg_base[0],
            "labeled_base_accounts": tg_base[3],
            "base_rate": round(base_rate, 4),
            "detected_groups": sum(1 for g in groups if g["source"] == "telegram_research"),
            "detected_accounts": tg_det[0],
            "labeled_detected_accounts": tg_det[3],
            "pro_ru_detected": tg_det[1],
            "pro_ua_detected": tg_det[2],
            "precision": round(precision, 4),
            "lift_over_active_base": round(precision / base_rate, 1) if base_rate else 0.0,
        }

    # X IRA validation: operational category purity across all detected groups
    x_groups = [g for g in groups if g["source"] == "x_ira"]
    if x_groups:
        cats_by_group = defaultdict(Counter)
        for gid, cat, cnt in con.execute("""
            select m.group_id, coalesce(p.category, 'Unknown') cat, count(distinct p.user_id) cnt
            from members m join posts p using (platform, source, user_id)
            where m.source = 'x_ira'
            group by 1, 2
        """).fetchall():
            cats_by_group[gid][cat] += cnt
        total_u = sum(sum(c.values()) for c in cats_by_group.values())
        pure_u = sum(c.most_common(1)[0][1] for c in cats_by_group.values() if c)
        val["x_ira"] = {
            "detected_groups": len(x_groups),
            "detected_accounts": total_u,
            "category_purity": round(pure_u / total_u, 4) if total_u else 0.0,
        }

    # Bluesky summary
    bs_groups = [g for g in groups if g["source"] == "bluesky"]
    if bs_groups:
        val["bluesky"] = {
            "detected_groups": len(bs_groups),
            "detected_accounts": sum(len(g["accounts"]) for g in bs_groups),
        }
    return val


def _schedule_profile(hourly):
    """Turn a 24-hour UTC histogram into a human-readable schedule classification."""
    total = sum(hourly)
    if total == 0:
        return {
            "total_posts": 0,
            "peak_utc_hour": 0,
            "quiet_6h_share": 0.0,
            "moscow_work_share": 0.0,
            "us_daytime_share": 0.0,
            "label": "Insufficient volume",
        }
    peak_hour = max(range(24), key=lambda h: hourly[h])
    quiet_6h = min(sum(hourly[(h + k) % 24] for k in range(6)) for h in range(24)) / total
    moscow_work = sum(hourly[h] for h in range(6, 18)) / total
    us_daytime = sum(hourly[h % 24] for h in range(14, 26)) / total
    if quiet_6h >= 0.14:
        label = "Never sleeps (24/7 posting)"
    elif moscow_work >= 0.60 and quiet_6h < 0.11:
        label = "Russia / Eastern Europe work hours"
    elif us_daytime >= 0.62 and quiet_6h < 0.11:
        label = "US daytime hours"
    else:
        label = "Normal sleep-wake schedule"
    return {
        "total_posts": total,
        "peak_utc_hour": peak_hour,
        "quiet_6h_share": round(quiet_6h, 3),
        "moscow_work_share": round(moscow_work, 3),
        "us_daytime_share": round(us_daytime, 3),
        "label": label,
    }


def _classify_tactic(group):
    """Assign a transparent, rule-based behavioral tactic and review tier."""
    sigs = group["signal_breakdown"]
    total_sigs = sum(sigs.values()) or 1
    cross_share = sigs.get("cross-channel text", 0) / total_sigs
    repost_share = sigs.get("shared repost", 0) / total_sigs
    reused_share = sigs.get("reused text", 0) / total_sigs
    url_share = sigs.get("shared URL", 0) / total_sigs
    med_gap = group["median_gap_seconds"]
    domains = group["domains"]
    top_dom = domains[0] if domains else None
    has_state_media = any(d["is_state_media"] for d in domains)
    has_exclusive = bool(top_dom and top_dom["is_exclusive"])
    mainstream_top = bool(top_dom and top_dom["domain"] in MAINSTREAM_NEWS_DOMAINS)
    paraphrased = group["paraphrased_matches"]

    if paraphrased >= 2 and med_gap <= 15 and has_exclusive and group["platform"] != "x":
        return ("paraphrased_link_ring", "Rewritten links", 1)
    if cross_share >= 0.50:
        return ("cross_channel_script", "Copied across channels", 1)
    if has_exclusive and med_gap <= 60:
        return ("exclusive_domain_ring", "Single-site bot ring", 1)
    if repost_share >= 0.60:
        return ("fast_repost_ring", "Instant repost ring", 2)
    if (
        group["platform"] == "bluesky"
        and not has_exclusive
        and not has_state_media
        and (mainstream_top or (len(domains) >= 2 and med_gap > 15))
    ):
        return ("news_mirror", "News / RSS feed", 2)
    if has_state_media or reused_share >= 0.35 or med_gap <= 30:
        return ("synchronized_blast", "Synced posting squad", 1)
    return ("news_mirror", "News / RSS feed", 2)


def _format_gap(seconds, platform=None):
    if seconds is None:
        return "unknown timing"
    if platform == "x" and seconds == 0:
        return "within the same minute"
    if seconds < 1.5:
        return "within 1 second"
    if seconds < 60:
        return f"{seconds:.0f}s apart"
    if seconds < 3600:
        return f"{seconds / 60:.1f} min apart"
    if seconds < 86400:
        return f"{seconds / 3600:.1f} hours apart"
    return f"{seconds / 86400:.1f} days apart"


def _narrate_group(group):
    """Generate a short, plain-English headline and explanation with zero jargon."""
    n = len(group["accounts"])
    plat = group["platform"]
    tactic = group["tactic"]
    top_dom = group["domains"][0] if group["domains"] else None
    med_gap = group["median_gap_seconds"]
    sched = group["schedule"]
    rl = group.get("researcher_labels")
    cats = group.get("archive_categories") or []
    dominant_cat = cats[0]["category"] if cats else None

    cat_plain = {
        "RightTroll": "US right-wing persona",
        "LeftTroll": "US left-wing persona",
        "NonEnglish": "Russian-language",
        "NewsFeed": "fake local-news",
        "HashtagGamer": "hashtag-game",
        "Fearmonger": "fearmongering",
        "Commercial": "commercial",
    }

    # 1. Plain-English headline
    if tactic == "paraphrased_link_ring" and top_dom:
        headline = f"{n} accounts posting rewritten stories to {top_dom['domain']} {_format_gap(med_gap, plat)}"
    elif tactic == "exclusive_domain_ring" and top_dom:
        headline = f"{n} accounts only promoting {top_dom['domain']} ({top_dom['group_share']:.0%} of links)"
    elif tactic == "cross_channel_script":
        if rl and rl.get("pro_ru_accounts", 0) >= max(2, n * 0.5):
            headline = f"{n} accounts copying the same pro-Russian scripts across Telegram channels"
        elif rl and rl.get("pro_ua_accounts", 0) >= max(2, n * 0.5):
            headline = f"{n} accounts copying the same pro-Ukrainian scripts across Telegram channels"
        else:
            headline = f"{n} accounts copying the same political messages across Telegram channels"
    elif tactic == "synchronized_blast":
        if top_dom and top_dom["is_state_media"]:
            shift_note = " on Russian work hours" if (sched["moscow_work_share"] >= 0.60 and sched["quiet_6h_share"] < 0.11) else ""
            headline = f"{n} accounts pushing {top_dom['domain']} together{shift_note}"
        elif dominant_cat in cat_plain:
            headline = f"{n} {cat_plain[dominant_cat]} accounts posting together on X"
        else:
            headline = f"{n} accounts posting the same political messages {_format_gap(med_gap, plat)}"
    elif tactic == "fast_repost_ring":
        headline = f"{n} accounts reposting the same posts within 15 seconds"
    else:
        dom_txt = f" ({top_dom['domain']})" if top_dom else ""
        headline = f"{n} accounts sharing mainstream news links{dom_txt}"

    # 2. Short, direct plain-English explanation (behavior first, labels strictly separate)
    parts = []
    if tactic == "paraphrased_link_ring" and top_dom:
        parts.append(
            f"All {n} accounts link only to {top_dom['domain']} ({top_dom['outside_accounts']} outside accounts in our data link there), "
            f"posting typically {med_gap:.1f}s apart. On {group['paraphrased_matches']} stories they used different words for the exact same link."
        )
    elif tactic == "cross_channel_script":
        parts.append(
            f"{n} accounts ({group['pair_density']:.0%} linked to each other) posted the exact same long political text "
            f"across different Telegram channels ({group['matching_signals']:,} shared matches)."
        )
    elif tactic == "exclusive_domain_ring" and top_dom:
        parts.append(
            f"{n} accounts focus on {top_dom['domain']} ({top_dom['group_share']:.0%} of links, only {top_dom['outside_accounts']} outside accounts), "
            f"posting typically {med_gap:.0f}s apart."
        )
    elif tactic == "synchronized_blast":
        gap_txt = _format_gap(med_gap, plat)
        dom_note = f" and linking {top_dom['domain']}" if top_dom else ""
        parts.append(
            f"{n} accounts ({group['pair_density']:.0%} linked to each other) posted the same political text or links "
            f"{gap_txt}{dom_note} ({group['matching_signals']:,} shared matches)."
        )
    elif tactic == "fast_repost_ring":
        parts.append(
            f"{n} accounts reposted the exact same posts within 15 seconds of each other ({group['matching_signals']:,} shared matches)."
        )
    else:
        dom_list = ", ".join(d["domain"] for d in group["domains"][:2]) or "news sites"
        parts.append(
            f"These {n} accounts share mainstream news links ({dom_list}) about {med_gap:.0f}s apart — likely normal news bots or RSS feeds."
        )

    if sched["quiet_6h_share"] >= 0.14:
        parts.append(f"They post 24/7 with no sleep break ({sched['quiet_6h_share']:.0%} of posts in their quietest 6 hours).")
    elif sched["moscow_work_share"] >= 0.60 and sched["quiet_6h_share"] < 0.11:
        tz_desc = "St. Petersburg / Moscow daytime" if plat == "x" else "Russia / Eastern Europe daytime"
        parts.append(f"{sched['moscow_work_share']:.0%} of posts land during {tz_desc} (peak {sched['peak_utc_hour']:02d}:00 UTC).")

    # External record kept strictly separate
    if cats:
        cat_str = ", ".join(f"{cat_plain.get(c['category'], c['category'])} ({c['accounts']})" for c in cats[:2])
        parts.append(f"Outside record: known Russian troll archive lists these as {cat_str}.")
    elif rl:
        ru = rl.get("pro_ru_accounts", 0)
        ua = rl.get("pro_ua_accounts", 0)
        tot = rl.get("accounts_with_pro_ru_label", 0)
        if ru > 0 and ua == 0:
            parts.append(f"Outside check: university researchers labeled {ru} of {tot} accounts as pro-Russian propaganda.")
        elif ua > 0 and ru == 0:
            parts.append(f"Outside check: university researchers labeled {ua} of {tot} accounts as pro-Ukrainian propaganda.")
        elif ru > 0 and ua > 0:
            parts.append(f"Outside check: university researchers labeled {ru} pro-Russian and {ua} pro-Ukrainian accounts.")
        else:
            parts.append("Outside check: not labeled in the university dataset — worth manual review.")
    elif plat == "bluesky":
        parts.append("Outside check: no known owner label. Behavior shows they act together, not who runs them.")

    chips = []
    if tactic == "paraphrased_link_ring":
        chips.append(f"Rewritten stories ({group['paraphrased_matches']})")
    if top_dom and top_dom["is_exclusive"]:
        chips.append(f"Only site: {top_dom['domain']}")
    elif top_dom and top_dom["is_state_media"]:
        chips.append(f"State media: {top_dom['domain']}")
    if plat == "x" and med_gap == 0:
        chips.append("Same minute")
    elif med_gap <= 5:
        chips.append(f"~{med_gap:.1f}s apart")
    if group["signal_breakdown"].get("cross-channel text", 0) > 0:
        chips.append("Copied across channels")
    if sched["quiet_6h_share"] >= 0.14:
        chips.append("Never sleeps (24/7)")
    elif sched["moscow_work_share"] >= 0.60 and sched["quiet_6h_share"] < 0.11:
        chips.append("Russia / E. Europe hours")
    if group["pair_density"] >= 0.80:
        chips.append(f"{group['pair_density']:.0%} linked")
    return headline, " ".join(parts), chips


def _profile_and_select(con, groups, per_dataset):
    """Profile all groups with behavioral forensics, rank them, and attach full evidence to selected groups."""
    if not groups:
        return []
    group_map = {g["id"]: g for g in groups}

    # 1. Internal hits summary: median gap & signal breakdown per group
    con.execute("""
        create temp table group_hits as
        select m.group_id, h.*
        from corroborated_hits h
        join members m on m.platform = h.platform and m.source = h.source and m.user_id = h.left_user
        join members r on r.platform = h.platform and r.source = h.source and r.user_id = h.right_user
            and r.group_id = m.group_id
    """)
    med_gaps = dict(con.execute(
        "select group_id, median(gap_seconds) from group_hits group by 1"
    ).fetchall())
    sig_counts = defaultdict(dict)
    for gid, kind, cnt in con.execute(
        "select group_id, kind, count(*) from group_hits group by 1, 2"
    ).fetchall():
        sig_counts[gid][kind] = cnt

    # 2. Paraphrase detection on fast (<= 60s) shared-URL hits
    paraphrase_signals = defaultdict(set)
    paraphrase_by_hit = {}
    for gid, signal, ltext, rtext in con.execute("""
        select h.group_id, h.signal, l.text, r.text
        from (
            select group_id, signal, left_record, right_record, gap_seconds
            from group_hits
            where kind = 'shared URL' and gap_seconds <= 60
            qualify row_number() over (partition by group_id, signal order by gap_seconds, left_record, right_record) = 1
        ) h
        join posts l on l.record_id = h.left_record
        join posts r on r.record_id = h.right_record
    """).fetchall():
        sim = _paraphrase_similarity(ltext, rtext)
        if sim is not None:
            paraphrase_signals[gid].add(signal)
            paraphrase_by_hit[(gid, signal)] = sim

    # 3. 24-hour UTC activity histograms per group
    hourly_map = {gid: [0] * 24 for gid in group_map}
    for gid, hr, cnt in con.execute("""
        select m.group_id, hour(p.ts) hr, count(*) cnt
        from members m join posts p using (platform, source, user_id)
        group by 1, 2
    """).fetchall():
        hourly_map[gid][int(hr)] = cnt

    # 4. Domain concentration + outside-account exclusivity per group
    con.execute("""
        create temp table post_domains as
        select platform, source, user_id,
               regexp_extract(lower(it), '^url:(?:https?://)?(?:www[.])?([^/:?#]+)', 1) dom
        from posts, unnest(coalesce(items, []::varchar[])) as t(it)
        where starts_with(lower(it), 'url:')
    """)
    global_dom_users = {
        (plat, src, dom): cnt
        for plat, src, dom, cnt in con.execute("""
            select platform, source, dom, count(distinct user_id)
            from post_domains where dom <> ''
            group by 1, 2, 3
        """).fetchall()
    }
    group_dom_totals = defaultdict(int)
    group_dom_rows = defaultdict(list)
    for gid, plat, src, dom, posts_cnt, accts_cnt in con.execute("""
        select m.group_id, m.platform, m.source, d.dom, count(*) posts_cnt, count(distinct d.user_id) accts_cnt
        from members m join post_domains d using (platform, source, user_id)
        where d.dom <> ''
        group by 1, 2, 3, 4
    """).fetchall():
        if dom in SHORTENER_DOMAINS:
            continue
        group_dom_totals[gid] += posts_cnt
        group_dom_rows[gid].append((plat, src, dom, posts_cnt, accts_cnt))

    domains_map = {}
    for gid, rows in group_dom_rows.items():
        tot = group_dom_totals[gid] or 1
        rows.sort(key=lambda r: (-r[3], r[2]))
        top_list = []
        for plat, src, dom, posts_cnt, accts_cnt in rows[:3]:
            share = posts_cnt / tot
            outside = max(0, global_dom_users.get((plat, src, dom), accts_cnt) - accts_cnt)
            top_list.append({
                "domain": dom,
                "posts": posts_cnt,
                "accounts": accts_cnt,
                "group_share": round(share, 3),
                "outside_accounts": outside,
                "is_exclusive": bool(share >= 0.50 and outside <= 3 and accts_cnt >= 2 and posts_cnt >= 10),
                "is_state_media": dom in STATE_MEDIA_DOMAINS,
            })
        domains_map[gid] = top_list

    # 5. External archive metadata (kept strictly separate from behavioral signals)
    archive_cats = defaultdict(list)
    for row in _rows(con, """
        select m.group_id, p.category, count(distinct p.user_id) accounts
        from members m join posts p using (platform, source, user_id)
        where m.source = 'x_ira' and p.category is not null
        group by all order by m.group_id, accounts desc, p.category
    """):
        archive_cats[row.pop("group_id")].append(row)

    researcher_labs = {
        row.pop("group_id"): row for row in _rows(con, """
            select m.group_id,
                count(distinct p.user_id) filter (where p.label is not null) as accounts_with_pro_ru_label,
                count(distinct p.user_id) filter (where p.label is true) as pro_ru_accounts,
                count(distinct p.user_id) filter (where p.label_ua is not null) as accounts_with_pro_ua_label,
                count(distinct p.user_id) filter (where p.label_ua is true) as pro_ua_accounts
            from members m join posts p using (platform, source, user_id)
            where m.source = 'telegram_research' group by all
        """)
    }

    # Attach profiles and classify every group
    for g in groups:
        gid = g["id"]
        g["median_gap_seconds"] = round(float(med_gaps.get(gid, 0.0)), 1)
        g["signal_breakdown"] = sig_counts[gid]
        g["paraphrased_matches"] = len(paraphrase_signals[gid])
        g["hourly_utc"] = hourly_map[gid]
        g["schedule"] = _schedule_profile(hourly_map[gid])
        g["domains"] = domains_map.get(gid, [])
        g["archive_categories"] = archive_cats[gid]
        g["researcher_labels"] = researcher_labs.get(gid)
        tactic, tactic_label, tier = _classify_tactic(g)
        g["tactic"] = tactic
        g["tactic_label"] = tactic_label
        g["priority_tier"] = tier
        headline, why, chips = _narrate_group(g)
        g["headline"] = headline
        g["why_flagged"] = why
        g["signals_explained"] = chips

    # Sort: Tier 1 covert/coordinated ops first, with paraphrased rings boosted, then strength
    def _sort_key(g):
        paraphrase_boost = 0 if g["tactic"] == "paraphrased_link_ring" else 1
        return (
            g["priority_tier"],
            paraphrase_boost,
            -g["signals_per_account"],
            -g["pair_density"],
            -len(g["accounts"]),
            g["id"],
        )

    groups.sort(key=_sort_key)

    # Select balanced top groups per dataset so every archive is thoroughly represented
    by_dataset = defaultdict(list)
    for g in groups:
        by_dataset[(g["platform"], g["source"])].append(g)
    selected = []
    for key in sorted(by_dataset):
        selected.extend(by_dataset[key][:per_dataset])
    selected.sort(key=_sort_key)

    # 6. Attach full readable evidence + network topology edges for selected groups
    con.execute("create temp table report_groups (group_id integer)")
    con.executemany("insert into report_groups values (?)", [(g["id"],) for g in selected])

    # Internal topology edges (top 64 strongest edges per group for crisp network graphs)
    edges_by_group = defaultdict(list)
    for gid, left_u, right_u, cnt, top_kind, med_g in con.execute("""
        with agg as (
            select h.group_id, h.left_user, h.right_user, count(*) cnt,
                   arg_max(h.kind, h.gap_seconds * -1) top_kind,
                   median(h.gap_seconds) med_g
            from group_hits h join report_groups rg using (group_id)
            group by 1, 2, 3
        )
        select group_id, left_user, right_user, cnt, top_kind, med_g
        from agg
        qualify row_number() over (partition by group_id order by cnt desc, med_g asc, left_user, right_user) <= 64
        order by group_id, cnt desc
    """).fetchall():
        edges_by_group[gid].append({
            "from": left_u,
            "to": right_u,
            "count": cnt,
            "kind": top_kind,
            "median_gap": round(float(med_g), 1),
        })

    # Resolve original post text for Bluesky shared reposts
    repost_texts = dict(con.execute("""
        select post_id, any_value(text)
        from posts where platform = 'bluesky' and coalesce(trim(text), '') <> ''
        group by 1
    """).fetchall())

    exhibits = defaultdict(list)
    for row in _rows(con, f"""
        with hits as (
            select h.* from group_hits h join report_groups rg using (group_id)
        ), coverage as (
            select group_id, kind, signal, count(distinct user_id) accounts
            from (
                select group_id, kind, signal, left_user user_id from hits
                union all
                select group_id, kind, signal, right_user user_id from hits
            )
            group by all
        ), examples as (
            select group_id, kind, signal, left_record, right_record, gap_seconds
            from hits
            qualify row_number() over (
                partition by group_id, kind, signal order by gap_seconds, left_record, right_record
            ) = 1
        ), selected_hits as (
            select *
            from coverage join examples using (group_id, kind, signal)
            qualify row_number() over (
                partition by group_id order by accounts desc, gap_seconds, kind, signal
            ) <= {MAX_EXHIBITS * 2}
        )
        select group_id, kind, signal, accounts, gap_seconds,
            l.user_id left_user, l.post_id left_post, l.thread left_thread, l.ts left_time, l.text left_text,
            r.user_id right_user, r.post_id right_post, r.thread right_thread, r.ts right_time, r.text right_text
        from selected_hits
        join posts l on l.record_id = left_record
        join posts r on r.record_id = right_record
        order by group_id, accounts desc, gap_seconds, kind, signal
    """):
        gid = row.pop("group_id")
        sig = row.pop("signal")
        kind = row["kind"]
        ltext = (row.pop("left_text") or "").strip()
        rtext = (row.pop("right_text") or "").strip()
        sim = paraphrase_by_hit.get((gid, sig)) if kind == "shared URL" else None
        if kind in ("reused text", "cross-channel text"):
            example = ltext[:320]
        elif kind == "shared repost":
            example = repost_texts.get(sig, sig)[:320]
        else:
            example = sig
        row["example"] = example
        row["signal"] = sig
        if sim is not None:
            row["paraphrased"] = True
            row["word_overlap"] = sim
        row["posts"] = [
            {
                "account": row.pop("left_user"),
                "id": row.pop("left_post"),
                "thread": row.pop("left_thread"),
                "time_utc": _timestamp(row.pop("left_time")),
                "text": ltext[:360] if ltext else None,
            },
            {
                "account": row.pop("right_user"),
                "id": row.pop("right_post"),
                "thread": row.pop("right_thread"),
                "time_utc": _timestamp(row.pop("right_time")),
                "text": rtext[:360] if rtext else None,
            },
        ]
        exhibits[gid].append(row)

    for g in selected:
        gid = g["id"]
        # Prioritize paraphrased examples first, then account coverage
        ev = exhibits[gid]
        ev.sort(key=lambda r: (0 if r.get("paraphrased") else 1, -r["accounts"], r["gap_seconds"]))
        g["evidence"] = ev[:MAX_EXHIBITS]
        g["graph_edges"] = edges_by_group[gid]
    return selected


def _timestamp(timestamp):
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC).isoformat()


def detect(src, *, source=None, min_posts=5, window_minutes=5, per_dataset=45, resolution=LEIDEN_RESOLUTION):
    """Run behavioral coordination detection and forensic profiling across local Parquet archives."""
    if min(min_posts, window_minutes, per_dataset) < 1:
        raise ValueError("Detection thresholds must be positive")
    if source is not None and source not in SOURCES:
        raise ValueError(f"Unknown source {source!r}")
    with duckdb.connect() as con:
        political_posts(con, src)
        _prepare(con, source, min_posts)
        _matching_pairs(con, window_minutes * 60)
        all_groups = _groups(con, resolution=resolution)
        validation = _validation(con, all_groups)
        shown_groups = _profile_and_select(con, all_groups, per_dataset=per_dataset)
        datasets = _rows(con, """
            select platform, source, count(*) posts, count(distinct user_id) accounts,
                count(distinct a.user_id) active_accounts
            from posts p left join active_accounts a using (platform, source, user_id)
            group by platform, source order by platform, source
        """)
        group_counts = Counter((g["platform"], g["source"]) for g in all_groups)
        shown_counts = Counter((g["platform"], g["source"]) for g in shown_groups)
        tier1_counts = Counter((g["platform"], g["source"]) for g in all_groups if g["priority_tier"] == 1)
        for dataset in datasets:
            key = (dataset["platform"], dataset["source"])
            dataset["raw_posts"] = RAW_ARCHIVE_TOTALS.get(key)
            dataset["candidate_groups"] = group_counts[key]
            dataset["high_priority_groups"] = tier1_counts[key]
            dataset["groups_shown"] = shown_counts[key]
        if "bluesky" in validation:
            bs_all = [g for g in all_groups if g["source"] == "bluesky"]
            validation["bluesky"]["high_priority_groups"] = sum(1 for g in bs_all if g["priority_tier"] == 1)
            validation["bluesky"]["news_mirror_groups"] = sum(1 for g in bs_all if g["tactic"] == "news_mirror")
            validation["bluesky"]["repost_groups"] = sum(1 for g in bs_all if g["tactic"] == "fast_repost_ring")
        return {
            "thresholds": {
                "min_political_posts": min_posts,
                "window_minutes": window_minutes,
                "repost_window_seconds": REPOST_WINDOW_SECONDS,
                "min_accounts": MIN_GROUP_SIZE,
                "min_signals_per_pair": MIN_SIGNAL_EVENTS,
                "min_telegram_template_chars": MIN_TELEGRAM_TEMPLATE_LENGTH,
                "max_accounts_per_signal": MAX_FAN,
                "leiden_resolution": resolution,
                "max_pair_weight": MAX_EDGE_WEIGHT,
            },
            "datasets": datasets,
            "validation": validation,
            "total_groups": len(all_groups),
            "groups": shown_groups,
        }


def build_site_payload(report):
    """Build a privacy-aware, rich, readable dataset for the unified PropNET website.

    Public FiveThirtyEight IRA handles on X are kept verbatim (documented state-troll archive).
    Telegram and Bluesky account identifiers are consistently aliased (TG-0001, BS-0001),
    while preserving clean post excerpts, domains, schedules, and forensic signals so every case
    is immediately readable and explainable without importing a local file.
    """
    prefixes = {"telegram": "TG", "bluesky": "BS"}
    aliases = {}
    for platform in ("telegram", "bluesky"):
        ids = sorted({
            acct
            for g in report["groups"]
            if g["platform"] == platform
            for acct in g["accounts"]
        })
        rng = Random(42)
        rng.shuffle(ids)
        prefix = prefixes[platform]
        aliases[platform] = {uid: f"{prefix}-{i:04d}" for i, uid in enumerate(ids, start=1)}

    def _alias(platform, uid):
        return aliases[platform].get(uid, uid) if platform in aliases else uid

    site_groups = []
    for g in report["groups"]:
        plat = g["platform"]
        ev_out = []
        for row in g["evidence"]:
            posts_out = []
            for p in row["posts"]:
                entry = {
                    "account": _alias(plat, p["account"]),
                    "time_utc": p["time_utc"],
                }
                if p.get("text"):
                    entry["text"] = p["text"][:320]
                if plat == "x" and p.get("id"):
                    entry["id"] = p["id"]
                elif plat == "telegram" and p.get("thread"):
                    entry["thread"] = p["thread"]
                posts_out.append(entry)
            item = {
                "kind": row["kind"],
                "accounts": row["accounts"],
                "gap_seconds": round(float(row["gap_seconds"]), 1),
                "example": (row.get("example") or "")[:300],
                "posts": posts_out,
            }
            if row.get("paraphrased"):
                item["paraphrased"] = True
                item["word_overlap"] = row.get("word_overlap")
            ev_out.append(item)

        edges_out = [
            {
                "from": _alias(plat, e["from"]),
                "to": _alias(plat, e["to"]),
                "count": e["count"],
                "kind": e["kind"],
                "median_gap": e["median_gap"],
            }
            for e in g.get("graph_edges", [])
        ]

        site_groups.append({
            "id": g["id"],
            "platform": plat,
            "source": g["source"],
            "tactic": g["tactic"],
            "tactic_label": g["tactic_label"],
            "priority_tier": g["priority_tier"],
            "headline": g["headline"],
            "why_flagged": g["why_flagged"],
            "signals_explained": g["signals_explained"],
            "accounts": sorted(_alias(plat, a) for a in g["accounts"]),
            "corroborated_pairs": g["corroborated_pairs"],
            "pair_density": round(float(g["pair_density"]), 4),
            "matching_signals": g["matching_signals"],
            "signals_per_account": round(float(g["signals_per_account"]), 2),
            "median_gap_seconds": g["median_gap_seconds"],
            "paraphrased_matches": g["paraphrased_matches"],
            "signal_breakdown": g["signal_breakdown"],
            "hourly_utc": g["hourly_utc"],
            "schedule": g["schedule"],
            "domains": g["domains"],
            "archive_categories": g["archive_categories"],
            "researcher_labels": g["researcher_labels"],
            "evidence": ev_out,
            "graph_edges": edges_out,
        })

    # Pick the strongest concrete spotlight case from each archive for the 4-minute demo
    def _pick_spotlight(predicate):
        return next((g["id"] for g in site_groups if predicate(g)), None)

    spotlights = {
        "bluesky": _pick_spotlight(lambda g: g["platform"] == "bluesky" and g["tactic"] == "paraphrased_link_ring")
        or _pick_spotlight(lambda g: g["platform"] == "bluesky"),
        "telegram_ru": _pick_spotlight(
            lambda g: g["platform"] == "telegram"
            and (g.get("researcher_labels") or {}).get("pro_ru_accounts", 0) >= 50
            and g["schedule"]["quiet_6h_share"] >= 0.13
        ) or _pick_spotlight(lambda g: g["platform"] == "telegram" and (g.get("researcher_labels") or {}).get("pro_ru_accounts", 0) > 0),
        "telegram_ua": _pick_spotlight(
            lambda g: g["platform"] == "telegram"
            and (g.get("researcher_labels") or {}).get("pro_ua_accounts", 0) >= 5
        ),
        "x_ru": _pick_spotlight(
            lambda g: g["platform"] == "x"
            and g["schedule"]["moscow_work_share"] >= 0.80
            and g["pair_density"] >= 0.70
            and any(d["is_state_media"] for d in g["domains"])
        ) or _pick_spotlight(
            lambda g: g["platform"] == "x"
            and g["schedule"]["moscow_work_share"] >= 0.80
            and any(d["is_state_media"] for d in g["domains"])
        ) or _pick_spotlight(lambda g: g["platform"] == "x"),
        "x_us": _pick_spotlight(
            lambda g: g["platform"] == "x"
            and any(c["category"] == "RightTroll" for c in g["archive_categories"])
            and len(g["accounts"]) >= 20
        ),
        "x_left": _pick_spotlight(
            lambda g: g["platform"] == "x"
            and any(c["category"] == "LeftTroll" for c in g["archive_categories"])
            and len(g["accounts"]) >= 20
        ),
    }

    return {
        "thresholds": report["thresholds"],
        "datasets": report["datasets"],
        "validation": report["validation"],
        "total_groups": report["total_groups"],
        "spotlights": spotlights,
        "groups": site_groups,
    }


def write_site_bundle(report, target: Path):
    payload = build_site_payload(report)
    serialized = json.dumps(payload, allow_nan=False, ensure_ascii=False, separators=(",", ":"))
    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".site-", dir=target.parent) as tmp:
        staging = Path(tmp) / target.name
        staging.write_text(f"window.PROPNET_REPORT = {serialized};\n", encoding="utf-8")
        staging.replace(target)
    return len(payload["groups"])


def render(report):
    """Render a standalone, self-contained local HTML summary report."""
    platform_names = {"x": "X", "telegram": "Telegram", "bluesky": "Bluesky"}
    sections = []
    for g in report["groups"]:
        plat = g["platform"]
        chips = " ".join(f'<span class="chip">{escape(c)}</span>' for c in g["signals_explained"])
        ev_items = []
        for row in g["evidence"]:
            posts_html = "".join(
                f'<div class="post"><strong>{escape(p["account"])}</strong> '
                f'<small>{escape(p["time_utc"])}</small>'
                + (f'<blockquote>{escape(p["text"])}</blockquote>' if p.get("text") else "")
                + "</div>"
                for p in row["posts"]
            )
            tag = " · Paraphrased wording" if row.get("paraphrased") else ""
            ev_items.append(
                f'<li><strong>{escape(row["kind"])}</strong> · {row["accounts"]} accounts · '
                f'{_format_gap(row["gap_seconds"], plat)}{tag}<div class="pair">{posts_html}</div></li>'
            )
        sections.append(
            f'<article><h2>{escape(platform_names.get(plat, plat))} · Group {g["id"]} — {escape(g["headline"])}</h2>'
            f'<p class="why">{escape(g["why_flagged"])}</p>'
            f'<p class="chips">{chips}</p>'
            f'<ol>{"".join(ev_items)}</ol></article>'
        )
    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PropNET Coordination Report</title>
<style>
body{{background:#f6f7f9;color:#1b1f24;font:15px/1.55 system-ui,sans-serif;margin:0}}
main{{max-width:920px;margin:auto;padding:2rem 1rem}}
article{{background:#fff;border:1px solid #d9dde3;border-radius:6px;padding:1.2rem 1.4rem;margin:1rem 0}}
h2{{margin:0 0 .5rem;font-size:1.15rem}}
.why{{color:#3d434b;margin:0 0 .7rem}}
.chip{{display:inline-block;background:#eef5fd;color:#13294b;border:1px solid #c5daf4;border-radius:3px;padding:2px 7px;font-size:.8rem;margin:0 4px 4px 0}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:.7rem;margin-top:.4rem}}
blockquote{{margin:.35rem 0 0;padding:.45rem .65rem;background:#f6f7f9;border-left:3px solid #1a5fb4;white-space:pre-wrap}}
</style>
<main><h1>PropNET Local Coordination Report</h1>
<p>Showing {len(report["groups"])} of {report["total_groups"]} candidate groups. Load this JSON in <code>docs/index.html</code> for interactive exploration.</p>
{"".join(sections)}</main></html>
"""


def _positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("posts", nargs="?", default="data/focused/*.parquet", help="Parquet path or glob")
    parser.add_argument("--source", choices=SOURCES, help="archive name for one verified input")
    parser.add_argument("--min-posts", type=_positive_int, default=5, help="minimum filtered posts per account")
    parser.add_argument("--window-minutes", type=_positive_int, default=5, help="maximum gap for timed matches")
    parser.add_argument("--per-dataset", type=_positive_int, default=45, help="maximum groups kept per archive")
    parser.add_argument("--resolution", type=float, default=LEIDEN_RESOLUTION, help="Leiden CPM resolution")
    parser.add_argument("--output", type=Path, default=Path("data/influence_report.html"), help="local HTML report")
    parser.add_argument("--json", type=Path, default=Path("data/influence_report.json"), help="local full JSON report")
    parser.add_argument("--site", type=Path, help="export website JS bundle (e.g. docs/site-data.js)")
    args = parser.parse_args()
    try:
        result = detect(
            args.posts,
            source=args.source,
            min_posts=args.min_posts,
            window_minutes=args.window_minutes,
            per_dataset=args.per_dataset,
            resolution=args.resolution,
        )
    except (duckdb.Error, ValueError) as error:
        parser.exit(1, f"detect: {error}\n")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render(result), encoding="utf-8")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.site:
        written = write_site_bundle(result, args.site)
        print(f"Wrote {written} website cases -> {args.site}")
    print(f'Found {result["total_groups"]} total groups ({len(result["groups"])} profiled). Wrote {args.json}')


if __name__ == "__main__":
    main()
