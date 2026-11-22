(function () {
  "use strict";

  const BUNDLED_REPORT = window.PROPNET_REPORT;
  if (!BUNDLED_REPORT || !Array.isArray(BUNDLED_REPORT.groups)) {
    console.error("PropNET: window.PROPNET_REPORT is missing or malformed.");
    return;
  }

  const EDGE_COLORS =
    (window.PropnetGraph && window.PropnetGraph.EDGE_COLORS) || {
      "reused text": "#1a5fb4",
      "shared URL": "#d9531e",
      "cross-channel text": "#6b46a8",
      "shared repost": "#14855c",
    };

  const SIGNAL_LABELS = {
    "shared URL": "Shared link",
    "reused text": "Copied text",
    "cross-channel text": "Copied across channels",
    "shared repost": "Instant repost",
  };

  const SOURCE_META = {
    bluesky: { label: "Bluesky", pill: "pill-bluesky", full: "Bluesky" },
    telegram_research: { label: "Telegram", pill: "pill-telegram", full: "Telegram" },
    x_ira: { label: "X trolls", pill: "pill-x", full: "Russian troll archive (X)" },
  };

  const CATEGORY_LABELS = {
    RightTroll: "US right-wing persona",
    LeftTroll: "US left-wing persona",
    NonEnglish: "Russian-language squad",
    NewsFeed: "Fake local news",
    HashtagGamer: "Hashtag campaign",
    Fearmonger: "Fearmongering account",
    Unknown: "Unlabeled",
  };

  const TACTIC_LABELS = {
    paraphrased_link_ring: "Rewritten links",
    cross_channel_script: "Copied across channels",
    exclusive_domain_ring: "Single-site bot ring",
    synchronized_blast: "Synced posting squad",
    fast_repost_ring: "Instant repost ring",
    news_mirror: "News / RSS feed",
  };

  // Optional English translations shown below verbatim Russian quotes
  const SPOTLIGHT_GLOSSES = [
    {
      match: "Нельзя пускать на самотек использование беспилотников",
      en: "We cannot let the use of drones go unchecked! We need rules governing their use for military purposes!!!",
    },
    {
      match: "почему-то военные объекты мало интересуют украинцев",
      en: "For some reason military targets barely interest Ukrainians — they aim their UAVs at civilians, some 'heroes')))",
    },
    {
      match: "Должен же быть какой-то регламент, контролирующий применение беспилотников",
      en: "There must be some kind of regulation controlling the use of drones for military purposes! If there isn't one, it's high time to create it!",
    },
    {
      match: "Война нарушает права человека, подвергает население насилию",
      en: "War violates human rights, exposes the population to violence and cruelty, depriving them of freedom and security.",
    },
    {
      match: "Капитуляция России может привести к прекращению бесплодной",
      en: "Russia's capitulation could bring an end to a fruitless and destructive war, which would save human lives.",
    },
    {
      match: "Война разрушает промышленность и экономику",
      en: "War destroys industry and the economy, depriving citizens of jobs and economic stability.",
    },
    {
      match: "Украина умирает: без злорадства про дефолт",
      en: "Ukraine is dying: without schadenfreude, on default and its consequences",
    },
    {
      match: "Немного хорошей пародии на тему блокады Крыма",
      en: "A bit of good parody on the topic of the Crimea blockade",
    },
    {
      match: "Пойдет ли Запад на 4 условия Путина",
      en: "Will the West agree to Putin's 4 conditions?",
    },
  ];

  // Put the two paraphrased examples first for quick demos
  const SPOTLIGHT_CONFIG = [
    { key: "bluesky", plat: "Bluesky", shortTitle: "Rewritten links" },
    { key: "x_left", plat: "X", shortTitle: "Rewritten voting reply" },
    { key: "telegram_ru", plat: "Telegram", shortTitle: "Pro-Russian farm" },
    { key: "telegram_ua", plat: "Telegram", shortTitle: "Pro-Ukrainian ring" },
    { key: "x_ru", plat: "X", shortTitle: "Russian daytime shift" },
    { key: "x_us", plat: "X", shortTitle: "US right-wing 24/7 bots" },
  ];

  const state = {
    workbenchReport: BUNDLED_REPORT,
    isLocalReport: false,
    localFilename: "",
    activeSpotlightKey: "bluesky",
    spotlightSelectedNode: null,
    spotlightGraphCtrl: null,
    filters: {
      search: "",
      source: "all",
      tactic: "all",
      tier: "all",
      sort: "priority",
    },
    filteredGroups: [],
    selectedGroupId: null,
    wbSelectedNode: null,
    wbGraphCtrl: null,
  };

  /* ---------- Helpers ---------- */

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function makeCaseButton(groupId, label) {
    const btn = el("button", "inline-case-btn", label || "Group #" + groupId);
    btn.type = "button";
    btn.addEventListener("click", () => jumpToWorkbenchCase(groupId));
    return btn;
  }

  function formatCompact(n) {
    if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
    const num = Number(n);
    if (num >= 1e6) return (num / 1e6).toFixed(2) + "M";
    if (num >= 1e4) return (num / 1e3).toFixed(1) + "K";
    return num.toLocaleString();
  }

  function formatPct(ratio, digits) {
    if (typeof ratio !== "number" || Number.isNaN(ratio)) return "—";
    return (ratio * 100).toFixed(digits === undefined ? 1 : digits) + "%";
  }

  function formatGap(seconds, platform) {
    if (typeof seconds !== "number" || Number.isNaN(seconds)) return "—";
    if (platform === "x" && seconds < 1) return "Same min";
    if (seconds < 0.05) return "<0.1s";
    if (seconds < 60) return (seconds < 10 ? seconds.toFixed(1) : Math.round(seconds)) + "s";
    if (seconds < 3600) return (seconds / 60).toFixed(1) + "m";
    if (seconds < 86400) return (seconds / 3600).toFixed(1) + "h";
    return (seconds / 86400).toFixed(1) + "d";
  }

  function formatExactPostDelta(posts, fallbackGap, platform) {
    if (Array.isArray(posts) && posts.length >= 2) {
      const t1 = Date.parse(posts[0].time_utc);
      const t2 = Date.parse(posts[1].time_utc);
      if (!Number.isNaN(t1) && !Number.isNaN(t2)) {
        const diffMs = Math.abs(t2 - t1);
        if (diffMs > 0 && diffMs < 1000) {
          return (diffMs / 1000).toFixed(diffMs < 50 ? 3 : 1) + "s apart";
        }
        if (diffMs === 0) {
          return platform === "x" ? "Same min" : "Same second";
        }
        return formatGap(diffMs / 1000, platform) + " apart";
      }
    }
    return formatGap(fallbackGap, platform) + " gap";
  }

  function formatUtcTime(iso, showMs) {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const yyyy = d.getUTCFullYear();
    const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
    const dd = String(d.getUTCDate()).padStart(2, "0");
    const hh = String(d.getUTCHours()).padStart(2, "0");
    const mi = String(d.getUTCMinutes()).padStart(2, "0");
    const ss = String(d.getUTCSeconds()).padStart(2, "0");
    if (showMs) {
      const ms = String(d.getUTCMilliseconds()).padStart(3, "0");
      return yyyy + "-" + mm + "-" + dd + " " + hh + ":" + mi + ":" + ss + "." + ms + " UTC";
    }
    return yyyy + "-" + mm + "-" + dd + " " + hh + ":" + mi + ":" + ss + " UTC";
  }

  function findGloss(text) {
    if (!text) return null;
    for (const item of SPOTLIGHT_GLOSSES) {
      if (text.includes(item.match)) return item.en;
    }
    return null;
  }

  function sourceInfo(source, platform) {
    if (SOURCE_META[source]) return SOURCE_META[source];
    if (platform === "bluesky") return SOURCE_META.bluesky;
    if (platform === "telegram") return SOURCE_META.telegram_research;
    if (platform === "x") return SOURCE_META.x_ira;
    return { label: platform || source || "Dataset", pill: "pill-x", full: source || "Dataset" };
  }

  function plainTacticLabel(group) {
    return TACTIC_LABELS[group.tactic] || group.tactic_label || group.tactic || "Group";
  }

  function plainCategory(cat) {
    return CATEGORY_LABELS[cat] || cat;
  }

  function plainSignalKind(kind) {
    return SIGNAL_LABELS[kind] || kind || "Match";
  }

  function safeAccountUrl(account, platform) {
    if (!account) return null;
    if (platform === "bluesky" && (account.startsWith("did:plc:") || account.startsWith("did:web:"))) {
      return "https://bsky.app/profile/" + encodeURIComponent(account);
    }
    if (
      platform === "x" &&
      /^[A-Za-z0-9_]{1,20}$/.test(account) &&
      !account.startsWith("BS-") &&
      !account.startsWith("TG-")
    ) {
      return "https://x.com/" + encodeURIComponent(account);
    }
    return null;
  }

  function safePostUrl(post, platform) {
    if (!post || !post.id) return null;
    if (platform === "bluesky" && typeof post.id === "string" && post.id.startsWith("at://")) {
      const parts = post.id.slice(5).split("/");
      if (parts.length >= 3 && parts[1] === "app.bsky.feed.post") {
        return (
          "https://bsky.app/profile/" +
          encodeURIComponent(parts[0]) +
          "/post/" +
          encodeURIComponent(parts[2])
        );
      }
    }
    return null;
  }

  /**
   * Separate why the group was flagged from outside archive/researcher labels.
   */
  function splitBehavioralAndProvenance(group) {
    const raw = (group.why_flagged || "").trim();
    const splitRe =
      /(?=Outside record:|Outside check:|Independent archive record:|Independent EPFL research labels|No EPFL propaganda labels|Unattributed live capture:)/;
    const parts = raw.split(splitRe);
    const behaviorText = (parts[0] || raw).trim();
    const extractedProv = parts.length > 1 ? parts.slice(1).join(" ").trim() : "";

    let provenanceTitle = "Outside labels";
    let provenanceText = extractedProv;
    let isUnattributed = false;
    const provenanceTags = [];

    if (Array.isArray(group.archive_categories) && group.archive_categories.length) {
      provenanceTitle = "Outside labels (Russian troll archive)";
      for (const cat of group.archive_categories) {
        provenanceTags.push(plainCategory(cat.category) + ": " + cat.accounts);
      }
      if (!provenanceText) {
        provenanceText =
          "Known Russian troll archive (X, 2014-2018) lists these accounts as " +
          provenanceTags.join(", ") +
          ". These labels were not shown to the detector.";
      }
    } else if (group.researcher_labels) {
      provenanceTitle = "Outside labels (university researchers)";
      const rl = group.researcher_labels;
      if (rl.pro_ru_accounts > 0) {
        provenanceTags.push(
          "Pro-Russian: " + rl.pro_ru_accounts + "/" + (rl.accounts_with_pro_ru_label || group.accounts.length)
        );
      }
      if (rl.pro_ua_accounts > 0) {
        provenanceTags.push(
          "Pro-Ukrainian: " + rl.pro_ua_accounts + "/" + (rl.accounts_with_pro_ua_label || group.accounts.length)
        );
      }
      if (!provenanceTags.length) {
        provenanceTags.push("No researcher label on these accounts");
      }
      if (!provenanceText) {
        provenanceText =
          "Checked after grouping against university researcher labels (not used during detection).";
      }
    } else {
      isUnattributed = true;
      provenanceTitle = "Outside labels (none)";
      provenanceTags.push("No known owner label");
      if (!provenanceText) {
        provenanceText =
          "Public live capture with no outside label. Behavior shows these accounts act together, not who runs them.";
      }
    }

    return {
      behaviorText: behaviorText || group.headline || "Coordinated posting detected.",
      provenanceTitle,
      provenanceText,
      isUnattributed,
      provenanceTags,
    };
  }

  function getBehavioralChips(group) {
    const chips = [];
    const seen = new Set();
    const pushChip = (label, isAlert) => {
      if (!label || seen.has(label)) return;
      seen.add(label);
      chips.push({ label, isAlert: Boolean(isAlert) });
    };

    if (Array.isArray(group.signals_explained)) {
      for (const s of group.signals_explained) {
        const alert =
          s.includes("Rewritten") ||
          s.includes("Only site") ||
          s.includes("State media") ||
          s.includes("24/7") ||
          s.includes("Russia");
        pushChip(s, alert);
      }
    }

    if (group.paraphrased_matches > 0 && !chips.some((c) => c.label.toLowerCase().includes("rewritten"))) {
      pushChip("Rewritten stories (" + group.paraphrased_matches + ")", true);
    }

    if (chips.length < 2) {
      if (typeof group.median_gap_seconds === "number") {
        if (group.platform === "x" && group.median_gap_seconds < 1) {
          pushChip("Same minute", false);
        } else if (group.median_gap_seconds <= 300) {
          pushChip("~" + formatGap(group.median_gap_seconds, group.platform) + " apart", group.median_gap_seconds <= 5);
        }
      }
      if (group.pair_density >= 0.4) {
        pushChip(Math.round(group.pair_density * 100) + "% linked", false);
      }
      if (group.signal_breakdown) {
        const topKind = Object.entries(group.signal_breakdown).sort((a, b) => b[1] - a[1])[0];
        if (topKind) {
          pushChip(plainSignalKind(topKind[0]) + " (" + topKind[1].toLocaleString() + ")", false);
        }
      }
    }

    return chips;
  }

  function renderEdgeLegend(container, edges) {
    container.replaceChildren();
    const kinds = [...new Set((edges || []).map((e) => e.kind).filter(Boolean))];
    for (const kind of kinds) {
      const item = el("span", "edge-legend-item");
      const sw = el("span", "edge-swatch");
      sw.style.background = EDGE_COLORS[kind] || "#566373";
      item.append(sw, document.createTextNode(plainSignalKind(kind)));
      container.append(item);
    }
  }

  function renderEvidenceCards(container, group, options) {
    container.replaceChildren();
    const opts = options || {};
    const selectedNode = opts.selectedNode || null;
    const maxItems = opts.maxItems || 100;
    const allEv = Array.isArray(group.evidence) ? group.evidence : [];

    let items = allEv;
    let filteredNote = "";
    if (selectedNode) {
      const hits = allEv.filter(
        (ev) => Array.isArray(ev.posts) && ev.posts.some((p) => p.account === selectedNode)
      );
      if (hits.length) {
        items = hits;
        filteredNote =
          "Showing " + hits.length + " matched post" + (hits.length === 1 ? "" : "s") + " for " + selectedNode;
      } else {
        const notice = el(
          "div",
          "ev-empty",
          selectedNode +
            " is linked in the account network, though not in the " +
            allEv.length +
            " sample posts below. Showing all sample posts:"
        );
        container.append(notice);
        filteredNote = "Showing " + Math.min(allEv.length, maxItems) + " sample matches";
      }
    } else {
      filteredNote =
        "Showing " + Math.min(allEv.length, maxItems) + " of " + allEv.length + " sample matches";
    }

    const shown = items.slice(0, maxItems);
    if (!shown.length) {
      container.append(el("div", "ev-empty", "No sample posts recorded for this group."));
      return filteredNote;
    }

    for (const ev of shown) {
      const card = el("article", "ev-card" + (selectedNode ? " is-highlighted" : ""));

      const head = el("div", "ev-head");
      const headLeft = el("div", "ev-head-left");

      const kindSpan = el("span", "ev-kind");
      const dot = el("span", "ev-kind-dot");
      dot.style.background = EDGE_COLORS[ev.kind] || "#566373";
      kindSpan.append(dot, document.createTextNode(plainSignalKind(ev.kind)));
      headLeft.append(kindSpan);

      headLeft.append(
        el(
          "span",
          "ev-gap",
          (ev.accounts || 0) + " accounts · " + formatExactPostDelta(ev.posts, ev.gap_seconds, group.platform)
        )
      );

      head.append(headLeft);

      if (ev.paraphrased) {
        const ovPct =
          typeof ev.word_overlap === "number"
            ? " (" + Math.round(ev.word_overlap * 100) + "% word overlap)"
            : "";
        head.append(el("span", "pill pill-paraphrase", "Different wording" + ovPct));
      }

      card.append(head);

      if (ev.example) {
        const anchor = el("div", "ev-anchor");
        const label = ev.kind === "shared URL" ? "Same link" : "Matched text";
        anchor.append(el("span", "ev-anchor-label", label), document.createTextNode(ev.example));
        card.append(anchor);
      }

      const postsGrid = el("div", "ev-posts");
      const showMs = group.platform === "bluesky" && (ev.gap_seconds || 0) < 5;

      for (const post of ev.posts || []) {
        const pBox = el(
          "div",
          "ev-post" + (selectedNode && post.account === selectedNode ? " is-node-match" : "")
        );

        const pHead = el("div", "ev-post-head");
        const acctWrap = el("span", "ev-post-acct");
        const acctHref = safeAccountUrl(post.account, group.platform);
        if (acctHref) {
          const a = el("a", "", post.account);
          a.href = acctHref;
          a.target = "_blank";
          a.rel = "noopener noreferrer";
          a.title =
            group.platform === "x"
              ? "Archived handle on X (most accounts were suspended)"
              : "Open Bluesky profile";
          acctWrap.append(a);
        } else {
          acctWrap.textContent = post.account || "Account";
        }

        const timeEl = el("time", "ev-post-time", formatUtcTime(post.time_utc, showMs));
        if (post.time_utc) timeEl.dateTime = post.time_utc;

        pHead.append(acctWrap, timeEl);
        pBox.append(pHead);

        if (post.thread) {
          pBox.append(el("span", "ev-post-thread", "Channel: " + post.thread));
        }

        pBox.append(el("p", "ev-post-text", post.text || ""));

        const gloss = findGloss(post.text);
        if (gloss) {
          const gEl = el("p", "ev-post-gloss");
          gEl.append(el("strong", "", "English"), document.createTextNode(gloss));
          pBox.append(gEl);
        }

        const pHref = safePostUrl(post, group.platform);
        if (pHref) {
          const pLink = el("a", "ev-post-link", "Open post on Bluesky ↗");
          pLink.href = pHref;
          pLink.target = "_blank";
          pLink.rel = "noopener noreferrer";
          pBox.append(pLink);
        }

        postsGrid.append(pBox);
      }

      card.append(postsGrid);
      container.append(card);
    }

    return filteredNote;
  }

  /* ---------- Section 1: Hero ---------- */

  function renderHero() {
    const datasets = BUNDLED_REPORT.datasets || [];
    const totalRaw = datasets.reduce((s, d) => s + (d.raw_posts || 0), 0);
    const val = BUNDLED_REPORT.validation || {};
    const tgVal = val.telegram_research || {};
    const xVal = val.x_ira || {};

    document.getElementById("nav-workbench-count").textContent = String(BUNDLED_REPORT.groups.length);
    document.getElementById("hero-wb-count").textContent = "(" + BUNDLED_REPORT.groups.length + " groups)";
    document.getElementById("kpi-raw").textContent = formatCompact(totalRaw);
    document.getElementById("kpi-groups").textContent = (BUNDLED_REPORT.total_groups || 0).toLocaleString();
    document.getElementById("kpi-tg-prec").textContent = formatPct(tgVal.precision, 1);
    document.getElementById("kpi-ira-purity").textContent = formatPct(xVal.category_purity, 1);

    const bsId = BUNDLED_REPORT.spotlights && BUNDLED_REPORT.spotlights.bluesky;
    const bsGroup = BUNDLED_REPORT.groups.find((g) => g.id === bsId) || BUNDLED_REPORT.groups[0];
    if (!bsGroup) return;

    document.getElementById("hero-proof-meta").textContent =
      "Group #" + bsGroup.id + " · " + bsGroup.accounts.length + " accounts";

    // Pick the Van Hollen / Schumer Iran-deal rewrite (34% word overlap, 0.1s apart), else lowest overlap, else evidence[0]
    const evList = bsGroup.evidence || [];
    const heroEv =
      evList.find((e) => (e.example || "").includes("van-hollen-uses-schumers")) ||
      evList
        .filter((e) => e.paraphrased && typeof e.word_overlap === "number")
        .sort((a, b) => a.word_overlap - b.word_overlap)[0] ||
      evList[0];

    const overlapBar = document.getElementById("hero-overlap-bar");
    overlapBar.replaceChildren();
    if (heroEv) {
      const ovText =
        typeof heroEv.word_overlap === "number"
          ? "Only " + Math.round(heroEv.word_overlap * 100) + "% word overlap"
          : "Different wording";
      overlapBar.append(
        el("span", "", formatExactPostDelta(heroEv.posts, heroEv.gap_seconds, "bluesky") + " · " + ovText),
        el("span", "", (bsGroup.paraphrased_matches || 0) + " rewritten stories found")
      );
    }

    const postsWrap = document.getElementById("hero-proof-posts");
    postsWrap.replaceChildren();
    if (heroEv && Array.isArray(heroEv.posts)) {
      for (const post of heroEv.posts.slice(0, 2)) {
        const card = el("div", "hero-post");
        const meta = el("div", "hero-post-meta");
        meta.append(
          el("strong", "", post.account),
          el("time", "", formatUtcTime(post.time_utc, true).slice(11))
        );
        const cleanText = (post.text || "").replace(/\s*https?:\/\/\S+\s*$/, "").trim();
        card.append(meta, el("p", "", cleanText));
        postsWrap.append(card);
      }
    }

    const topDomain = bsGroup.domains && bsGroup.domains[0];
    document.getElementById("hero-proof-url").textContent =
      (heroEv && heroEv.example) || (topDomain ? topDomain.domain : "—");

    const inspectBtn = document.getElementById("hero-inspect-btn");
    inspectBtn.textContent = "Open Group #" + bsGroup.id + " →";
    inspectBtn.addEventListener("click", () => {
      jumpToWorkbenchCase(bsGroup.id);
    });
  }

  /* ---------- Section 2: How It Works (Static 3-Step + Archive Table) ---------- */

  function renderMethod() {
    const datasets = BUNDLED_REPORT.datasets || [];
    const th = BUNDLED_REPORT.thresholds || {};
    const totalRaw = datasets.reduce((s, d) => s + (d.raw_posts || 0), 0);
    const totalKept = datasets.reduce((s, d) => s + (d.posts || 0), 0);
    const totalActive = datasets.reduce((s, d) => s + (d.active_accounts || 0), 0);
    const totalGroups = BUNDLED_REPORT.total_groups || datasets.reduce((s, d) => s + (d.candidate_groups || 0), 0);
    const totalHigh = datasets.reduce((s, d) => s + (d.high_priority_groups || 0), 0);
    const keepRatio = totalRaw > 0 ? totalKept / totalRaw : 0;

    document.getElementById("step-1-metric").textContent =
      formatCompact(totalRaw) + " → " + formatCompact(totalKept) + " (" + formatPct(keepRatio, 0) + ")";
    document.getElementById("step-1-desc").textContent =
      "Keeps political posts and strips out porn, casino and crypto ads, and everyday chat.";

    const winMin = th.window_minutes || 5;
    const repostSec = th.repost_window_seconds || 15;
    const minPairs = th.min_signals_per_pair || 2;
    const maxViral = th.max_accounts_per_signal || 100;
    const minAccts = th.min_accounts || 3;

    document.getElementById("step-2-metric").textContent =
      "≥" + minPairs + " matches · ≤" + winMin + " min";
    document.getElementById("step-2-desc").textContent =
      "Two accounts link only if they share a link, copied text, or instant repost (≤" +
      repostSec +
      "s) on at least " +
      minPairs +
      " separate posts. Viral items shared by over " +
      maxViral +
      " accounts are ignored.";

    document.getElementById("step-3-metric").textContent =
      totalGroups.toLocaleString() + " groups (" + minAccts + "+ accounts)";
    document.getElementById("step-3-desc").textContent =
      totalHigh.toLocaleString() +
      " suspected bot rings separated from " +
      Math.max(0, totalGroups - totalHigh).toLocaleString() +
      " news feeds and fast repost groups.";

    // Compact 3-row archive table
    const tbody = document.getElementById("archive-table-body");
    tbody.replaceChildren();
    const order = ["telegram_research", "x_ira", "bluesky"];
    const sorted = datasets.slice().sort((a, b) => order.indexOf(a.source) - order.indexOf(b.source));

    for (const ds of sorted) {
      const meta = sourceInfo(ds.source, ds.platform);
      const pct = ds.raw_posts > 0 ? ((ds.posts / ds.raw_posts) * 100).toFixed(1) + "%" : "—";
      const tr = document.createElement("tr");

      const tdName = document.createElement("td");
      tdName.append(el("span", "pill " + meta.pill, meta.full));

      tr.append(
        tdName,
        el("td", "num", formatCompact(ds.raw_posts)),
        el("td", "num", formatCompact(ds.posts) + " (" + pct + ")"),
        el("td", "num", (ds.active_accounts || 0).toLocaleString()),
        el("td", "num", (ds.candidate_groups || 0).toLocaleString())
      );
      tbody.append(tr);
    }

    // Total row
    const totRow = document.createElement("tr");
    const totLabel = document.createElement("td");
    totLabel.append(el("strong", "", "Total"));
    totRow.append(
      totLabel,
      el("td", "num", formatCompact(totalRaw)),
      el("td", "num", formatCompact(totalKept) + " (" + formatPct(keepRatio, 1) + ")"),
      el("td", "num", totalActive.toLocaleString()),
      el("td", "num", totalGroups.toLocaleString())
    );
    tbody.append(totRow);

    // Wire up inline case jump buttons inside the comparison table
    for (const btn of document.querySelectorAll("[data-jump-case]")) {
      btn.addEventListener("click", () => {
        const gid = Number(btn.dataset.jumpCase);
        if (!Number.isNaN(gid)) jumpToWorkbenchCase(gid);
      });
    }
  }

  /* ---------- Section 3: Accuracy ---------- */

  function renderValidation() {
    const val = BUNDLED_REPORT.validation || {};
    const tg = val.telegram_research || {};
    const x = val.x_ira || {};
    const bs = val.bluesky || {};

    const grid = document.getElementById("validation-grid");
    grid.replaceChildren();

    // Card 1: Telegram
    const tgCard = el("article", "val-card val-tg");
    const tgExample = el("p", "val-example");
    tgExample.append(
      el("strong", "", "Example: "),
      makeCaseButton(25, "Group #25"),
      document.createTextNode(" (93 accounts copying Russian drone scripts across 12 channels, 93/93 verified) and "),
      makeCaseButton(686, "Group #686"),
      document.createTextNode(" (18 pro-Ukrainian accounts, 16/18 verified).")
    );

    tgCard.append(
      buildValHead("Telegram", "pill-telegram", "University researchers"),
      buildValMetric(formatPct(tg.precision, 1), "matched researcher labels"),
      el(
        "p",
        "val-desc",
        (tg.labeled_detected_accounts || 0).toLocaleString() +
          " of " +
          (tg.detected_accounts || 0).toLocaleString() +
          " flagged accounts match outside propaganda labels (" +
          (tg.lift_over_active_base || 0).toFixed(1) +
          "× above the " +
          formatPct(tg.base_rate, 1) +
          " baseline). Catches both pro-Russian and pro-Ukrainian teams."
      ),
      buildValBar(
        [
          { pct: ((tg.pro_ru_detected || 0) / Math.max(tg.detected_accounts || 1, 1)) * 100, color: "#6b46a8" },
          { pct: Math.max(1.5, ((tg.pro_ua_detected || 0) / Math.max(tg.detected_accounts || 1, 1)) * 100), color: "#1a5fb4" },
        ],
        (tg.pro_ru_detected || 0).toLocaleString() + " pro-RU + " + (tg.pro_ua_detected || 0).toLocaleString() + " pro-UA",
        (tg.lift_over_active_base || 0).toFixed(1) + "× baseline"
      ),
      tgExample,
      buildValFacts([
        ["Groups found", (tg.detected_groups || 0).toLocaleString()],
        ["Baseline rate", formatPct(tg.base_rate, 1)],
      ])
    );
    grid.append(tgCard);

    // Card 2: Russian troll archive (X)
    const xCard = el("article", "val-card val-x");
    const xExample = el("p", "val-example");
    xExample.append(
      el("strong", "", "Example: "),
      makeCaseButton(865, "Group #865"),
      document.createTextNode(" (48 Russian accounts posting identical headlines within the same minute, 86% during St. Petersburg daytime).")
    );

    xCard.append(
      buildValHead("X trolls", "pill-x", "Russian troll archive (2014–2018)"),
      buildValMetric(formatPct(x.category_purity, 1), "clean team separation"),
      el(
        "p",
        "val-desc",
        "Groups " +
          (x.detected_accounts || 0).toLocaleString() +
          " known Russian troll accounts on X into " +
          (x.detected_groups || 0).toLocaleString() +
          " teams without reading profile labels, separating Russian-language squads from US right-wing and left-wing personas."
      ),
      buildValBar(
        [{ pct: (x.category_purity || 0) * 100, color: "#13294b" }],
        "Accounts grouped with matching role",
        formatPct(x.category_purity, 1)
      ),
      xExample,
      buildValFacts([
        ["Teams found", (x.detected_groups || 0).toLocaleString()],
        ["Accounts grouped", (x.detected_accounts || 0).toLocaleString()],
      ])
    );
    grid.append(xCard);

    // Card 3: Bluesky
    const bsCard = el("article", "val-card val-bs");
    const bsTotal = Math.max(bs.detected_groups || 1, 1);
    const bsExample = el("p", "val-example");
    bsExample.append(
      el("strong", "", "Example: "),
      makeCaseButton(20, "Group #20"),
      document.createTextNode(" (6 fake news accounts rewriting stories for nextstamina.com ~1s apart; nobody else links to it).")
    );

    bsCard.append(
      buildValHead("Bluesky", "pill-bluesky", "Public live capture"),
      buildValMetric(String(bs.high_priority_groups || 0), "suspected bot rings"),
      el(
        "p",
        "val-desc",
        "Separates " +
          (bs.high_priority_groups || 0) +
          " suspected bot rings from " +
          (bs.news_mirror_groups || 0) +
          " normal news feeds and " +
          (bs.repost_groups || 0) +
          " fast repost groups on unlabeled live posts."
      ),
      buildValBar(
        [
          { pct: Math.max(8, ((bs.high_priority_groups || 0) / bsTotal) * 100), color: "#d9531e" },
          { pct: ((bs.news_mirror_groups || 0) / bsTotal) * 100, color: "#8fa2b8" },
          { pct: ((bs.repost_groups || 0) / bsTotal) * 100, color: "#c9d4e0" },
        ],
        (bs.high_priority_groups || 0) + " bot rings",
        (bs.news_mirror_groups || 0) + " news feeds · " + (bs.repost_groups || 0) + " repost groups"
      ),
      bsExample,
      buildValFacts([
        ["Total groups", (bs.detected_groups || 0).toLocaleString()],
        ["Accounts mapped", (bs.detected_accounts || 0).toLocaleString()],
      ])
    );
    grid.append(bsCard);
  }

  function buildValHead(pillText, pillClass, sourceText) {
    const top = el("div", "val-card-top");
    top.append(el("span", "pill " + pillClass, pillText), el("span", "val-source", sourceText));
    return top;
  }

  function buildValMetric(big, label) {
    const row = el("div", "val-metric-row");
    row.append(el("strong", "val-big", big), el("span", "val-big-label", label));
    return row;
  }

  function buildValBar(segments, leftCaption, rightCaption) {
    const wrap = el("div", "val-bar-wrap");
    const bar = el("div", "val-bar");
    for (const seg of segments) {
      const s = el("span", "val-bar-seg");
      s.style.width = seg.pct.toFixed(1) + "%";
      s.style.background = seg.color;
      bar.append(s);
    }
    const cap = el("div", "val-bar-caption");
    cap.append(el("span", "", leftCaption), el("span", "", rightCaption));
    wrap.append(bar, cap);
    return wrap;
  }

  function buildValFacts(pairs) {
    const dl = el("dl", "val-facts");
    for (const [k, v] of pairs) {
      const box = document.createElement("div");
      box.append(el("dt", "", k), el("dd", "", v));
      dl.append(box);
    }
    return dl;
  }

  /* ---------- Section 4: Real Examples From The Data ---------- */

  function initSpotlights() {
    const tabsContainer = document.getElementById("spotlight-tabs");
    tabsContainer.replaceChildren();

    const spotlights = BUNDLED_REPORT.spotlights || {};
    const available = SPOTLIGHT_CONFIG.filter((cfg) => {
      const id = spotlights[cfg.key];
      return BUNDLED_REPORT.groups.some((g) => g.id === id);
    });

    if (!available.length) return;
    state.activeSpotlightKey = available[0].key;

    for (const cfg of available) {
      const gid = spotlights[cfg.key];
      const group = BUNDLED_REPORT.groups.find((g) => g.id === gid);
      const tab = el("button", "spot-tab");
      tab.type = "button";
      tab.role = "tab";
      tab.dataset.spotKey = cfg.key;
      tab.setAttribute("aria-selected", String(cfg.key === state.activeSpotlightKey));

      tab.append(
        el("span", "spot-tab-plat", cfg.plat + " · #" + group.id),
        el("span", "spot-tab-title", cfg.shortTitle),
        el("span", "spot-tab-meta", group.accounts.length + " accts · " + formatGap(group.median_gap_seconds, group.platform))
      );

      tab.addEventListener("click", () => {
        state.activeSpotlightKey = cfg.key;
        state.spotlightSelectedNode = null;
        for (const b of tabsContainer.querySelectorAll(".spot-tab")) {
          b.setAttribute("aria-selected", String(b.dataset.spotKey === cfg.key));
        }
        renderActiveSpotlight();
      });

      tabsContainer.append(tab);
    }

    document.getElementById("spot-clear-node").addEventListener("click", () => {
      state.spotlightSelectedNode = null;
      if (state.spotlightGraphCtrl) state.spotlightGraphCtrl.select(null);
      updateSpotlightEvidence();
    });

    document.getElementById("spot-open-wb").addEventListener("click", () => {
      const gid = spotlights[state.activeSpotlightKey];
      if (gid !== undefined) jumpToWorkbenchCase(gid);
    });

    renderActiveSpotlight();
  }

  function getActiveSpotlightGroup() {
    const spotlights = BUNDLED_REPORT.spotlights || {};
    const gid = spotlights[state.activeSpotlightKey];
    return BUNDLED_REPORT.groups.find((g) => g.id === gid) || BUNDLED_REPORT.groups[0];
  }

  function renderActiveSpotlight() {
    const group = getActiveSpotlightGroup();
    if (!group) return;

    const sInfo = sourceInfo(group.source, group.platform);

    const badges = document.getElementById("spot-badges");
    badges.replaceChildren(
      el("span", "pill pill-id", "Group #" + group.id),
      el("span", "pill " + sInfo.pill, sInfo.full),
      el("span", "pill pill-tactic", plainTacticLabel(group)),
      el(
        "span",
        "pill " + (group.priority_tier === 1 ? "pill-tier1" : "pill-tier2"),
        group.priority_tier === 1 ? "Suspected bot ring" : "News feed / reposts"
      )
    );

    document.getElementById("spot-headline").textContent = group.headline || "Group #" + group.id;

    const stats = document.getElementById("spot-stats");
    stats.replaceChildren();
    const tiles = [
      ["Accounts", group.accounts.length.toLocaleString()],
      ["How tightly linked", Math.round((group.pair_density || 0) * 100) + "%"],
      ["Typical gap", formatGap(group.median_gap_seconds, group.platform)],
      [
        group.paraphrased_matches > 0 ? "Rewritten stories" : "Shared matches",
        group.paraphrased_matches > 0
          ? String(group.paraphrased_matches)
          : (group.matching_signals || 0).toLocaleString(),
      ],
    ];
    for (const [label, val] of tiles) {
      const t = el("div", "stat-tile");
      t.append(el("span", "", label), el("strong", "", val));
      stats.append(t);
    }

    const brief = splitBehavioralAndProvenance(group);
    document.getElementById("spot-behavior-text").textContent = brief.behaviorText;

    const chipsEl = document.getElementById("spot-signal-chips");
    chipsEl.replaceChildren();
    for (const ch of getBehavioralChips(group)) {
      chipsEl.append(el("span", "signal-chip" + (ch.isAlert ? " is-alert" : ""), ch.label));
    }

    const provBox = document.getElementById("spot-provenance-box");
    provBox.classList.toggle("is-unattributed", brief.isUnattributed);
    document.getElementById("spot-provenance-title").textContent = brief.provenanceTitle;
    document.getElementById("spot-provenance-text").textContent = brief.provenanceText;

    const domWrap = document.getElementById("spot-domains");
    domWrap.replaceChildren();
    for (const d of (group.domains || []).slice(0, 3)) {
      const chip = el("span", "domain-chip");
      chip.append(
        el("strong", "", d.domain),
        document.createTextNode(" " + Math.round((d.group_share || 0) * 100) + "% (" + d.outside_accounts + " outside)")
      );
      if (d.is_exclusive) chip.append(el("span", "pill pill-exclusive", "Only this group"));
      if (d.is_state_media) chip.append(el("span", "pill pill-state", "State media"));
      domWrap.append(chip);
    }

    const graphEl = document.getElementById("spot-graph");
    state.spotlightGraphCtrl = window.PropnetGraph.mount(graphEl, {
      edges: group.graph_edges,
      maxNodes: 18,
      onSelect: (acct) => {
        state.spotlightSelectedNode = acct;
        updateSpotlightEvidence();
      },
    });
    renderEdgeLegend(document.getElementById("spot-edge-legend"), group.graph_edges);

    const gMeta = document.getElementById("spot-graph-meta");
    if (state.spotlightGraphCtrl) {
      const { shownNodes, shownEdges } = state.spotlightGraphCtrl;
      gMeta.textContent =
        group.accounts.length > shownNodes
          ? "Top " + shownNodes + " of " + group.accounts.length + " accounts (" + shownEdges + " links)"
          : "All " + shownNodes + " accounts (" + shownEdges + " links)";
    }

    window.PropnetGraph.mountSchedule(document.getElementById("spot-schedule"), {
      hourly: group.hourly_utc,
      schedule: group.schedule,
    });

    updateSpotlightEvidence();
  }

  function updateSpotlightEvidence() {
    const group = getActiveSpotlightGroup();
    if (!group) return;
    const node = state.spotlightSelectedNode;
    const statusEl = document.getElementById("spot-node-status");
    const clearBtn = document.getElementById("spot-clear-node");

    if (node) {
      statusEl.textContent = "Showing links and posts for " + node;
      clearBtn.hidden = false;
    } else {
      statusEl.textContent = "Click any account to highlight its links and filter posts";
      clearBtn.hidden = true;
    }

    const note = renderEvidenceCards(document.getElementById("spot-evidence"), group, {
      selectedNode: node,
      maxItems: 2,
    });
    document.getElementById("spot-evidence-meta").textContent = note;
  }

  /* ---------- Section 5: Investigator ---------- */

  function initWorkbench() {
    const searchInput = document.getElementById("wb-search");
    const sourceSel = document.getElementById("wb-source");
    const tacticSel = document.getElementById("wb-tactic");
    const tierSel = document.getElementById("wb-tier");
    const sortSel = document.getElementById("wb-sort");

    searchInput.addEventListener("input", () => {
      state.filters.search = searchInput.value;
      applyWorkbenchFilters();
    });
    sourceSel.addEventListener("change", () => {
      state.filters.source = sourceSel.value;
      applyWorkbenchFilters();
    });
    tacticSel.addEventListener("change", () => {
      state.filters.tactic = tacticSel.value;
      applyWorkbenchFilters();
    });
    tierSel.addEventListener("change", () => {
      state.filters.tier = tierSel.value;
      applyWorkbenchFilters();
    });
    sortSel.addEventListener("change", () => {
      state.filters.sort = sortSel.value;
      applyWorkbenchFilters();
    });

    document.getElementById("wb-clear").addEventListener("click", () => {
      resetWorkbenchFilters();
      applyWorkbenchFilters();
    });

    const listEl = document.getElementById("wb-list");
    listEl.addEventListener("keydown", (evt) => {
      if (evt.key !== "ArrowDown" && evt.key !== "ArrowUp") return;
      if (!state.filteredGroups.length) return;
      evt.preventDefault();
      const idx = state.filteredGroups.findIndex((g) => g.id === state.selectedGroupId);
      const nextIdx =
        evt.key === "ArrowDown"
          ? Math.min(state.filteredGroups.length - 1, idx + 1)
          : Math.max(0, idx - 1);
      const nextGroup = state.filteredGroups[nextIdx];
      if (nextGroup) {
        selectWorkbenchGroup(nextGroup.id, true);
      }
    });

    document.getElementById("wb-clear-node").addEventListener("click", () => {
      state.wbSelectedNode = null;
      if (state.wbGraphCtrl) state.wbGraphCtrl.select(null);
      updateWorkbenchEvidenceAndRoster();
    });

    document.getElementById("wb-export-json").addEventListener("click", exportSelectedJson);
    document.getElementById("wb-export-csv").addEventListener("click", exportSelectedCsv);
    document.getElementById("wb-copy-link").addEventListener("click", copyShareLink);

    document.getElementById("json-import").addEventListener("change", handleLocalImport);
    document.getElementById("reset-report").addEventListener("click", () => {
      state.workbenchReport = BUNDLED_REPORT;
      state.isLocalReport = false;
      state.localFilename = "";
      document.getElementById("json-import").value = "";
      document.getElementById("import-error").hidden = true;
      updateSourceStatus();
      applyWorkbenchFilters();
    });

    updateSourceStatus();
    applyWorkbenchFilters();

    const params = new URLSearchParams(window.location.search);
    const caseParam = params.get("case");
    if (caseParam) {
      const targetId = Number(caseParam);
      if (!Number.isNaN(targetId)) {
        const exists = state.workbenchReport.groups.some((g) => g.id === targetId);
        if (exists) {
          jumpToWorkbenchCase(targetId);
        }
      }
    }
  }

  function resetWorkbenchFilters() {
    state.filters = { search: "", source: "all", tactic: "all", tier: "all", sort: "priority" };
    document.getElementById("wb-search").value = "";
    document.getElementById("wb-source").value = "all";
    document.getElementById("wb-tactic").value = "all";
    document.getElementById("wb-tier").value = "all";
    document.getElementById("wb-sort").value = "priority";
  }

  function updateSourceStatus() {
    const groups = state.workbenchReport.groups || [];
    const hasUnaliased = groups.some(
      (g) => Array.isArray(g.accounts) && g.accounts.some((a) => String(a).startsWith("did:plc:"))
    );
    const dot = document.getElementById("wb-source-dot");
    const status = document.getElementById("wb-source-status");
    const resetBtn = document.getElementById("reset-report");

    dot.classList.toggle("is-local", state.isLocalReport);
    resetBtn.hidden = !state.isLocalReport;
    document.getElementById("nav-workbench-count").textContent = String(groups.length);

    if (state.isLocalReport) {
      status.textContent =
        "Local file: " +
        state.localFilename +
        " (" +
        groups.length +
        " groups" +
        (hasUnaliased ? ", direct profile links enabled" : "") +
        ")";
    } else {
      status.textContent =
        "Bundled dataset (" + groups.length + " groups · Bluesky/Telegram IDs anonymized)";
    }
  }

  function handleLocalImport(evt) {
    const file = evt.target.files && evt.target.files[0];
    const errEl = document.getElementById("import-error");
    errEl.hidden = true;
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      try {
        const parsed = JSON.parse(String(reader.result || ""));
        if (!parsed || !Array.isArray(parsed.groups) || !parsed.groups.length) {
          throw new Error("JSON must contain a non-empty 'groups' array.");
        }
        const sample = parsed.groups[0];
        if (sample.id === undefined || !Array.isArray(sample.accounts)) {
          throw new Error("Group records are missing 'id' or 'accounts'.");
        }
        state.workbenchReport = parsed;
        state.isLocalReport = true;
        state.localFilename = file.name;
        updateSourceStatus();
        resetWorkbenchFilters();
        applyWorkbenchFilters();
      } catch (err) {
        errEl.textContent = "Could not load file: " + (err && err.message ? err.message : "Invalid JSON");
        errEl.hidden = false;
      }
    };
    reader.onerror = () => {
      errEl.textContent = "Failed to read the selected file.";
      errEl.hidden = false;
    };
    reader.readAsText(file);
  }

  function matchesSearch(group, q) {
    if (!q) return true;
    const needle = q.trim().toLowerCase();
    if (!needle) return true;
    if (String(group.id) === needle || ("#" + group.id) === needle || ("group " + group.id) === needle) {
      return true;
    }
    const hayParts = [
      String(group.id),
      group.headline || "",
      group.why_flagged || "",
      plainTacticLabel(group),
      group.source || "",
      group.platform || "",
      (group.schedule && group.schedule.label) || "",
      ...(group.signals_explained || []),
      ...(group.accounts || []),
      ...(group.domains || []).map((d) => d.domain || ""),
      ...(group.archive_categories || []).map((c) => plainCategory(c.category) + " " + c.category),
    ];
    for (const ev of group.evidence || []) {
      if (ev.example) hayParts.push(ev.example);
      for (const p of ev.posts || []) {
        if (p.text) hayParts.push(p.text);
        if (p.thread) hayParts.push(p.thread);
        if (p.account) hayParts.push(p.account);
      }
    }
    return hayParts.join(" ").toLowerCase().includes(needle);
  }

  function sortGroups(list, mode) {
    const arr = list.slice();
    if (mode === "accounts") {
      arr.sort((a, b) => (b.accounts.length || 0) - (a.accounts.length || 0) || a.id - b.id);
    } else if (mode === "density") {
      arr.sort((a, b) => (b.pair_density || 0) - (a.pair_density || 0) || b.accounts.length - a.accounts.length);
    } else if (mode === "gap") {
      arr.sort((a, b) => (a.median_gap_seconds ?? 1e12) - (b.median_gap_seconds ?? 1e12) || b.accounts.length - a.accounts.length);
    } else if (mode === "paraphrased") {
      arr.sort((a, b) => (b.paraphrased_matches || 0) - (a.paraphrased_matches || 0) || (a.priority_tier || 2) - (b.priority_tier || 2));
    } else {
      const tacticRank = {
        paraphrased_link_ring: 0,
        exclusive_domain_ring: 1,
        cross_channel_script: 2,
        synchronized_blast: 3,
        news_mirror: 4,
        fast_repost_ring: 5,
      };
      arr.sort((a, b) => {
        const tierDiff = (a.priority_tier || 2) - (b.priority_tier || 2);
        if (tierDiff !== 0) return tierDiff;
        const rA = tacticRank[a.tactic] ?? 9;
        const rB = tacticRank[b.tactic] ?? 9;
        if (rA !== rB && (rA <= 1 || rB <= 1)) return rA - rB;
        return (b.matching_signals || 0) - (a.matching_signals || 0) || b.accounts.length - a.accounts.length;
      });
    }
    return arr;
  }

  function applyWorkbenchFilters() {
    const allGroups = state.workbenchReport.groups || [];
    const { search, source, tactic, tier, sort } = state.filters;

    const filtered = allGroups.filter((g) => {
      if (source !== "all" && g.source !== source) return false;
      if (tactic !== "all" && g.tactic !== tactic) return false;
      if (tier !== "all" && String(g.priority_tier) !== tier) return false;
      return matchesSearch(g, search);
    });

    state.filteredGroups = sortGroups(filtered, sort);

    document.getElementById("wb-count-summary").textContent =
      "Showing " + state.filteredGroups.length + " of " + allGroups.length + " groups";

    renderWorkbenchList();

    if (state.filteredGroups.length) {
      const stillVisible = state.filteredGroups.some((g) => g.id === state.selectedGroupId);
      if (!stillVisible) {
        selectWorkbenchGroup(state.filteredGroups[0].id, false);
      } else {
        renderWorkbenchInspector(getSelectedWorkbenchGroup());
      }
    } else {
      state.selectedGroupId = null;
      renderEmptyInspector();
    }
  }

  function renderWorkbenchList() {
    const listEl = document.getElementById("wb-list");
    listEl.replaceChildren();

    if (!state.filteredGroups.length) {
      listEl.append(
        el("div", "wb-list-empty", "No groups match those filters. Try clearing your search or changing filters.")
      );
      return;
    }

    const frag = document.createDocumentFragment();
    for (const group of state.filteredGroups) {
      const sInfo = sourceInfo(group.source, group.platform);
      const btn = el("button", "wb-item");
      btn.type = "button";
      btn.role = "option";
      btn.dataset.groupId = String(group.id);
      btn.setAttribute("aria-selected", String(group.id === state.selectedGroupId));

      const top = el("div", "wb-item-top");
      top.append(
        el("span", "pill " + sInfo.pill, sInfo.label),
        el("span", "wb-item-id", "#" + group.id),
        el("span", "pill pill-tactic", plainTacticLabel(group))
      );

      const headline = el("div", "wb-item-headline", group.headline || "Group #" + group.id);

      const meta = el("div", "wb-item-meta");
      meta.append(
        el("span", "", group.accounts.length + " accts"),
        el("span", "", formatGap(group.median_gap_seconds, group.platform)),
        el("span", "", Math.round((group.pair_density || 0) * 100) + "% linked")
      );

      if (group.paraphrased_matches > 0) {
        meta.append(el("span", "wb-item-flag", group.paraphrased_matches + " rewritten"));
      } else if (group.domains && group.domains.some((d) => d.is_exclusive)) {
        meta.append(el("span", "wb-item-flag", "Single site"));
      } else if (group.researcher_labels && group.researcher_labels.pro_ua_accounts > 0) {
        meta.append(el("span", "", "Pro-UA " + group.researcher_labels.pro_ua_accounts + "/" + group.accounts.length));
      } else if (group.researcher_labels && group.researcher_labels.pro_ru_accounts > 0) {
        meta.append(el("span", "", "Pro-RU " + group.researcher_labels.pro_ru_accounts + "/" + group.accounts.length));
      } else if (group.archive_categories && group.archive_categories[0]) {
        meta.append(el("span", "", plainCategory(group.archive_categories[0].category)));
      }

      btn.append(top, headline, meta);
      btn.addEventListener("click", () => selectWorkbenchGroup(group.id, false));
      frag.append(btn);
    }

    listEl.append(frag);
  }

  function getSelectedWorkbenchGroup() {
    return (state.workbenchReport.groups || []).find((g) => g.id === state.selectedGroupId) || null;
  }

  function selectWorkbenchGroup(groupId, scrollListItem) {
    state.selectedGroupId = groupId;
    state.wbSelectedNode = null;

    const listEl = document.getElementById("wb-list");
    for (const item of listEl.querySelectorAll(".wb-item")) {
      const match = Number(item.dataset.groupId) === groupId;
      item.setAttribute("aria-selected", String(match));
      if (match && scrollListItem) {
        item.scrollIntoView({ block: "nearest" });
      }
    }

    const group = getSelectedWorkbenchGroup();
    if (group) {
      renderWorkbenchInspector(group);
    }
  }

  function jumpToWorkbenchCase(groupId) {
    const exists = (state.workbenchReport.groups || []).some((g) => g.id === groupId);
    if (!exists) {
      state.workbenchReport = BUNDLED_REPORT;
      state.isLocalReport = false;
      state.localFilename = "";
      updateSourceStatus();
    }

    if (!state.filteredGroups.some((g) => g.id === groupId)) {
      resetWorkbenchFilters();
      applyWorkbenchFilters();
    }

    selectWorkbenchGroup(groupId, true);
    const wbSection = document.getElementById("workbench");
    if (wbSection) {
      wbSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  function renderEmptyInspector() {
    document.getElementById("wb-badges").replaceChildren();
    document.getElementById("wb-headline").textContent = "No group selected";
    document.getElementById("wb-behavior-text").textContent =
      "Clear your filters on the left to browse groups.";
    document.getElementById("wb-signal-chips").replaceChildren();
    document.getElementById("wb-provenance-text").textContent = "—";
    document.getElementById("wb-provenance-tags").replaceChildren();
    document.getElementById("wb-metrics").replaceChildren();
    document.getElementById("wb-signal-breakdown").replaceChildren();
    document.getElementById("wb-schedule").replaceChildren();
    document.getElementById("wb-domains").replaceChildren();
    document.getElementById("wb-graph").replaceChildren();
    document.getElementById("wb-evidence").replaceChildren();
  }

  function renderWorkbenchInspector(group) {
    if (!group) return;
    const sInfo = sourceInfo(group.source, group.platform);

    const badges = document.getElementById("wb-badges");
    badges.replaceChildren(
      el("span", "pill pill-id", "Group #" + group.id),
      el("span", "pill " + sInfo.pill, sInfo.full),
      el("span", "pill pill-tactic", plainTacticLabel(group)),
      el(
        "span",
        "pill " + (group.priority_tier === 1 ? "pill-tier1" : "pill-tier2"),
        group.priority_tier === 1 ? "Suspected bot ring" : "News feed / reposts"
      )
    );
    document.getElementById("wb-headline").textContent = group.headline || "Group #" + group.id;

    const brief = splitBehavioralAndProvenance(group);
    document.getElementById("wb-behavior-text").textContent = brief.behaviorText;

    const sigChips = document.getElementById("wb-signal-chips");
    sigChips.replaceChildren();
    for (const ch of getBehavioralChips(group)) {
      sigChips.append(el("span", "signal-chip" + (ch.isAlert ? " is-alert" : ""), ch.label));
    }

    const provBox = document.getElementById("wb-provenance-box");
    provBox.classList.toggle("is-unattributed", brief.isUnattributed);
    document.getElementById("wb-provenance-title").textContent = brief.provenanceTitle;
    document.getElementById("wb-provenance-text").textContent = brief.provenanceText;

    const provTags = document.getElementById("wb-provenance-tags");
    provTags.replaceChildren();
    for (const t of brief.provenanceTags) {
      provTags.append(el("span", "prov-tag", t));
    }

    const metrics = document.getElementById("wb-metrics");
    metrics.replaceChildren();
    const cells = [
      ["Accounts", group.accounts.length.toLocaleString()],
      ["Linked pairs", (group.corroborated_pairs || 0).toLocaleString()],
      ["How tightly linked", Math.round((group.pair_density || 0) * 100) + "%"],
      ["Shared matches", (group.matching_signals || 0).toLocaleString()],
      ["Typical gap", formatGap(group.median_gap_seconds, group.platform)],
      ["Matches / account", typeof group.signals_per_account === "number" ? group.signals_per_account.toFixed(1) : "—"],
    ];
    for (const [k, v] of cells) {
      const tile = el("div", "stat-tile");
      tile.append(el("span", "", k), el("strong", "", v));
      metrics.append(tile);
    }

    renderSignalBreakdown(group);

    window.PropnetGraph.mountSchedule(document.getElementById("wb-schedule"), {
      hourly: group.hourly_utc,
      schedule: group.schedule,
    });

    renderDomainsPanel(group);

    state.wbGraphCtrl = window.PropnetGraph.mount(document.getElementById("wb-graph"), {
      edges: group.graph_edges,
      maxNodes: 18,
      onSelect: (acct) => {
        state.wbSelectedNode = acct;
        updateWorkbenchEvidenceAndRoster();
      },
    });
    renderEdgeLegend(document.getElementById("wb-edge-legend"), group.graph_edges);

    const gMeta = document.getElementById("wb-graph-meta");
    if (state.wbGraphCtrl) {
      const { shownNodes, shownEdges } = state.wbGraphCtrl;
      gMeta.textContent =
        group.accounts.length > shownNodes
          ? "Showing top " + shownNodes + " of " + group.accounts.length + " accounts (" + shownEdges + " links)"
          : "All " + shownNodes + " accounts (" + shownEdges + " links)";
    }

    document.getElementById("wb-roster-details").open = false;

    updateWorkbenchEvidenceAndRoster();
  }

  function renderSignalBreakdown(group) {
    const wrap = document.getElementById("wb-signal-breakdown");
    wrap.replaceChildren();
    const entries = Object.entries(group.signal_breakdown || {}).sort((a, b) => b[1] - a[1]);
    const total = entries.reduce((s, [, count]) => s + count, 0);

    const top = el("div", "sb-top");
    top.append(
      el("span", "", "What linked them"),
      el(
        "span",
        "",
        total.toLocaleString() +
          " shared matches" +
          (group.paraphrased_matches > 0 ? " · " + group.paraphrased_matches + " rewritten stories" : "")
      )
    );

    const bar = el("div", "sb-bar");
    const legend = el("div", "sb-legend");

    for (const [kind, count] of entries) {
      const pct = total > 0 ? (count / total) * 100 : 0;
      const seg = document.createElement("span");
      seg.style.width = Math.max(2, pct).toFixed(1) + "%";
      seg.style.background = EDGE_COLORS[kind] || "#566373";
      bar.append(seg);

      const item = el("span", "sb-legend-item");
      const dot = el("span", "sb-dot");
      dot.style.background = EDGE_COLORS[kind] || "#566373";
      item.append(
        dot,
        document.createTextNode(plainSignalKind(kind) + ": " + count.toLocaleString() + " (" + Math.round(pct) + "%)")
      );
      legend.append(item);
    }

    wrap.append(top, bar, legend);
  }

  function renderDomainsPanel(group) {
    const panel = document.getElementById("wb-domains");
    const meta = document.getElementById("wb-domains-meta");
    panel.replaceChildren();

    const domains = group.domains || [];
    if (!domains.length) {
      meta.textContent = "No web links";
      panel.append(
        el("p", "domains-empty", "These accounts matched on copied text or reposts without external web links.")
      );
      return;
    }

    const exclCount = domains.filter((d) => d.is_exclusive).length;
    const stateCount = domains.filter((d) => d.is_state_media).length;
    const metaParts = [domains.length + " top site" + (domains.length === 1 ? "" : "s")];
    if (exclCount) metaParts.push(exclCount + " group-only");
    if (stateCount) metaParts.push(stateCount + " state media");
    meta.textContent = metaParts.join(" · ");

    for (const d of domains.slice(0, 5)) {
      const row = el("div", "domain-row");
      const top = el("div", "domain-row-top");
      top.append(el("span", "domain-name", d.domain));

      const badges = el("span", "domain-badges");
      if (d.is_exclusive) {
        badges.append(el("span", "pill pill-exclusive", "Only this group links here"));
      }
      if (d.is_state_media) {
        badges.append(el("span", "pill pill-state", "State media"));
      }
      top.append(badges);

      const track = el("div", "domain-bar-track");
      const fill = el(
        "div",
        "domain-bar-fill" + (d.is_exclusive ? " is-exclusive" : d.is_state_media ? " is-state" : "")
      );
      fill.style.width = Math.max(4, Math.min(100, (d.group_share || 0) * 100)).toFixed(1) + "%";
      track.append(fill);

      const info = el(
        "div",
        "domain-row-meta",
        Math.round((d.group_share || 0) * 100) +
          "% of group links · " +
          (d.posts || 0).toLocaleString() +
          " posts by " +
          (d.accounts || 0) +
          " accounts · " +
          (d.outside_accounts || 0).toLocaleString() +
          " outside accounts"
      );

      row.append(top, track, info);
      panel.append(row);
    }
  }

  function updateWorkbenchEvidenceAndRoster() {
    const group = getSelectedWorkbenchGroup();
    if (!group) return;

    const node = state.wbSelectedNode;
    const statusEl = document.getElementById("wb-node-status");
    const clearBtn = document.getElementById("wb-clear-node");

    if (node) {
      const edgeCount = (group.graph_edges || []).filter((e) => e.from === node || e.to === node).length;
      statusEl.textContent =
        "Filtering by " + node + " (" + edgeCount + " link" + (edgeCount === 1 ? "" : "s") + " shown)";
      clearBtn.hidden = false;
    } else {
      statusEl.textContent = "Click any account to highlight its links and filter matched posts below";
      clearBtn.hidden = true;
    }

    const rosterSummary = document.getElementById("wb-roster-summary");
    rosterSummary.textContent =
      "All accounts (" + group.accounts.length.toLocaleString() + ")";

    const rosterGrid = document.getElementById("wb-roster-grid");
    rosterGrid.replaceChildren();
    const frag = document.createDocumentFragment();
    for (const acct of group.accounts) {
      const href = safeAccountUrl(acct, group.platform);
      const inGraph = state.wbGraphCtrl && state.wbGraphCtrl.hasNode(acct);
      if (inGraph) {
        const b = el("button", "roster-chip" + (acct === node ? " is-active" : ""), acct);
        b.type = "button";
        b.title = "Highlight " + acct + " in network and posts";
        b.addEventListener("click", () => {
          const next = state.wbSelectedNode === acct ? null : acct;
          state.wbSelectedNode = next;
          if (state.wbGraphCtrl) state.wbGraphCtrl.select(next);
          updateWorkbenchEvidenceAndRoster();
        });
        frag.append(b);
      } else if (href) {
        const a = el("a", "roster-chip", acct);
        a.href = href;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        frag.append(a);
      } else {
        frag.append(el("span", "roster-chip", acct));
      }
    }
    rosterGrid.append(frag);

    const note = renderEvidenceCards(document.getElementById("wb-evidence"), group, {
      selectedNode: node,
      maxItems: 50,
    });
    document.getElementById("wb-evidence-meta").textContent = note;
  }

  /* ---------- Export Helpers ---------- */

  function downloadBlob(filename, mime, content) {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function exportSelectedJson() {
    const group = getSelectedWorkbenchGroup();
    if (!group) return;
    downloadBlob(
      "propnet-group-" + group.id + ".json",
      "application/json;charset=utf-8",
      JSON.stringify(group, null, 2)
    );
  }

  function csvCell(val) {
    const s = val === null || val === undefined ? "" : String(val);
    if (/[",\r\n]/.test(s)) {
      return '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
  }

  function exportSelectedCsv() {
    const group = getSelectedWorkbenchGroup();
    if (!group) return;
    const headers = [
      "group_id",
      "platform",
      "source",
      "group_type",
      "pattern",
      "headline",
      "group_accounts",
      "tightness",
      "typical_gap_seconds",
      "match_type",
      "matched_accounts",
      "gap_seconds",
      "different_wording",
      "word_overlap",
      "shared_anchor",
      "post_account",
      "post_time_utc",
      "channel",
      "post_text",
    ];
    const rows = [headers.map(csvCell).join(",")];

    for (const ev of group.evidence || []) {
      const posts = ev.posts && ev.posts.length ? ev.posts : [{}];
      for (const p of posts) {
        rows.push(
          [
            group.id,
            group.platform,
            group.source,
            group.priority_tier === 1 ? "Suspected bot ring" : "News feed / reposts",
            plainTacticLabel(group),
            group.headline,
            group.accounts.length,
            group.pair_density,
            group.median_gap_seconds,
            plainSignalKind(ev.kind),
            ev.accounts,
            ev.gap_seconds,
            Boolean(ev.paraphrased),
            ev.word_overlap ?? "",
            ev.example || "",
            p.account || "",
            p.time_utc || "",
            p.thread || "",
            p.text || "",
          ]
            .map(csvCell)
            .join(",")
        );
      }
    }

    downloadBlob(
      "propnet-group-" + group.id + ".csv",
      "text/csv;charset=utf-8",
      rows.join("\r\n")
    );
  }

  function copyShareLink() {
    const group = getSelectedWorkbenchGroup();
    if (!group) return;
    const url = new URL(window.location.href);
    url.searchParams.set("case", String(group.id));
    url.hash = "workbench";
    const btn = document.getElementById("wb-copy-link");

    const done = () => {
      const prev = btn.textContent;
      btn.textContent = "Copied!";
      setTimeout(() => {
        btn.textContent = prev;
      }, 1600);
    };

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url.toString()).then(done).catch(() => {
        window.history.replaceState(null, "", url.toString());
        done();
      });
    } else {
      window.history.replaceState(null, "", url.toString());
      done();
    }
  }

  /* ---------- Sticky Nav Scroll-Spy ---------- */

  function initScrollSpy() {
    const sections = ["overview", "method", "proof", "spotlights", "workbench"]
      .map((id) => document.getElementById(id))
      .filter(Boolean);
    const navLinks = new Map();
    for (const a of document.querySelectorAll(".site-nav a[data-nav]")) {
      navLinks.set(a.dataset.nav, a);
    }
    if (!("IntersectionObserver" in window) || !sections.length) return;

    const obs = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (!visible.length) return;
        const activeId = visible[0].target.id;
        for (const [id, link] of navLinks) {
          if (id === activeId) {
            link.setAttribute("aria-current", "location");
          } else {
            link.removeAttribute("aria-current");
          }
        }
      },
      { rootMargin: "-18% 0px -55% 0px", threshold: [0.05, 0.25, 0.5] }
    );

    sections.forEach((s) => obs.observe(s));
  }

  /* ---------- Boot ---------- */

  renderHero();
  renderMethod();
  renderValidation();
  initSpotlights();
  initWorkbench();
  initScrollSpy();
})();
