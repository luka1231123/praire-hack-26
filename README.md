# praire-hack-26

Finds groups of accounts that act together (troll farms, state operators, spam networks).
Detection uses no text model. AI can rewrite the words, but operators still share **behavior**:
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
4. Each group gets a **kind**: `political`, `scam`, `porn` or `other` (see below).
5. An HTML report lists each group with its kind, members and top shared evidence.

## Group kind

Detection finds all coordinated groups, so spam networks come out next to state operators.
A small multilingual embedding model ([model2vec](https://github.com/MinishLab/model2vec) `potion-multilingual-128M`, numpy only)
sorts them. It runs only after detection, on up to 200 posts per group.

- Each post votes for the class of its closest prototype sentence (`PROTOTYPES` in `detect.py`).
  A post votes only when one class is clearly closest (cosine margin 0.05).
- Links to porn hosts (onlyfans, fansly, ...) or scam hosts (casino, airdrop, gofundme, ...) add to that class.
- The group kind is the flagged class with the largest share, if the share is 15% or more. Else it is `other`.
- Hover the kind cell in the report to see the vote shares.

The kind tells the topic only. A `political` group can be real activists. Evidence for a state operator
is the schedule signal and the labels. To add a class or fix a miss, add a prototype sentence.

| Data      | Result |
|-----------|--------|
| Telegram  | 1,033 of 1,035 labeled propaganda users are in `political` groups. `other` groups are 0.4% labeled. |
| X (IRA)   | 1,563 of 1,762 troll users are `political`. 79 of 83 HashtagGamer (word games) are `other`. |
| Bluesky   | Finds porn, Korean porn spam, donation-begging spam and affiliate spam. Errors: flight-tracker bots as `scam`, webcam feeds as `porn`. |

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

## Result on X (Twitter) troll data

[FiveThirtyEight russian-troll-tweets](https://github.com/fivethirtyeight/russian-troll-tweets): 2.9M tweets
from 2,843 accounts of the Russian Internet Research Agency (IRA), each with a category
(RightTroll, LeftTroll, NewsFeed, HashtagGamer, Fearmonger, NonEnglish, ...).
All accounts are trolls, so the test is: do the found groups match the real categories?

The found groups are **91% pure** by category, against 55% for random groups of the same sizes (resolution 5).
Examples: one group is 79 of 80 HashtagGamer accounts, one is 104 of 104 RightTroll, one is 33 of 33 NewsFeed.
One group of 207 mixes LeftTroll and RightTroll accounts that amplified the same content.

Lift of each signal for one pair of users (both users labeled, against 0.7% for a random pair):
the same text is 94×, the same link or tag is 9×, and the same reply targets are about 5×.

## Run

Needs [uv](https://docs.astral.sh/uv/).

Telegram (offline test against labels):

```bash
uv run ingest.py telegram dataset_v2.csv   # CSV to data/posts.parquet (about 5 s)
uv run detect.py                           # data/report.html (about 70 s)
```

X troll data (offline test against categories):

```bash
mkdir -p data/x_ira && cd data/x_ira && for i in $(seq 1 13); do curl -sSfLO "https://raw.githubusercontent.com/fivethirtyeight/russian-troll-tweets/master/IRAhandle_tweets_$i.csv"; done && cd ../..
uv run ingest.py x "data/x_ira/*.csv"      # data/posts_x.parquet (about 2 s)
uv run detect.py data/posts_x.parquet 20 5 # data/report_x.html (about 5 s)
```

Bluesky (live, free, no key):

```bash
uv run monitor.py                 # data/live_report.html, refreshed every 5 min
WINDOW_H=48 uv run monitor.py     # keep 48 hours of data instead of 24
```

The monitor reads the Bluesky Jetstream firehose (about 40 posts/s) and keeps a rolling 24-hour window in `data/live/`.

## Website

`docs/` is the project website (GitHub Pages: Settings → Pages → main, `/docs`). A dropdown switches
between datasets. `docs/data.js` starts with the numbers above; to fill every chart, export each dataset:

```bash
uv run export_site.py telegram data/posts.parquet 20 0.2
uv run export_site.py x data/posts_x.parquet 20 5
uv run export_site.py bluesky "data/live/*.parquet" 3     # optional, from monitor.py
```

Only summary numbers are written (no user IDs; evidence text is cut to 120 characters).

## Dataset

`dataset_v2.csv` (3.9 GB) is not in git. It is too large for GitHub, and it holds Telegram user data.

Download: [dataset_v2.zip on Zenodo](https://zenodo.org/records/14736756/files/dataset_v2.zip?download=1) (record: https://zenodo.org/records/14736756)

Unzip it and put `dataset_v2.csv` in the repo root. `.gitignore` keeps it and `data/` out of commits.

Source: Kireev et al. (EPFL), "Characterizing and Detecting Propaganda-Spreading Accounts on Telegram", USENIX Security 2025.

Columns: `message_id, date, from_id, reply_to_message_id, text, channel, source, ru_pa, deleted, topic, ua_pa, reply_count`
