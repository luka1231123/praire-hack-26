# PropNET — 6 Verified Real-World Examples

Every number, timestamp, domain, account count, and quote below comes directly from `data/influence_report.json`, `docs/site-data.js`, and `data/focused/*.parquet`. What the accounts did (measured behavior) is kept strictly separate from outside labels or attribution.

## Quick Overview

| # | Group | Source | What the Accounts Are Doing | Key Numbers | Outside Labels |
|---|---|---|---|---|---|
| 1 | **Group #20** (`nextstamina.com`) | Bluesky (2026 live) | 6 fake news accounts posting rewritten captions to one exclusive site every 30 min | `100%` pairs linked · `1.2s` median gap · `13` rewritten stories · `0` outside accounts | **None** (unattributed lead) |
| 2 | **Group #25** | Telegram (2023–24) | 93 accounts posting identical Russian drone-warfare scripts across channels | `3,043` cross-channel matches · `ria.ru` & `az.sputniknews.ru` · `13.9%` quietest 6h | **93/93 (100%)** labeled pro-Russian |
| 3 | **Group #686** | Telegram (2023) | 18 accounts posting emoji-prefixed anti-war scripts in `Readovka` & `Ru2ch` | `1,402` cross-channel matches · `54.9%` pairs linked · `2,284` posts | **16/18 (88.9%)** labeled pro-Ukrainian |
| 4 | **Group #836** | Telegram (2023) | 3 accounts pasting Mi-8 defection scripts with **17 Latin lookalike letters** inside Cyrillic words | `17` cross-channel matches · `87.4%` daytime UTC+3 (`0%` quiet 6h) · `86s` gap | **0/3 labeled** (missed by study labels) |
| 5 | **Group #865** | X (2015–16) | 48 Russian-language accounts posting identical headlines & MH17 blog links on a St. Petersburg shift | `88.7%` pairs linked · `10,194` same-minute matches · `86.0%` in `06–18 UTC` (`1.8%` low) | **48/48 (100%)** Russian troll archive (`NonEnglish`) |
| 6 | **Groups #853 & #858** | X (2014–17) | Two opposing US-focused teams: 79 right-leaning accounts running 24/7 & 49 left-leaning accounts with reworded voter-suppression replies | `83,949` posts (`18.0%` quiet 6h) · `60s` reworded voter-suppression pair | **79/79** `RightTroll` · **49/49** `LeftTroll` |

---

## 1. Live Bluesky Ring Using AI-Style Rewrites — `Group #20` (`nextstamina.com`)

**What the accounts are doing:** Six Bluesky accounts act like six separate news outlets — four active since late October or early November 2026 (**Next Stamina** `BS-0032`, **ReadGrid** `BS-0068`, **News Wire** `BS-0035`, **Kitepost** `BS-0086`) and two new ones that started posting at the exact same second on November 21 at `19:55:49 UTC` (**Vex Brief** `BS-0064` and **True Beat** `BS-0085`). Every ~30 minutes (`20:06`, `20:36`, `21:07`, `21:36 UTC`), all six post freshly reworded political summaries within **1–3 seconds** of each other, every single one pointing to the same `nextstamina.com` article.

**Verified numbers:**
- **Accounts and links:** `6` accounts, all `15/15` pairs linked (`100%`), `147` matched pair events (`127` shared URL, `20` reused text) across `128` political posts (`Oct 27 – Nov 21, 2026`).
- **Timing:** **`1.2s` median gap**. On Nov 21, six-account bursts fired at `19:55:48` (`1.90s` spread), `20:05:59` (`2.80s`), `20:15:43` (`1.00s`), `20:36:16` (`1.70s`), `21:07:01` (`3.70s`, 5 accounts), and `21:36:04 UTC` (`2.80s`).
- **Website exclusivity:** **`100%`** of links (`128/128` posts) go to `nextstamina.com`, and **`0` outside accounts** anywhere in our 2,274,195-post Bluesky archive link to that site.
- **Rewritten bursts:** `13` separate political stories posted with different wording for the exact same link within seconds.

**Side-by-side rewritten posts (paraphrased but linked):**

- **Chris Van Hollen / Chuck Schumer Iran-deal story** (`nextstamina.com/2026/11/21/van-hollen-uses-schumers-iran-deal-stance-in-leadership-challenge/`) — all 6 accounts fired different rewrites within **2.80 seconds** (`21:36:04.253` to `21:36:07.053 UTC`). The closest pair had **only 34% word overlap** and posted **99 milliseconds apart**:
  - `BS-0085` (*True Beat*, `21:36:06.853 UTC`):
    > *"Senator Chris Van Hollen is taking aim at Chuck Schumer, highlighting past Iran policy as he makes his case for the Senate majority leader position. How this shifts the leadership race…"*
  - `BS-0068` (*ReadGrid*, `21:36:06.952 UTC`, `+0.099s`, **34% word overlap**):
    > *"Senator Chris Van Hollen is taking a swing at Chuck Schumer for the top Democratic spot in the Senate. The strategy centers on a key disagreement over past Iran policy. Read the full story on…"*
  - `BS-0032` (*Next Stamina*, `21:36:04.253 UTC`):
    > *"Chris Van Hollen is making a move for Senate leadership. He is using Chuck Schumer's history on the Iran deal as a key point of contention in his challenge for the top spot."*
  - `BS-0064` (*Vex Brief*, `21:36:07.053 UTC`):
    > *"Senator Chris Van Hollen is taking aim at Chuck Schumer’s leadership, leveraging the majority leader's past record on the Iran deal as a key point of contention in his bid for the top spot."*

- **Santa Clarita immigration arrest** (`nextstamina.com/2026/11/21/federal-immigration-agents-arrest-man-outside-california-sheriff-station/`) — all 6 accounts fired within `1.70s`; the closest pair posted **2 milliseconds apart** (`0.0017s`, **50% word overlap**):
  - `BS-0068` (*ReadGrid*, `2026-11-21 20:36:18.654 UTC`):
    > *"Federal immigration agents arrested a man outside a Santa Clarita sheriff station on Friday, sparking a heated confrontation on the scene. Read the latest on the developing situation…"*
  - `BS-0085` (*True Beat*, `2026-11-21 20:36:18.656 UTC`, `+0.002s`):
    > *"Federal immigration agents took a man into custody outside a Santa Clarita sheriff station on Friday, sparking a tense standoff at the scene. We are tracking the latest on this…"*
  - `BS-0032` (*Next Stamina*, `2026-11-21 20:36:18.454 UTC`):
    > *"Tensions flared in Santa Clarita on Friday as federal immigration agents took a man into custody directly outside a sheriff station. We are tracking the details of this confrontation…"*

**Outside labels:** None — unattributed live Bluesky capture. The data shows six automated accounts serving one exclusive website, not who owns `nextstamina.com` (it could be a commercial click-farm, SEO ring, or political operation).

**Why this example matters:** Exact copy-paste filters miss this group completely because the wording changes on every account (down to 34% shared words), and AI-text detectors can't prove six accounts belong to the same operator. Matching on shared links, sub-second timing, and zero-outside-account exclusivity catches all six cleanly.

---

## 2. 93-Account Pro-Russian Telegram Script Farm — `Group #25`

**What the accounts are doing:** Ninety-three Telegram accounts drop identical Russian talking points into public chat channels — mainly `Readovka` (`6,304` posts), `Ru2ch` (`1,590`), `Murz` (`1,165`), `Rtrus` (`851`), `KK` (`485`), and `Topor` (`257`), plus opposition channels like `Nexta` — pushing demands for international rules on Ukrainian drone strikes and linking Russian state media (`ria.ru`, `az.sputniknews.ru`) almost around the clock.

**Verified numbers:**
- **Accounts and matches:** `93` accounts, `945` connected pairs (`22.1%`), **`3,043` matched pair events** (`3,041` cross-channel text, `1` reused text, `1` shared URL), `10,825` political posts across `12` channels (`Jan 2023 – Jan 2024`).
- **Links shared:** `ria.ru` (`20` posts across `10` accounts, `17.9%` of group links), `az.sputniknews.ru` (`15` posts, `10` accounts, `13.4%`), `innov.ru` (`9` posts).
- **Schedule:** Almost flat 24/7 activity — **`13.9%`** of posts happen during their quietest 6-hour stretch (`59.7%` in `06:00–18:00 UTC`, peak `08:00 UTC`).

**Exact Russian posts and English translations:**

- **Posted by 10 accounts across channels (e.g., `Nexta` `2023-08-19 11:44:27 UTC` and `Donrf` `2023-08-27 06:29:40 UTC` — 7.8 days apart):**
  > **Russian:** *"Военные беспилотники как вид вооружения давно пора отдельно законодательством и конвенциями международными урегулировать, ввести четкие правила их применения, потому что в ином случае они и дальше будут использоваться для нарушения чужих границ."*
  > **English:** *"It is long past time to regulate military drones as a weapons category through dedicated legislation and international conventions, setting clear rules for their use — otherwise they will keep being used to violate other countries' borders."*

- **Posted by 12 accounts (e.g., `Rtrus` `2023-05-27 12:09:23 UTC` and `Readovka` `2023-05-28 06:10:45 UTC`):**
  > **Russian:** *"Нельзя пускать на самотек использование беспилотников! 😤 Нужны правила их использования в военных целях!!! 😤😤😤"*
  > **English:** *"We can't let drone use run unchecked! 😤 We need rules governing their military use!!! 😤😤😤"*

- **Posted by 11 accounts (`Rtrus` `2023-05-30 08:29:21 UTC` and `Readovka` `2023-05-30 08:47:34 UTC`, 18.2 min apart):**
  > **Russian:** *"почему-то военные объекты мало интересуют украинцев, они направляют свои БПЛА на мирных жителей, такие вот герои)))"*
  > **English:** *"For some reason military targets barely interest the Ukrainians — they aim their UAVs at civilians, what 'heroes')))"*

**Outside labels:** **93 of 93 accounts (100%)** were independently labeled as pro-Russian propaganda in the university Telegram study (Zenodo / USENIX Security 2025). PropNET never read those labels during detection.

**Why this example matters:** Short 5-minute time windows miss slow Telegram farms that reuse talking-point sheets days apart across different chats (like `Nexta` to `Donrf` 7.8 days later). Adding a rule for identical long messages (`>=60` characters) reused across different channels recovers all 93 accounts.

---

## 3. 18-Account Pro-Ukrainian Telegram Script Ring — `Group #686`

**What the accounts are doing:** Eighteen accounts paste emoji-prefixed Russian anti-war and pro-Ukrainian scripts into large Russian Telegram comment threads (`Readovka`: `1,756` posts; `Ru2ch`: `528` posts) between May and September 2023.

**Verified numbers:**
- **Accounts and matches:** `18` accounts, `84` connected pairs (`54.9%`), **`1,402` matched pair events** (`1,393` cross-channel text, `9` reused text), `2,284` political posts.
- **Schedule:** Peaks at `21:00 UTC` (`72.1%` in `14:00–02:00 UTC`, quietest 6h = `3.9%`).

**Exact Russian posts and English translations (all posted July 5, 2023 across `Readovka` and `Ru2ch`):**

- **10 accounts (`Readovka` `18:48:42 UTC` and `Ru2ch` `19:10:23 UTC`, 21.7 min apart):**
  > **Russian:** *"🚫 Война нарушает права человека, подвергает население насилию и жестокости, лишая их свободы и безопасности."*
  > **English:** *"🚫 War violates human rights, subjecting the population to violence and brutality and stripping them of freedom and security."*

- **10 accounts (`Readovka` `18:32:27 UTC` and `Ru2ch` `19:12:03 UTC`, 39.6 min apart):**
  > **Russian:** *"🕊️ Капитуляция России может привести к прекращению бесплодной и разрушительной войны, что позволит сэкономить людские жизни."*
  > **English:** *"🕊️ Russia's capitulation could bring an end to a fruitless and destructive war, saving human lives."*

- **9 accounts (`Readovka` `20:23:32 UTC` and `Ru2ch` `21:40:10 UTC`, 76.6 min apart):**
  > **Russian:** *"🌱 После капитуляции Россия сможет сосредоточиться на развитии экологически устойчивого сельского хозяйства и обеспечении продовольственной безопасности."*
  > **English:** *"🌱 After capitulation, Russia will be able to focus on developing environmentally sustainable agriculture and ensuring food security."*

**Outside labels:** **16 of 18 accounts (88.9%)** were independently labeled as pro-Ukrainian propaganda in the university Telegram study (`0` pro-Russian).

**Why this example matters:** Unlike a text classifier trained on one side's slogans, PropNET catches both the 93-account pro-Russian farm (`Group #25`) and the 18-account pro-Ukrainian ring (`Group #686`) using the exact same behavior rules.

---

## 4. Unlabeled Telegram Group Hiding Behind Lookalike Letters — `Group #836`

**What the accounts are doing:** Three Telegram accounts (`TG-0173`, `TG-0235`, `TG-0358` on the site; local IDs `508869`, `367993`, `349002`) post identical Russian war commentary in `KK` (`765` posts) and `Ru2ch` (`517` posts) on a sharp Eastern Europe daytime schedule — while swapping **Latin lookalike letters** into Cyrillic words to slip past keyword filters.

**Verified numbers:**
- **Accounts and matches:** `3` accounts, `2/3` pairs connected (`66.7%`), `17` cross-channel matches across `1,282` political posts (`June – Sept 2023`).
- **Schedule:** **`87.4%`** of posts happen between `06:00` and `18:00 UTC` (`09:00–21:00` Eastern Europe / Moscow time), peaking at `14:00 UTC`, with **`0.0%`** activity during their quietest 6 hours (no posts from `15:00` to `02:59 UTC`).
- **Timing:** On `2023-08-28`, right after a Russian Mi-8 helicopter defected to Ukraine, two accounts pasted **five** identical disguised scripts into `Ru2ch` (`06:04:43–06:05:31 UTC`) and `KK` (`06:06:57–06:07:28 UTC`) just **86 to 140 seconds apart**.

**Exact disguised post (`Ru2ch` `06:05:31 UTC` -> `KK` `06:06:57 UTC`, 86s apart):**
> **Russian (exact archived bytes — looks like normal Cyrillic, but hides 17 Latin letters):**
> *"Pоссийский вертолет Ми-8 cдался в плен. Это позволит Украине oдновременно пополнить cвои oграниченные aвиационные запасы и получить ценные pазведданные o pоссийских ВВС. Но. Писец даже не в этом. Вы xоть знаете, что в вертолете yстановлена cистема pаспознавания cвой-чужой для ПВО? Перепрограммировать cвой-чужой – это масса времени и денег! И пока наши генералы мозги включат, yкраинцы будут к нам летать, как к cебе на дачу."*
>
> **English:** *"A Russian Mi-8 helicopter surrendered. That lets Ukraine simultaneously replenish its limited aviation stock and gain valuable intelligence on the Russian Air Force. But that's not even the worst part. Do you even know the helicopter has an IFF friend-or-foe transponder for air defense? Reprogramming friend-or-foe takes a ton of time and money! And while our generals finally switch their brains on, the Ukrainians will fly over here like they're visiting their own summer cottage."*

**Character check:** Seventeen initial letters in this single message are English/Latin characters rather than Cyrillic (`U+0050 P` in `Pоссийский`, `U+0063 c` in `cдался`/`cвои`/`cистема`/`cвой-чужой`/`cебе`, `U+006F o` in `oдновременно`/`oграниченные`/`o`, `U+0061 a` in `aвиационные`, `U+0070 p` in `pазведданные`/`pоссийских`/`pаспознавания`, `U+0078 x` in `xоть`, `U+0079 y` in `yстановлена`/`yкраинцы`) — plus a stray opening `"` copied straight out of a spreadsheet cell.

**Outside labels:** **0 of 3 accounts labeled** in the university Telegram dataset (`ru_pa = false`, `ua_pa = false`) — an unlabeled lead missed by the original study.

**Why this example matters:** Swapping Latin lookalikes breaks standard Russian keyword filters, yet pasting the exact same disguised text across two channels still matches byte-for-byte. PropNET flags real disguised behavior that even published ground-truth labels missed.

---

## 5. Russian-Language St. Petersburg Work-Shift Group on X — `Group #865`

**What the accounts are doing:** Forty-eight Russian-language accounts act as a tight broadcast team on a St. Petersburg office schedule — posting identical headlines and links within the same minute to push Kremlin-aligned blogs, including `boeing-is-back.livejournal.com` (a documented MH17 disinformation blog) along with Ukraine-collapse and Crimea stories.

**Verified numbers:**
- **Accounts and matches:** `48` accounts, `1,001 / 1,128` pairs connected (**`88.7%`**), **`10,194` matched pair signals** (`5,736` shared URL, `4,458` reused text) across `556` political posts (`May 2015 – July 2016`).
- **Timing and work shift:** **`0s` median gap** (same recorded minute). **`86.0%`** of posts happen between **`06:00` and `18:00 UTC`** (`09:00–21:00` St. Petersburg / Moscow time), peaking at `10:00 UTC`, with only **`1.8%`** of posts during their quietest 6 hours.
- **Top sites linked:** `stalist.livejournal.com` (`55` posts, `37` accounts), **`boeing-is-back.livejournal.com`** (`45` posts, `45` accounts), and `jpgazeta.ru` (`45` posts, `45` accounts).

**Exact same-minute Russian posts and English translations:**

- **45 accounts in the same minute (e.g., `alodoy` & `androfag`, `2015-10-06 10:59 UTC`, linking `jpgazeta.ru`):**
  > **Russian:** *"Украина умирает: без злорадства про дефолт и его последствия"*
  > **English:** *"Ukraine is dying: without schadenfreude, on the default and its consequences"*

- **45 accounts in the same minute (`alodoy` & `androfag`, `2015-09-28 14:34 UTC`, linking `boeing-is-back.livejournal.com/339835.html`):**
  > **Russian:** *"Пойдет ли Запад на 4 условия Путина?"*
  > **English:** *"Will the West agree to Putin's 4 conditions?"*

- **45 accounts in the same minute (`alodoy` & `androfag`, `2015-09-29 13:15 UTC`):**
  > **Russian:** *"Немного хорошей пародии на тему блокады Крыма"*
  > **English:** *"A bit of good parody on the topic of the Crimea blockade"*

**Outside labels:** The public Clemson / FiveThirtyEight dataset of known Russian troll accounts on X records **48 of 48 accounts (100%)** as Russian Internet Research Agency `NonEnglish` accounts.

**Why this example matters:** Before checking any external label, the 88.7% connected network, same-minute bursts, disinformation blog links, and 9-to-9 St. Petersburg posting hours make it obvious this is an organized daytime team.

---

## 6. Two Opposing US Election Teams on X — `Group #853` (Right-Leaning) & `Group #858` (Left-Leaning)

**What the accounts are doing:** Inside the same 2014–2018 Russian troll archive, PropNET cleanly separates two opposing US-focused teams without ever seeing their role tags: a 79-account right-leaning group posting nonstop around the clock, and a 49-account left-leaning group that included **manually reworded voter-suppression replies** sent to ordinary Americans in June 2016.

**Verified numbers:**
- **`Group #853` (right-leaning team):** `79` accounts, `663` connected pairs (`21.5%`), `5,456` matched pair events (`3,174` reused text, `2,282` shared URL), **`83,949` political posts** (`Nov 2014 – Aug 2017`). **No sleep break:** **`18.0%`** of posts happen during their quietest 6 hours (peak `16:00 UTC`). Top sites: `breitbart.com` (`897` posts, `66` accounts), `dld.bz` (`765`), `truthfeed.com` (`522`).
- **`Group #858` (left-leaning team):** `49` accounts, `295` connected pairs (`25.1%`), `3,574` matched pair events (`1,801` reused text, `1,773` shared URL), `17,492` political posts (`Jan 2015 – Aug 2017`). Top sites: `hill.cm` (`699` posts), `bloom.bg` (`117`), `washingtonpost.com` (`106`).

**Exact matched posts:**

- **2016 manually reworded voter-suppression pair (`Group #858`, `2016-06-09`)** — `6` accounts matched inside 5-minute windows (part of an 8-account burst from `13:05` to `13:57 UTC`) pushing the exact same link (`flatoutunconstitutional.com/2015/08/02/welfare-deadbeats-should-not-vote` via `https://t.co/KaKG8KnkyL`). **60 seconds apart**, `blmsoldier` and `robertebonyking` replied to two different Americans with reworded versions of the same line — both claiming *"Here, I wrote this on it:"* (`67%` word overlap):
  - `blmsoldier` (`2016-06-09 13:40 UTC`):
    > `.@oscrewedUSA There is no right to vote in the Constitution. Voting is up to states. Here, I wrote this on it:  https://t.co/KaKG8KnkyL`
  - `robertebonyking` (`2016-06-09 13:41 UTC`, `+60s`):
    > `.@LindsayMMeredit That isn't in the Constitution. Voting isn't a right. It's up to states. Here, I wrote this on it:  https://t.co/KaKG8KnkyL`

- **24/7 right-leaning same-minute blasts (`Group #853`):**
  - `edwardbroberts` & `jacquelinisbest` (`2015-05-29 23:50 UTC`, `19` accounts in the same minute):
    > `#Obama Claims #ClimateChange Greatest Threat   @POTUS ➰ FLOTUS FLY SEPARATE PLANES   #JunkScience   #TCOT #PJNET http://t.co/tKDHRRPUE2`
  - `happkendrahappy` & `prettylaraplace` (`2015-06-14 22:22 UTC`, `19` accounts in the same minute):
    > `Michelle Obama set for summer trip to Europe http://t.co/NNtl8z6XL1`

**Outside labels:** The Clemson / FiveThirtyEight Russian troll dataset independently labels **79 of 79** in `Group #853` as `RightTroll` and **49 of 49** in `Group #858` as `LeftTroll` (`99.24%` role purity across all 48 X groups detected).

**Why this example matters:** Pair this with Bluesky `Group #20`. In June 2016, Russian operators manually rewrote *"There is no right to vote in the Constitution"* across `blmsoldier` and `robertebonyking` 60 seconds apart while linking the same URL. In November 2026, six Bluesky accounts used AI to rewrite political stories 99 milliseconds apart while linking the same `nextstamina.com` URL. Text-only detectors break on both; behavioral link and timing checks catch both across ten years.
