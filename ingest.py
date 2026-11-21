"""Convert the Telegram dataset into the shared posts table: data/posts.parquet.

Shared columns (Bluesky uses the same ones):
  platform, post_id, user_id, ts, text, reply_to, thread, label, items
label = ground truth when known (Telegram ru_pa), else NULL.
items = links, #hashtags and @mentions in the post.
"""
import sys
import duckdb

SRC = sys.argv[1] if len(sys.argv) > 1 else "dataset_v2.csv"

duckdb.sql(rf"""
copy (
  select 'telegram'                    as platform,
         message_id::varchar           as post_id,
         from_id::varchar              as user_id,
         date::timestamp               as ts,
         text,
         reply_to_message_id::varchar  as reply_to,
         channel                       as thread,
         ru_pa::boolean                as label,
         list_distinct(list_transform(
           regexp_extract_all(coalesce(text, ''), '(https?://[^\s?#]+|#[\p{{L}}\p{{N}}_]+|@[\p{{L}}\p{{N}}_]+)'),
           lambda x: lower(regexp_replace(x, '^https?://(www\.)?', 'url:')))) as items
  from read_csv('{SRC}', header=true)
  where from_id is not null
) to 'data/posts.parquet' (format parquet, compression zstd)
""")
print(duckdb.sql("select count(*) posts, count(distinct user_id) users, sum(len(items)) items from 'data/posts.parquet'"))
