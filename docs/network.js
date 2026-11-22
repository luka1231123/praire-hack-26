(function () {
  "use strict";

  const graphs = new WeakMap();

  const EDGE_COLORS = {
    "reused text": "#1a5fb4",
    "shared URL": "#d9531e",
    "cross-channel text": "#6b46a8",
    "shared repost": "#14855c",
  };

  function shortLabel(name, maxLen) {
    if (!name) return "";
    if (name.startsWith("did:plc:")) {
      return "did:…" + name.slice(-8);
    }
    if (name.length <= maxLen) return name;
    return name.slice(0, maxLen - 1) + "…";
  }

  /**
   * Mount an interactive radial account network graph.
   * Shows up to `maxNodes` most-connected accounts so labels stay readable.
   */
  function mount(container, options) {
    if (!container) return null;
    const prev = graphs.get(container);
    if (prev) prev.disconnect();
    container.replaceChildren();

    const opts = options || {};
    const allEdges = Array.isArray(opts.edges) ? opts.edges : [];
    const maxNodes = opts.maxNodes || 18;
    const onSelect = typeof opts.onSelect === "function" ? opts.onSelect : null;

    if (!allEdges.length) {
      const empty = document.createElement("p");
      empty.className = "graph-empty";
      empty.textContent = "No account links available for this group.";
      container.append(empty);
      return { select: function () {}, shownNodes: 0, shownEdges: 0, totalEdgeNodes: 0, hasNode: function () { return false; } };
    }

    const score = new Map();
    const degree = new Map();
    for (const e of allEdges) {
      const w = Number(e.count) || 1;
      score.set(e.from, (score.get(e.from) || 0) + w);
      score.set(e.to, (score.get(e.to) || 0) + w);
      degree.set(e.from, (degree.get(e.from) || 0) + 1);
      degree.set(e.to, (degree.get(e.to) || 0) + 1);
    }

    const allNodes = Array.from(score.keys()).sort((a, b) => {
      const diff = (score.get(b) || 0) - (score.get(a) || 0);
      if (diff !== 0) return diff;
      const degDiff = (degree.get(b) || 0) - (degree.get(a) || 0);
      if (degDiff !== 0) return degDiff;
      return a.localeCompare(b);
    });

    const selectedSet = new Set(allNodes.slice(0, maxNodes));
    const visibleEdges = allEdges.filter(
      (e) => selectedSet.has(e.from) && selectedSet.has(e.to)
    );

    const activeNodes = allNodes.filter((n) =>
      visibleEdges.some((e) => e.from === n || e.to === n)
    );

    if (!activeNodes.length) {
      const empty = document.createElement("p");
      empty.className = "graph-empty";
      empty.textContent = "No internal links among top accounts.";
      container.append(empty);
      return { select: function () {}, shownNodes: 0, shownEdges: 0, totalEdgeNodes: allNodes.length, hasNode: function () { return false; } };
    }

    const neighbors = new Map();
    const nodeEdgeCount = new Map();
    for (const n of activeNodes) {
      neighbors.set(n, new Set());
      nodeEdgeCount.set(n, 0);
    }
    let maxWeight = 1;
    for (const e of visibleEdges) {
      neighbors.get(e.from).add(e.to);
      neighbors.get(e.to).add(e.from);
      nodeEdgeCount.set(e.from, (nodeEdgeCount.get(e.from) || 0) + 1);
      nodeEdgeCount.set(e.to, (nodeEdgeCount.get(e.to) || 0) + 1);
      if ((e.count || 1) > maxWeight) maxWeight = e.count || 1;
    }

    const map = document.createElement("div");
    map.className = "network-map" + (activeNodes.length > 12 ? " dense" : "");
    map.setAttribute("role", "group");
    map.setAttribute(
      "aria-label",
      "Account network showing " + activeNodes.length + " accounts and " + visibleEdges.length + " links"
    );

    const canvas = document.createElement("canvas");
    canvas.setAttribute("aria-hidden", "true");
    map.append(canvas);

    const ctx = canvas.getContext("2d");
    const positions = new Map();
    const buttons = new Map();
    let current = null;
    let hovered = null;

    const nCount = activeNodes.length;
    const dense = nCount > 12;
    const labelLimit = dense ? 12 : 18;

    activeNodes.forEach((node, idx) => {
      const angle = (idx * 2 * Math.PI) / nCount - (nCount === 2 ? 0 : Math.PI / 2);
      const apexFactor = Math.abs(Math.sin(angle));
      const sign = idx % 2 === 0 ? 1 : -1;
      const staggerX = dense ? sign * 2.2 : 0;
      const staggerY = dense ? sign * (3.2 + apexFactor * 4.4) : 0;
      const rx = (nCount <= 6 ? 33 : 39) + staggerX;
      const ry = (nCount <= 6 ? 33 : 36.5) + staggerY;
      const x = 50 + rx * Math.cos(angle);
      const y = 50 + ry * Math.sin(angle);
      positions.set(node, { x, y });

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "map-node";
      btn.textContent = shortLabel(node, labelLimit);
      const deg = nodeEdgeCount.get(node) || 0;
      const totalSig = score.get(node) || 0;
      btn.title = node + " (" + deg + " links, " + totalSig + " shared matches)";
      btn.style.left = x.toFixed(2) + "%";
      btn.style.top = y.toFixed(2) + "%";
      btn.setAttribute("aria-pressed", "false");
      btn.dataset.account = node;

      btn.addEventListener("click", () => {
        const next = current === node ? null : node;
        select(next);
        if (onSelect) onSelect(current);
      });
      btn.addEventListener("mouseenter", () => {
        hovered = node;
        paint();
      });
      btn.addEventListener("mouseleave", () => {
        hovered = null;
        paint();
      });

      buttons.set(node, btn);
      map.append(btn);
    });

    container.append(map);

    function paint() {
      if (!ctx) return;
      const rect = map.getBoundingClientRect();
      const width = rect.width;
      const height = rect.height;
      if (!width || !height) return;

      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);
      ctx.lineCap = "round";

      const focus = current || hovered;
      const cx = width / 2;
      const cy = height / 2;
      const pairSeen = new Map();

      const ordered = focus
        ? visibleEdges.slice().sort((a, b) => {
            const aHit = a.from === focus || a.to === focus ? 1 : 0;
            const bHit = b.from === focus || b.to === focus ? 1 : 0;
            return aHit - bHit;
          })
        : visibleEdges;

      for (const edge of ordered) {
        const a = positions.get(edge.from);
        const b = positions.get(edge.to);
        if (!a || !b) continue;

        const key = edge.from < edge.to ? edge.from + "\0" + edge.to : edge.to + "\0" + edge.from;
        const dupIndex = pairSeen.get(key) || 0;
        pairSeen.set(key, dupIndex + 1);

        const x1 = (a.x * width) / 100;
        const y1 = (a.y * height) / 100;
        const x2 = (b.x * width) / 100;
        const y2 = (b.y * height) / 100;

        const isHit = focus && (edge.from === focus || edge.to === focus);
        const weightRatio = Math.log1p(edge.count || 1) / Math.log1p(maxWeight);
        const baseWidth = 1.15 + weightRatio * 2.4;

        ctx.strokeStyle = EDGE_COLORS[edge.kind] || "#566373";
        ctx.lineWidth = isHit ? Math.max(2.3, baseWidth + 0.9) : baseWidth;
        ctx.globalAlpha = focus ? (isHit ? 0.94 : 0.11) : nCount > 12 ? 0.56 : 0.72;

        const mx = (x1 + x2) / 2;
        const my = (y1 + y2) / 2;
        const pull = 0.18 + dupIndex * 0.12;
        const qx = mx + (cx - mx) * pull;
        const qy = my + (cy - my) * pull;

        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.quadraticCurveTo(qx, qy, x2, y2);
        ctx.stroke();
      }
    }

    function select(node) {
      current = node && buttons.has(node) ? node : null;
      const linked = current ? neighbors.get(current) : null;
      for (const [account, btn] of buttons) {
        const isCurrent = account === current;
        const isNeighbor = Boolean(linked && linked.has(account));
        btn.setAttribute("aria-pressed", String(isCurrent));
        btn.classList.toggle("is-neighbor", isNeighbor);
        btn.classList.toggle("is-dimmed", Boolean(current && !isCurrent && !isNeighbor));
      }
      paint();
    }

    const observer = new ResizeObserver(paint);
    observer.observe(map);
    graphs.set(container, observer);
    paint();

    return {
      select,
      shownNodes: activeNodes.length,
      shownEdges: visibleEdges.length,
      totalEdgeNodes: allNodes.length,
      hasNode: function (acct) {
        return buttons.has(acct);
      },
    };
  }

  /**
   * Mount a 24-hour UTC activity bar chart highlighting 9am-9pm Moscow / E. Europe daytime.
   */
  function mountSchedule(container, options) {
    if (!container) return;
    container.replaceChildren();

    const opts = options || {};
    const hourly = Array.isArray(opts.hourly) && opts.hourly.length === 24
      ? opts.hourly
      : new Array(24).fill(0);
    const schedule = opts.schedule || {};
    const maxVal = Math.max.apply(null, hourly.concat([1]));
    const total = hourly.reduce((acc, v) => acc + v, 0);
    const peakHour =
      typeof schedule.peak_utc_hour === "number"
        ? schedule.peak_utc_hour
        : hourly.indexOf(maxVal);

    const wrap = document.createElement("div");
    wrap.className = "schedule-chart";

    const head = document.createElement("div");
    head.className = "schedule-head";

    const badge = document.createElement("span");
    badge.className = "schedule-label";
    badge.textContent = schedule.label || "Posts by hour (UTC)";

    const readout = document.createElement("span");
    readout.className = "schedule-readout";
    readout.setAttribute("aria-live", "polite");
    const peakStr = String(peakHour).padStart(2, "0") + ":00 UTC";
    const defaultReadout =
      "Peak " + peakStr + " (" + (hourly[peakHour] || 0).toLocaleString() + " posts)";
    readout.textContent = defaultReadout;

    head.append(badge, readout);
    wrap.append(head);

    const plot = document.createElement("div");
    plot.className = "schedule-plot";
    plot.setAttribute("role", "img");
    plot.setAttribute(
      "aria-label",
      "Posting hours in UTC across " + total.toLocaleString() + " posts, peaking at " + peakStr
    );

    const band = document.createElement("div");
    band.className = "schedule-band";
    band.setAttribute("aria-hidden", "true");
    band.title = "9am-9pm Moscow / E. Europe (06:00-17:59 UTC)";
    plot.append(band);

    const bars = document.createElement("div");
    bars.className = "schedule-bars";

    hourly.forEach((count, hour) => {
      const col = document.createElement("button");
      col.type = "button";
      col.className = "schedule-col";
      const inMsk = hour >= 6 && hour < 18;
      if (inMsk) col.classList.add("is-utc3");
      if (hour === peakHour && count > 0) col.classList.add("is-peak");

      const hUtc = String(hour).padStart(2, "0") + ":00 UTC";
      const hMsk = String((hour + 3) % 24).padStart(2, "0") + ":00 Moscow";
      const pct = total > 0 ? ((count / total) * 100).toFixed(1) : "0.0";
      const detail = hUtc + " (" + hMsk + "): " + count.toLocaleString() + " posts (" + pct + "%)";
      col.title = detail;
      col.setAttribute("aria-label", detail);

      const bar = document.createElement("span");
      bar.className = "schedule-bar";
      const heightPct = count > 0 ? Math.max(4, (count / maxVal) * 100) : 2;
      bar.style.height = heightPct.toFixed(1) + "%";
      if (count === 0) bar.classList.add("is-zero");
      col.append(bar);

      col.addEventListener("mouseenter", () => {
        readout.textContent = detail;
      });
      col.addEventListener("focus", () => {
        readout.textContent = detail;
      });
      col.addEventListener("mouseleave", () => {
        readout.textContent = defaultReadout;
      });
      col.addEventListener("blur", () => {
        readout.textContent = defaultReadout;
      });

      bars.append(col);
    });

    plot.append(bars);
    wrap.append(plot);

    const axis = document.createElement("div");
    axis.className = "schedule-axis";
    ["00", "06", "12", "18", "23 UTC"].forEach((tick) => {
      const s = document.createElement("span");
      s.textContent = tick;
      axis.append(s);
    });
    wrap.append(axis);

    const foot = document.createElement("div");
    foot.className = "schedule-foot";

    const mskLegend = document.createElement("span");
    mskLegend.className = "schedule-legend-item";
    const swatch = document.createElement("i");
    swatch.className = "band-swatch";
    mskLegend.append(swatch, document.createTextNode("9am-9pm Moscow (06-17 UTC)"));

    const stats = document.createElement("span");
    stats.className = "schedule-metrics";
    const parts = [];
    if (typeof schedule.moscow_work_share === "number") {
      parts.push("Moscow day " + Math.round(schedule.moscow_work_share * 100) + "%");
    }
    if (typeof schedule.us_daytime_share === "number") {
      parts.push("US day " + Math.round(schedule.us_daytime_share * 100) + "%");
    }
    if (typeof schedule.quiet_6h_share === "number") {
      parts.push("Quietest 6h " + Math.round(schedule.quiet_6h_share * 100) + "%");
    }
    stats.textContent = parts.join(" · ");

    foot.append(mskLegend, stats);
    wrap.append(foot);

    container.append(wrap);
  }

  window.PropnetGraph = {
    mount: mount,
    mountSchedule: mountSchedule,
    EDGE_COLORS: EDGE_COLORS,
  };
})();
