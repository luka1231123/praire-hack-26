# praire-hack-26

Finds groups of accounts that act together (troll farms, state operators, spam networks).
It uses no text model. AI can rewrite the words, but operators still share **behavior**:
the same reply targets, the same timing, the same links and hashtags, the same template
text, and the same work schedule.

## How it works

1. Every post goes into one table: `platform, post_id, user_id, ts, text, reply_to, thread, label, items`.
2. `detect.py` scores each pair of users on shared keys. Popular keys count less (weight `1/(users-1)`):
   - `dup`: the same text after normalizing (case, links, digits, punctuation, emoji)
   - `item`: the same link, `#hashtag`, `@mention`, or repost
   - `tgt`: replies to the same message
   - `fast`: the same key within 60 s
   - `sched`: similar weekly activity pattern (168 hour buckets)
3. Leiden clustering finds tight groups. Groups are ranked by shared content per member.
4. An HTML report lists each group with members and its top shared evidence.

## Result on the Telegram dataset

The data has 17.3M comments from 13 Russian channels, and 15,856 accounts are labeled as propaganda accounts.
Users with 20 or more posts are scored. Of these, 3.1% are labeled.

| Groups         | Users | Labeled |
|----------------|------:|--------:|
| top 10         |   655 |   46.4% |
| top 50         | 1,231 |   52.6% |
| top 200        | 2,540 |   41.3% |

That is about 16× the base rate. The top groups also hold unlabeled networks, for example
accounts that post emoji-prefixed template talking points, and copypasta written with mixed Latin and Cyrillic letters.

Lift of each signal for one pair of users (both users labeled, against 0.7% for a random pair):
the same text is 94×, the same link or tag is 9×, and the same reply targets are about 5×.

## Run

Needs [uv](https://docs.astral.sh/uv/).

Telegram (offline test against labels):

```bash
uv run ingest.py dataset_v2.csv   # CSV to data/posts.parquet (about 5 s)
uv run detect.py                  # data/report.html (about 70 s)
```

Bluesky (live, free, no key):

```bash
uv run monitor.py                 # data/live_report.html, refreshed every 5 min
```

The monitor reads the Bluesky Jetstream firehose (about 40 posts/s) and keeps a rolling 24-hour window in `data/live/`.

## Dataset

`dataset_v2.csv` (3.9 GB) is not in git. It is too large for GitHub, and it holds Telegram user data.

Download: [dataset_v2.zip on Zenodo](https://zenodo.org/records/14736756/files/dataset_v2.zip?download=1) (record: https://zenodo.org/records/14736756)

Unzip it and put `dataset_v2.csv` in the repo root. `.gitignore` keeps it and `data/` out of commits.

Source: Kireev et al. (EPFL), "Characterizing and Detecting Propaganda-Spreading Accounts on Telegram", USENIX Security 2025.

Columns: `message_id, date, from_id, reply_to_message_id, text, channel, source, ru_pa, deleted, topic, ua_pa, reply_count`
