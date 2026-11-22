"""Ingest and filter political posts from Telegram, X (IRA), and Bluesky archives."""

import argparse
import ast
from glob import glob
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb

from detect import POST_IDENTITY, political_posts, unpack_telegram_text

ARCHIVES = {
    "telegram": ("telegram_research", ("dataset_v2.csv", "dataset_v2.csv.zst")),
    "x": ("x_ira", ("data/x_ira/IRAhandle_tweets_*.csv", "data/x_ira/IRAhandle_tweets_*.csv.zst")),
    "bluesky": ("bluesky", ("data/backfill/*.parquet", "data/live/*.parquet")),
}

URLS = r"""list_transform(
    regexp_extract_all(coalesce({column}, ''), '(?i)https?://[^\s<>"\x27]+'),
    lambda url: 'url:' || regexp_replace(url, '(?i)^https?://', '')
)"""

TELEGRAM_SQL = f"""
    select 'telegram' as platform,
           message_id as post_id,
           from_id as user_id,
           date::timestamp as ts,
           coalesce(text, '') as text,
           reply_to_message_id as reply_to,
           channel as thread,
           ru_pa::boolean as label,
           ua_pa::boolean as label_ua,
           null::varchar as category,
           list_distinct({URLS.format(column="text")}) as items
    from archive_csv
    where nullif(trim(from_id), '') is not null
      and nullif(trim(message_id), '') is not null
      and date is not null
"""

X_IRA_SQL = f"""
    select 'x' as platform,
           tweet_id as post_id,
           lower(author) as user_id,
           strptime(publish_date, '%m/%d/%Y %H:%M') as ts,
           content as text,
           null::varchar as reply_to,
           null::varchar as thread,
           null::boolean as label,
           null::boolean as label_ua,
           account_category as category,
           list_distinct({URLS.format(column="content")} || list_transform(
               list_filter([tco1_step1, tco2_step1, tco3_step1],
                           lambda url: regexp_matches(url, '(?i)^https?://')),
               lambda url: 'url:' || regexp_replace(url, '(?i)^https?://', '')
           )) as items
    from archive_csv
    where nullif(trim(author), '') is not null
      and nullif(trim(tweet_id), '') is not null
      and publish_date is not null
"""


def _extract_telegram_links(raw):
    """Extract hrefs hidden inside Telegram rich-text entity arrays."""
    if not raw:
        return []
    s = raw.strip()
    if not (s.startswith("[") and s.endswith("]")):
        return []
    try:
        parts = ast.literal_eval(s)
    except (SyntaxError, ValueError):
        return []
    if not isinstance(parts, list):
        return []
    links = []
    for part in parts:
        if isinstance(part, dict):
            href = part.get("href") or (part.get("text") if part.get("type") == "link" else None)
            if isinstance(href, str) and href.lower().startswith(("http://", "https://")):
                links.append("url:" + href.split("://", 1)[1])
    return links


def _resolve_inputs(platform, custom_inputs):
    archive, defaults = ARCHIVES[platform]
    if custom_inputs:
        patterns = custom_inputs
        is_default = False
    elif platform == "bluesky":
        patterns = defaults
        is_default = True
    else:
        plain, packed = defaults
        patterns = (plain,) if glob(plain) else (packed,)
        is_default = True

    files = []
    for pattern in patterns:
        path = Path(pattern).expanduser()
        if path.is_file():
            files.append(path.resolve())
        else:
            files.extend(Path(p).resolve() for p in sorted(glob(str(path))) if Path(p).is_file())
    files = sorted(set(files))
    if not files:
        raise ValueError(f"No input files match {', '.join(patterns)}")
    return files, is_default, archive


def ingest(platform, inputs=(), output=None, source=None):
    """Import, clean, and filter political posts for one platform archive."""
    files, is_default, archive = _resolve_inputs(platform, inputs)
    if source is not None and source != archive:
        raise ValueError(f"For {platform}, use --source {archive}.")
    provenance = source or (archive if is_default or platform == "bluesky" else "unverified")

    target = Path(output or Path("data/focused") / f"{platform}.parquet").expanduser().resolve()
    if target.suffix.lower() != ".parquet":
        raise ValueError("The output path must end in .parquet.")
    if target in files:
        raise ValueError("Choose an output path different from the input files.")
    target.parent.mkdir(parents=True, exist_ok=True)

    paths = [str(p) for p in files]
    with duckdb.connect() as con, TemporaryDirectory(prefix=".ingest-", dir=target.parent) as tmp:
        if platform == "bluesky":
            raw = con.read_parquet(paths, union_by_name=True)
            cols = set(raw.columns)
            raw.create_view("bsky_in")
            input_rows = con.execute("select count(*) from bsky_in").fetchone()[0]
            label_ua = "label_ua" if "label_ua" in cols else "null::boolean as label_ua"
            category = "category" if "category" in cols else "null::varchar as category"
            con.execute(f"""
                create temp view raw_posts as
                select platform, post_id, user_id, ts, text, reply_to, thread,
                       label, {label_ua}, {category}, items, ?::varchar as source
                from bsky_in
                where platform = 'bluesky'
            """, [provenance])
        else:
            con.read_csv(paths, header=True, all_varchar=True, union_by_name=True).create_view("archive_csv")
            input_rows = con.execute("select count(*) from archive_csv").fetchone()[0]
            con.sql(TELEGRAM_SQL if platform == "telegram" else X_IRA_SQL).create_view("archive_posts")
            con.execute(
                "create temp view raw_posts as select *, ?::varchar as source from archive_posts",
                [provenance],
            )

        political_posts(con)
        staged = Path(tmp) / target.name
        con.execute(f"""
            create temp table filtered as
            select *, row_number() over () as _rid
            from political_posts
            qualify row_number() over (
                partition by source, {POST_IDENTITY}
                order by ts, text, reply_to, label, label_ua, category, items
            ) = 1
        """)
        if platform == "telegram":
            rich_rows = con.execute("""
                select _rid, text from filtered
                where starts_with(ltrim(coalesce(text, '')), '[')
                  and ends_with(rtrim(coalesce(text, '')), ']')
            """).fetchall()
            if rich_rows:
                cleaned = [
                    (rid, unpack_telegram_text(txt), _extract_telegram_links(txt))
                    for rid, txt in rich_rows
                ]
                con.execute("create temp table cleaned_tg (_rid bigint, clean_text varchar, rich_links varchar[])")
                con.executemany("insert into cleaned_tg values (?, ?, ?)", cleaned)
                con.execute("""
                    update filtered
                    set text = c.clean_text,
                        items = list_distinct(coalesce(filtered.items, []::varchar[]) || c.rich_links)
                    from cleaned_tg c where filtered._rid = c._rid
                """)
        con.sql("select * exclude (_rid) from filtered").write_parquet(str(staged), compression="zstd")
        kept_rows, kept_users = con.execute(
            "select count(*), count(distinct user_id) from read_parquet(?)", [str(staged)]
        ).fetchone()
        staged.replace(target)
    return target, input_rows, kept_rows, kept_users


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=ARCHIVES)
    parser.add_argument("inputs", nargs="*", help="optional CSV, CSV.zst, or Parquet path(s) / quoted globs")
    parser.add_argument("--output", type=Path, help="output Parquet path (default: data/focused/<platform>.parquet)")
    parser.add_argument("--source", choices=[archive for archive, _ in ARCHIVES.values()],
                        help="archive provenance tag for verified custom input")
    args = parser.parse_args()
    try:
        target, total, kept, users = ingest(args.platform, args.inputs, args.output, args.source)
    except (duckdb.Error, OSError, ValueError) as exc:
        parser.exit(1, f"Could not import {args.platform}: {exc}\n")
    print(f"Kept {kept:,} of {total:,} posts from {users:,} accounts -> {target}")


if __name__ == "__main__":
    main()
