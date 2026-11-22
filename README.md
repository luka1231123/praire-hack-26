# PropNET

**PropNET** finds coordinated political posting groups across Telegram, X, and Bluesky by looking at posting behavior — shared links, timing, cross-channel scripts, exclusive domains, and 24-hour posting schedules — instead of guessing from writing style.

See [DEMO.md](DEMO.md) for the 4-minute presentation script, [EXAMPLES.md](EXAMPLES.md) for six verified real-world examples, and `docs/index.html` for the interactive report and browser-based Investigator.

## Verified Results

| Archive | Raw Posts | Political Kept | Flagged Groups (Accounts) | Check Against Outside Labels *(never used during detection)* |
|---|---:|---:|---:|---|
| **Telegram war chats** ([EPFL / USENIX '25](https://www.usenix.org/conference/usenixsecurity25/presentation/kireev)) | 17,310,897 | 2,624,724 | 819 (3,893) | **97.46% precision** (`3,794/3,893`: `3,775` pro-Russian, `19` pro-Ukrainian) · **9.5×** the `10.28%` baseline |
| **Russian troll accounts on X** ([Clemson / 538](https://github.com/fivethirtyeight/russian-troll-tweets)) | 2,946,207 | 584,815 | 48 (1,456) | **99.24% role purity** (`RightTroll`, `LeftTroll`, `NonEnglish`, etc. separated without seeing tags) |
| **Bluesky public captures** (2026 live) | 2,274,195 | 387,007 | 22 (128) | **Unattributed leads:** `2` exclusive-site rings (`nextstamina.com`, `briefly.co`), `12` fast-repost rings, `8` news mirrors |
| **Total** | **22,531,299** | **3,596,546** | **889 (5,477)** | Top `112` profiled groups (`45` Telegram, `45` X, `22` Bluesky) bundled in `docs/site-data.js` |

## Run Locally (3 Commands)

Requires Python 3.11+ and `uv`. The project uses two Python scripts (`ingest.py`, `detect.py`) and one static webpage (`docs/index.html`).

```bash
# 1. Import and filter each archive (.csv, .csv.zst, or Parquet -> data/focused/<platform>.parquet)
uv run --locked ingest.py telegram && uv run --locked ingest.py x && uv run --locked ingest.py bluesky

# 2. Detect coordinated groups and export JSON, HTML, and the website data file
uv run --locked detect.py --json data/influence_report.json --site docs/site-data.js

# 3. Serve the interactive report and Investigator locally
python3 -m http.server 8765 -d docs
```

Open `http://localhost:8765`. You can also import `data/influence_report.json` directly in the browser to view unaliased Telegram and Bluesky account IDs (the bundled `docs/site-data.js` replaces them with `TG-####` and `BS-####` while keeping public X troll handles as published).

## How It Works — and Why Behavior + Leiden

1. **Filter out noise (`ingest.py`):** Keeps English, Russian, and Ukrainian political/war posts (plus Bluesky reposts of kept originals) while dropping porn domains, adult spam, and crypto/casino promos (`22.53M -> 3.60M`, `15.96%`).
2. **Link repeating account pairs (`detect.py`):** Active accounts (`>=5` political posts) are linked only when they match on **`>=2` separate posts** for a link or text shared by **`2–100` accounts** (ignoring viral breaking news):
   - Same web link (excluding shorteners) or identical text (`>=35` chars, `>=5` words) within **5 minutes**.
   - Same Bluesky repost within **15 seconds**.
   - Identical long Telegram message (`>=60` chars, `>=6` words) posted across different channels, regardless of delay.
3. **Group with Leiden:** Leiden grouping splits the pair graph (`resolution=0.25`, pair weight capped at `8`, `>=3` accounts) into tight teams without merging loosely linked bystanders into one giant blob. Each group is then summarized by rewritten link bursts (`<=60s` same-link pairs sharing `10%–82%` of words), website exclusivity (`0` outside posters), and 24-hour UTC posting schedules.

**Why this approach works better than alternatives:**
- **Over AI-text detectors:** Style detectors misfire on normal human writing and break when prompts change. Tracking shared links and sub-second timing caught **Bluesky Group #20** (`nextstamina.com`) posting two completely different summaries of the Van Hollen–Schumer story (**only 34% word overlap**) just **99 milliseconds apart**, plus a Santa Clarita arrest story **2 milliseconds apart**.
- **Over exact copy-paste filters:** Copy-paste filters miss any manual or AI rewrite. Behavior rules caught both the 2026 Bluesky ring and the 2016 Russian troll pair in **X Group #858** (`blmsoldier` & `robertebonyking`), who reworded *"There is no right to vote in the Constitution"* **60 seconds apart** while linking the same page.
- **Over black-box classifiers:** Opaque scores are hard to audit and can absorb political bias. Transparent rules show every matching post, link, and timestamp — catching both a 93-account pro-Russian Telegram farm (**Group #25**) and an 18-account pro-Ukrainian ring (**Group #686**), plus an unlabeled 3-account Telegram group (**Group #836**) that hid **17 Latin lookalike letters** inside Cyrillic words.

## Limits and Attribution

- **Coordinated behavior does not prove who runs an account.** Shared links, timing, and scripts show shared tooling or instructions; attributing an operator to a state or organization requires outside evidence. PropNET keeps behavior summaries and outside labels strictly separate.
- **Archive caveats:** The [FiveThirtyEight X archive](https://github.com/fivethirtyeight/russian-troll-tweets) contains only known Russian troll accounts (no normal-user control group). The [Zenodo Telegram dataset](https://zenodo.org/records/14736756) used repeated text as one input when researchers built its labels. Bluesky captures have no outside attribution, and older backfill timestamps may be off by 1 hour for daylight saving time.
- **What can evade detection:** A campaign that rewrites every post with AI *and* avoids sharing links, rapid reposts, or cross-channel scripts can bypass these rules.
