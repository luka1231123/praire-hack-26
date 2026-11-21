"""Convert a raw dataset into the shared posts table.

Usage:
  uv run ingest.py telegram dataset_v2.csv        -> data/posts.parquet
  uv run ingest.py x "data/x_ira/*.csv"            -> data/posts_x.parquet   (FiveThirtyEight IRA tweets)

Shared columns (Bluesky uses the same ones):
  platform, post_id, user_id, ts, text, reply_to, thread, label, category, items
label    = True/False ground truth when known (Telegram ru_pa), else NULL.
category = known group of the account when known (IRA account_category), else NULL.
items    = links, #hashtags and @mentions in the post.
"""
import sys
import duckdb

# links, hashtags, mentions in text -> lowercase items; "https://www.x.com/a" -> "url:x.com/a"
ITEMS = r"""list_filter(list_distinct(list_transform(
  regexp_extract_all(coalesce(COL, ''), '(https?://[^\s?#]+|#[\p{L}\p{N}_]+|@[\p{L}\p{N}_]+)'),
  lambda x: lower(regexp_replace(x, '^https?://(www\.)?', 'url:')))), lambda x: not starts_with(x, 'url:t.co'))"""

QUERIES = {
    "telegram": ("data/posts.parquet", f"""
  select 'telegram' platform, message_id::varchar post_id, from_id::varchar user_id, date::timestamp ts, text,
         reply_to_message_id::varchar reply_to, channel thread, ru_pa::boolean label, null::varchar category,
         {ITEMS.replace('COL', 'text')} items
  from read_csv('SRC', header=true) where from_id is not null"""),

    "x": ("data/posts_x.parquet", f"""
  select 'x' platform, tweet_id::varchar post_id, lower(author) user_id,
         strptime(publish_date, '%m/%d/%Y %H:%M') ts, content text, null::varchar reply_to, null::varchar thread,
         null::boolean label, account_category category,
         list_distinct({ITEMS.replace('COL', 'content')} || list_filter(list_transform([tco1_step1, tco2_step1, tco3_step1],
           lambda x: lower(regexp_replace(x, '^https?://(www\.)?', 'url:'))), lambda x: x is not null)) items
  from read_csv('SRC', header=true, all_varchar=true, union_by_name=true) where author is not null"""),
}

kind = sys.argv[1] if len(sys.argv) > 1 else "telegram"
out, query = QUERIES[kind]
src = sys.argv[2] if len(sys.argv) > 2 else "dataset_v2.csv"
duckdb.sql(f"copy ({query.replace('SRC', src)}) to '{out}' (format parquet, compression zstd)")
print(duckdb.sql(f"select count(*) posts, count(distinct user_id) users, sum(len(items)) items from '{out}'"))
