# PropNET — Live 4-Minute Presentation Script

> **Before presenting:** Run `python3 -m http.server 8765 -d docs` and open `http://localhost:8765` full-screen. Keep [EXAMPLES.md](EXAMPLES.md) open nearby for Q&A, plus `data/influence_report.json` if someone asks to load unaliased local IDs.

---

## 0:00–0:40 · The Problem and Our Idea
**[SHOW ON SCREEN: `Overview` — point to the right-hand Bluesky card: "Real example: 6 Bluesky accounts rewriting the same story."]**

Most tools that look for coordinated political accounts check the wording — hunting for copy-pasted text or guessing whether AI wrote a post. That breaks as soon as accounts rewrite each sentence.

Look at this live Bluesky example. Two accounts posing as separate news sites posted different summaries of a Senate leadership story — sharing only **34% of the same words** — just **99 milliseconds apart**, linking the exact same obscure article.

PropNET skips writing style and checks posting behavior: shared links, timing, repeated scripts, and work-hour schedules.

---

## 0:40–1:30 · How It Works and Why Behavior + Leiden
**[SHOW ON SCREEN: Scroll to `How it works` and walk across Steps 1–3 (`22.53M` -> `3.60M` -> `889`) and the comparison table below.]**

We checked **22.53 million** posts across university-labeled Telegram war chats, known Russian troll accounts on X (2014–2018), and live Bluesky captures. Step 1 strips spam and off-topic posts, keeping **3.60 million** political posts.

Step 2 links two accounts only when they match on **at least two separate posts** — sharing a link or message within five minutes, or posting identical long scripts in different Telegram chats — ignoring anything shared by over 100 accounts so breaking news stays out.

Step 3 runs **Leiden grouping**, splitting repeating pairs into tight teams instead of one giant blob, finding **889 groups**. Unlike AI-text detectors (which misfire on human writing), copy-paste filters (which miss rewrites), or black-box models, every group shows the exact posts and timestamps behind it.

---

## 1:30–2:50 · Accuracy and Real Examples
**[SHOW ON SCREEN: Pause on `Accuracy` ("How accurate is it?"), then scroll to `Examples` ("Real examples from the data").]**

PropNET never sees outside labels. Checked afterward, **97.5%** of our 3,893 flagged Telegram accounts match university propaganda labels (**9.5×** the 10.3% baseline), and our 48 X groups are **99.2% pure** by team role.

**[SHOW ON SCREEN: Click Bluesky `Group #20`, then Telegram `Group #25` -> `Group #686`, then X `Group #865` / `Group #858`.]**

**Bluesky (`Group #20`):** Six accounts pose as separate news sites (*Next Stamina*, *ReadGrid*, *News Wire*, *Kitepost*, plus *Vex Brief* and *True Beat* from Nov 21). All 128 political posts link only to `nextstamina.com` with **zero outside accounts**. Every 30 minutes (`20:06`, `20:36`, `21:07`, `21:36 UTC`), all six fire rewritten posts (`1.2s` median) — **2ms apart** on a Santa Clarita arrest and **99ms apart** on Van Hollen–Schumer. Unattributed, so we report it strictly as a lead.

**Telegram (`Group #25` & `Group #686`):** Group #25 is **93 accounts** posting identical Russian drone scripts across `Readovka`, `Rtrus`, and `Nexta` nearly 24/7 (`ria.ru`, `az.sputniknews.ru`) — **93/93** labeled pro-Russian. Group #686 is **18 accounts** posting emoji anti-war scripts (`🚫`, `🕊️`) in `Readovka` and `Ru2ch` — **16/18** pro-Ukrainian. Same rules catch both sides.

**X (`Group #865` & `Group #858`):** Group #865 is 48 Russian-language accounts (`89%` connected) posting `boeing-is-back.livejournal.com` within the same minute — **86%** during `06:00–18:00 UTC` (9-to-9 St. Petersburg hours, `1.8%` nighttime low). In Group #858, `blmsoldier` and `robertebonyking` reworded *"There is no right to vote in the Constitution"* **60 seconds apart** to the same link — catching both 2016 human rewrites and 2026 AI rewrites.

---

## 2:50–3:40 · Live Investigator
**[SHOW ON SCREEN: Jump to `Investigator`, search `#836`, and open Telegram `Group #836`.]**

In the **Investigator**, you can search and filter all 112 profiled groups, separating likely covert groups from normal news mirrors.

Look at **Telegram Group #836**: **zero of three accounts** were flagged in the university study. On August 28, 2023, they pasted identical Russian posts about a Mi-8 helicopter defecting to Ukraine into `Ru2ch` and `KK` **86 seconds apart** — hiding **17 Latin letters** (`P, a, c, o, p, x, y`) inside Cyrillic words to slip past keyword filters. Because they reused the same altered script across channels, PropNET caught what the original labels missed.

**[SHOW ON SCREEN: Point to `Export CSV`, `Export JSON`, and `Import local JSON report`.]**

Any group exports to CSV or JSON, and local JSON reports load in the browser.

---

## 3:40–4:00 · Wrap-Up
**[SHOW ON SCREEN: Keep the `Investigator` open on the separate behavior and outside-label boxes.]**

Writing styles shifted from human troll farms in 2016 to AI-rewritten accounts on Bluesky in 2026, but coordinated behavior stayed measurable.

PropNET shows the exact posts, links, timestamps, and schedules behind every group, while keeping measured behavior strictly separate from claims about who runs an account. Happy to take questions.

---

## Likely Q&A (3 Short Answers)

- **"How do you keep normal news bots or breaking news from showing up as fake campaigns?"**
  Three checks: anything shared by more than 100 accounts is ignored so viral news doesn't link strangers; two accounts must match on at least two separate posts; and we label groups that only share mainstream news sites (`8` of `22` Bluesky groups) separately from groups pushing one exclusive site with zero outside posters (`2` Bluesky groups).

- **"On Telegram, didn't the university study also look at repeated text? Isn't 97.5% circular?"**
  Repeated text was one clue in that Telegram study, which we note openly in [README.md](README.md). Two checks show PropNET holds up independently: on the X archive (where teams were labeled by persona role, not text hashing), PropNET recovers **99.2% pure** groups on its own; and on Telegram it catches disguised groups like **Group #836** (`0/3` labeled) that the study missed.

- **"What can still get past PropNET?"**
  If an operation uses AI to rewrite every post and avoids sharing links, rapid reposts, or cross-channel scripts, exact text and URL rules won't catch it. That is why we combine timing, links, reposts, and daily schedules — and treat unattributed Bluesky groups as leads to check, not final proof.
