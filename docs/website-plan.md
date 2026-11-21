# Website plan (small)

## Goal

A simple website for OSINT investigators: it shows groups of Bluesky accounts that act together, with the evidence for each group.
It flags behavior, not opinions. A person makes the final decision.

## How it works

No web server and no database. `detect.py` already makes an HTML report. It makes a small static site instead:

```
monitor.py ──> data/live/*.parquet ──> detect.py (every 5 min) ──> data/site/index.html
                                                                    data/site/group/<n>.html
                                                                    data/site/method.html
```

To view it: open `data/site/index.html`, or run `python -m http.server -d data/site`.

## Pages

1. **Groups list** (`index.html`): one row per group with size, score, tags, top evidence. A tab for Iowa groups.
2. **Group page** (`group/<n>.html`):
   - "Why flagged" in 2 or 3 plain sentences
   - Evidence: shared texts, links, reposts, with links to the posts
   - Members: handle, created date, followers, posts
   - Timeline: one dot per post, so bursts are easy to see
3. **Method page** (`method.html`): how it works, the test results, the limits.

## Detector change

Add account facts from the free public Bluesky API, to separate fake networks from real communities.
Show them as tags:
- `same-name`: most members have the same display name
- `new-accounts`: most members were created in the same 2 weeks
- `template-bio`: members have near-identical bios
- `likely-community`: old accounts with varied bios (ranked lower)

## Build steps

| Step | Work | Time |
|---|---|---|
| 1 | Fetch account facts, add tags, rank `likely-community` lower | 1 h |
| 2 | Static pages: groups list, group page, timeline | 1.5 h |
| 3 | Method page, Iowa tab | 0.5 h |

Total: about 3 hours.

## Later, only if there is time

Account lookup, exports for Gephi, review labels, delete tracking, a live server.
