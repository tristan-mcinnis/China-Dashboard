/* ============================================================
   CHINA SNAPSHOT v2 — prototype engine
   Reads the SAME live data as production (data/*.json).
   Vanilla, no build step.

   PERFORMANCE MODEL:
   - Boot fetches only the small LIVE json per source (~140 KB total).
   - Large history files (5+ MB) are NEVER fetched on boot. Each card's
     ‹ › arrows lazy-load that source's history on first use, and the
     browser caches it (no cache-bust on history).
   - Index sparklines + the editions strip load during idle time, after
     first paint, so they never block the initial render.
   - The 90 s auto-refresh only re-pulls the tiny live files.
   ============================================================ */
const DATA = "data/";
const bust = () => `?t=${Date.now()}`;
const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const el = (tag, cls, html) => { const n = document.createElement(tag); if (cls) n.className = cls; if (html != null) n.innerHTML = html; return n; };
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c]));
const idle = (fn) => (window.requestIdleCallback ? requestIdleCallback(fn, { timeout: 1500 }) : setTimeout(fn, 250));

const loadLive = async (name) => { const r = await fetch(`${DATA}${name}${bust()}`); if (!r.ok) throw new Error(name); return r.json(); };
/* history: no cache-bust → served from browser cache after first fetch */
const _histCache = {};
async function loadHistFile(histName) {
  if (_histCache[histName]) return _histCache[histName];
  try { const r = await fetch(`${DATA}history/${histName}`); const j = await r.json();
    const out = (j.entries || []).map(e => ({ as_of: e.as_of, items: e.items || [] })); _histCache[histName] = out; return out;
  } catch { return []; }
}
function fmtTs(iso) { const m = String(iso || "").match(/(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/); return m ? `${m[2]}-${m[3]} ${m[4]}:${m[5]}` : (iso ? String(iso).slice(0, 16) : "—"); }

/* ---------------- language ---------------- */
let LANG = localStorage.getItem("cs2-lang") || "en";
const I18N = {
  "nav.brief": ["Brief","简报"], "nav.trending": ["Trending","热搜"], "nav.news": ["Press","媒体"],
  "nav.markets": ["Markets","市场"], "nav.macro": ["Macro","宏观"], "nav.sources": ["Sources","源头"],
  "search.placeholder": ["Search","搜索"], "tm.live": ["● LIVE","● 实时"], "tm.return": ["Return to live ›","返回实时 ›"],
  "brief.kicker": ["Today's Brief","今日简报"], "brief.copy": ["Copy","复制"],
  "sec.trending": ["Trending & Search","热搜与讨论"], "sec.trending.sub": ["What China is searching and arguing about right now","此刻中国正在搜索与热议的话题"],
  "sec.news": ["State & Domestic Press","官方与国内媒体"], "sec.news.sub": ["Bilingual headlines from Xinhua and The Paper","新华社与澎湃新闻双语头条"],
  "sec.markets": ["Markets & FX","市场与汇率"], "sec.markets.sub": ["Indices, currencies and China-demand commodities","指数、汇率与中国需求大宗商品"],
  "sec.macro": ["Macro & Policy","宏观与政策"], "sec.macro.sub": ["Rates, prices and the real-economy pulse","利率、物价与实体经济脉搏"],
  "sec.sources": ["Primary Sources","一手源头"], "sec.sources.sub": ["Ministries, regulators and diplomacy — straight from the wire","部委、监管机构与外交 — 直达原文"],
  "about.body": ["Built by Tristan McInnis to read China the way it reads itself — in real time, on its own platforms. Most coverage reaches you second-hand and a day late; this pulls straight from the source.",
    "由 Tristan McInnis 打造，以中国自身的方式实时阅读中国 —— 直接来自其本土平台。多数报道都是二手且滞后一天的，这里直达源头。"],
  "about.contact": ["Email me","联系我"],
  "footer.fine": ["Information provided “as is” for general informational purposes only.","本仪表板信息仅按“原样”提供，供一般参考之用。"],
};
const t = (k) => (I18N[k] ? I18N[k][LANG === "zh" ? 1 : 0] : k);
const pick = (en, zh) => (LANG === "zh" ? (zh || en) : (en || zh)) || "";
function applyLang() {
  document.documentElement.setAttribute("data-lang", LANG);
  document.documentElement.lang = LANG === "zh" ? "zh-CN" : "en";
  $$("[data-i18n]").forEach(n => { n.textContent = t(n.getAttribute("data-i18n")); });
  $$(".lang-toggle button").forEach(b => b.classList.toggle("is-active", b.dataset.lang === LANG));
  localStorage.setItem("cs2-lang", LANG);
}
$$(".lang-toggle button").forEach(b => b.addEventListener("click", () => { LANG = b.dataset.lang; applyLang(); rerenderAll(); }));

/* ---------------- pillars ---------------- */
const PILLARS = {
  politics:    { en: "Politics",               zh: "政治",       color: "var(--p-politics)" },
  economy:     { en: "Economy & Markets",      zh: "经济与市场", color: "var(--p-economy)" },
  geopolitics: { en: "International Relations", zh: "国际关系",   color: "var(--p-geopolitics)" },
  tech:        { en: "Industry & Tech",        zh: "产业与科技", color: "var(--p-tech)" },
  regulatory:  { en: "Regulatory",             zh: "监管",       color: "var(--p-regulatory)" },
  society:     { en: "What's Trending",        zh: "社会热点",   color: "var(--p-society)" },
};
const pillarColor = (k) => (PILLARS[k]?.color || "var(--ink-3)");
const pillarName  = (k) => (PILLARS[k] ? pick(PILLARS[k].en, PILLARS[k].zh) : k);
const parseList = (v) => { try { return typeof v === "string" ? JSON.parse(v.replace(/'/g, '"')) : (v || []); } catch { return []; } };
const PF = { baidu_top:"Baidu", weibo_hot:"Weibo", tencent_wechat_hot:"WeChat", xinhua_news:"Xinhua",
  thepaper_news:"The Paper", gov_registry:"Gov", elite_press:"Elite Press", ladymax_news:"LadyMax" };
/* pull the heat number out of noisy strings like "综艺 1974400 热度" → "1,974,400" */
function formatHeat(v) { const m = String(v ?? "").match(/(\d[\d,]{2,})/); return m ? Number(m[1].replace(/,/g, "")).toLocaleString("en-US") : ""; }

/* ---------------- lazy per-card history controller ---------------- */
class HistoryNav {
  constructor(barEl, liveSnap, histName, renderFn) {
    this.entries = liveSnap ? [liveSnap] : [];
    this.histName = histName; this.render = renderFn; this.i = 0; this.loaded = false; this.loading = false;
    barEl.innerHTML = `<button class="hb-prev" aria-label="Older snapshot">‹</button><span class="hb-ts mono"></span><button class="hb-next" aria-label="Newer snapshot">›</button>`;
    this.prev = $(".hb-prev", barEl); this.next = $(".hb-next", barEl); this.ts = $(".hb-ts", barEl);
    this.prev.onclick = () => this.older(); this.next.onclick = () => this.newer();
    this.show();
  }
  async older() {
    if (!this.loaded) { await this.ensure(); }
    if (this.i < this.entries.length - 1) { this.i++; this.show(); }
  }
  newer() { if (this.i > 0) { this.i--; this.show(); } }
  async ensure() {
    if (this.loaded || this.loading || !this.histName) return;
    this.loading = true; this.ts.textContent = "…";
    const hist = await loadHistFile(this.histName);
    const map = new Map(this.entries.map(e => [e.as_of, e]));
    hist.forEach(e => { if (e.as_of && !map.has(e.as_of)) map.set(e.as_of, e); });
    this.entries = [...map.values()].sort((a, b) => String(b.as_of).localeCompare(String(a.as_of)));
    this.loaded = true; this.loading = false; this.show();
  }
  updateLive(snap) { if (snap && this.i === 0) { this.entries[0] = snap; this.loaded = false; this.show(); } }
  show() {
    const e = this.entries[this.i];
    this.prev.disabled = this.loaded && this.i >= this.entries.length - 1;
    this.next.disabled = this.i <= 0;
    this.ts.textContent = e ? fmtTs(e.as_of) : "—";
    this.ts.classList.toggle("past", this.i > 0);
    if (e) this.render(e);
  }
}

/* ---------------- sparklines ---------------- */
function sparkline(values, { w = 56, h = 16 } = {}) {
  const v = (values || []).filter(n => typeof n === "number" && !Number.isNaN(n));
  if (v.length < 2) return "";
  const min = Math.min(...v), max = Math.max(...v), span = (max - min) || 1, step = w / (v.length - 1);
  const pts = v.map((n, i) => `${(i * step).toFixed(1)},${(h - ((n - min) / span) * h).toFixed(1)}`).join(" ");
  const col = v[v.length - 1] >= v[0] ? "var(--up)" : "var(--down)";
  return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" fill="none" aria-hidden="true"><polyline points="${pts}" stroke="${col}" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
}
function seriesFrom(snaps, title) {
  const out = [];
  (snaps || []).slice().reverse().forEach(s => { const it = (s.items || []).find(i => (i.title || "") === title);
    if (it) { const n = parseFloat(String(it.value).replace(/[^0-9.\-]/g, "")); if (!Number.isNaN(n)) out.push(n); } });
  return out.slice(-24);
}

/* ============================================================
   EDITIONS (whole-brief time travel) + BRIEF
   ============================================================ */
let BRIEFS = [], briefIndex = 0;
const SLOT = { morning: ["AM","早"], midday: ["MID","午"], evening: ["PM","晚"] };
async function initBrief() {
  let live = null; try { live = await loadLive("daily_digest.json"); } catch {}
  BRIEFS = live ? [live] : []; briefIndex = 0;
  buildTimeline(); renderBrief();
}
async function loadEditions() {        // deferred to idle
  let hist = { entries: [] }; try { hist = await loadLive("digest_history.json"); } catch {}
  const live = BRIEFS[0];
  let entries = (hist.entries || []).slice();
  if (live && !entries.some(e => e.as_of === live.as_of)) entries.unshift(live);
  if (entries.length) { BRIEFS = entries; buildTimeline(); }
}
function buildTimeline() {
  const scroll = $("#tm-scroll"); scroll.innerHTML = "";
  const groups = {};
  BRIEFS.forEach(e => { const d = e.date || (e.as_of || "").slice(0, 10); (groups[d] = groups[d] || []).push(e); });
  Object.keys(groups).sort().forEach(d => {
    const g = el("div", "vf-daygrp"); g.appendChild(el("div", "vf-daylabel", esc(d.slice(5))));
    const slots = el("div", "vf-slots");
    groups[d].sort((a, b) => BRIEFS.indexOf(b) - BRIEFS.indexOf(a));
    groups[d].forEach(e => {
      const i = BRIEFS.indexOf(e); const s = (SLOT[e.digest_type] || ["·","·"])[LANG === "zh" ? 1 : 0];
      const btn = el("button", "vf-slot", esc(s)); btn.dataset.idx = i; btn.title = `${e.time_label || ""} · ${e.beijing_time || ""}`;
      btn.addEventListener("click", () => { briefIndex = i; renderBrief(); syncTimeline(); });
      slots.appendChild(btn);
    });
    g.appendChild(slots); scroll.appendChild(g);
  });
  syncTimeline(); scroll.scrollLeft = scroll.scrollWidth;
}
function syncTimeline() {
  $$(".vf-slot").forEach(b => b.classList.toggle("is-active", Number(b.dataset.idx) === briefIndex));
  $("#tm-now").classList.toggle("dim", briefIndex !== 0);
}
$("#tm-prev").addEventListener("click", () => { if (briefIndex < BRIEFS.length - 1) { briefIndex++; renderBrief(); syncTimeline(); } });
$("#tm-next").addEventListener("click", () => { if (briefIndex > 0) { briefIndex--; renderBrief(); syncTimeline(); } });
$("#tm-now").addEventListener("click", () => { briefIndex = 0; renderBrief(); syncTimeline(); });
$("#brief-return").addEventListener("click", () => { briefIndex = 0; renderBrief(); syncTimeline(); });

function parseMarket(str) {
  return String(str || "").split(/\s+·\s+/).map(tok => {
    const m = tok.trim().match(/^(.*?)\s+([\d.,]+)\s*([▲▼])?\s*([\d.%-]+)?$/);
    return m ? { name: m[1], value: m[2], arrow: m[3] || "", delta: m[4] || "" } : { name: tok.trim(), value: "", arrow: "", delta: "" };
  }).filter(x => x.name);
}
function renderBrief() {
  const d = BRIEFS[briefIndex]; if (!d) return;
  const live = briefIndex === 0;
  const rw = $("#brief-rewound"); rw.hidden = live;
  if (!live) $("#brief-rewound-text").textContent = LANG === "zh"
    ? `正在查看 ${d.date} ${(SLOT[d.digest_type]||["",""])[1]}简报存档` : `Viewing the ${d.date} ${d.time_label || ""} archive`;
  $("#brief-stamp").textContent = `${d.time_label || ""} · ${d.date || ""} ${d.beijing_time || ""} CST`;
  $("#brief-headline").textContent = pick(d.headline, d.headline_zh);

  // hero (per-day image if the digest provides one, else the curated default)
  const heroImg = $("#brief-hero-img"), src = d.hero_image || "assets/hero.jpg";
  if (heroImg.getAttribute("src") !== src) heroImg.src = src;

  const nar = $("#brief-narrative"); nar.innerHTML = "";
  const paras = pick(d.narrative, d.narrative_zh).trim().split(/\n\s*\n/).filter(Boolean);
  if (paras.length) {
    nar.appendChild(el("p", "", esc(paras[0])));
    if (paras.length > 1) {
      const rest = el("div", "brief-rest"); rest.hidden = true;
      paras.slice(1).forEach(p => rest.appendChild(el("p", "", esc(p)))); nar.appendChild(rest);
      const more = LANG === "zh" ? "展开全文 ▾" : "Show full brief ▾", less = LANG === "zh" ? "收起 ▴" : "Show less ▴";
      const tog = el("button", "brief-toggle", more);
      tog.addEventListener("click", () => { const o = rest.hidden; rest.hidden = !o; tog.textContent = o ? less : more; });
      nar.appendChild(tog);
    }
  }
  const th = $("#brief-themes"); th.innerHTML = "";
  const trends = d.theme_trends || {};
  (d.themes || []).forEach(name => {
    const chip = el("button", "chip"); chip.appendChild(el("span", "", esc(name)));
    const tr = trends[name]; if (tr) { const g = { new:"✦", rising:"↑", recurring:"↻" }[tr.status]; if (tr.status === "new") chip.classList.add("is-new"); if (g) chip.appendChild(el("span", "tr", g)); }
    chip.addEventListener("click", () => openTagView(name)); th.appendChild(chip);
  });
  // sidebar: market snapshot
  const mblk = $("#brief-market-blk"), mlist = $("#brief-market-list"); const mkts = parseMarket(d.market_snapshot); mlist.innerHTML = "";
  if (mkts.length) { mblk.hidden = false; mkts.forEach(m => { const li = el("li");
    li.appendChild(el("span", "mname", esc(m.name))); li.appendChild(el("span", "mval", esc(m.value)));
    if (m.arrow) li.appendChild(el("span", `mdelta ${m.arrow === "▲" ? "up" : "down"}`, `${m.arrow}${esc(m.delta)}`)); mlist.appendChild(li); }); }
  else mblk.hidden = true;
  // sidebar: entities
  const eblk = $("#brief-entities-blk"), ebox = $("#brief-entities"); ebox.innerHTML = ""; const ents = d.entities || [];
  if (ents.length) { eblk.hidden = false; ents.forEach(name => { const b = el("button", "entity", esc(name)); b.addEventListener("click", () => openTagView(name)); ebox.appendChild(b); }); }
  else eblk.hidden = true;

  const wrap = $("#brief-blocks"); wrap.innerHTML = "";
  const all = d.top_stories || [];
  const order = (d.pillars && d.pillars.length) ? d.pillars.map(p => p.key) : Object.keys(PILLARS);
  order.forEach(key => {
    const block = all.filter(s => s.pillar === key); if (!block.length) return;
    const sec = el("section", "brief-block"); const head = el("div", "block-head");
    const dot = el("span", "block-dot"); dot.style.background = pillarColor(key); head.appendChild(dot);
    head.appendChild(el("span", "block-title", esc(pillarName(key))));
    head.appendChild(el("span", "block-count", `${block.length}`)); head.appendChild(el("span", "block-rule")); sec.appendChild(head);
    const grid = el("div", "story-grid"); block.forEach(s => grid.appendChild(storyCard(s))); sec.appendChild(grid); wrap.appendChild(sec);
  });
}
function storyCard(s) {
  const card = el("article", "story"); const top = el("div", "story-top");
  // Source badges carry the "where" — the internal salience rank is omitted (meaningless to a reader).
  let pfs = parseList(s.platforms).map(p => PF[p] || p); if (!pfs.length) pfs = s.source ? [s.source] : (s.category ? [s.category] : []);
  const badges = el("div", "story-platforms"); pfs.slice(0, 4).forEach(p => badges.appendChild(el("span", "pf-badge", esc(p)))); top.appendChild(badges); card.appendChild(top);
  const zhT = s.primary_title, enT = s.english_title;
  const primary = LANG === "zh" ? (zhT || enT) : (enT || zhT);
  const secondary = LANG === "zh" ? (enT && enT !== primary ? enT : "") : (zhT && zhT !== primary ? zhT : "");
  const ti = el("p", "story-title"); ti.innerHTML = s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(primary)}</a>` : esc(primary); card.appendChild(ti);
  if (secondary) card.appendChild(el("p", "story-sub", esc(secondary)));
  const why = pick(s.why_it_matters, s.why_it_matters_zh); if (why) card.appendChild(el("p", "story-why", esc(why)));
  return card;
}
$("#brief-copy").addEventListener("click", async (e) => {
  try { const r = await fetch(`${DATA}digest.md${bust()}`); const txt = await r.text(); await navigator.clipboard.writeText(txt);
    const b = e.currentTarget, old = b.textContent; b.textContent = LANG === "zh" ? "已复制 ✓" : "Copied ✓"; setTimeout(() => b.textContent = old, 1500); } catch {}
});

/* ============================================================
   KPI TAPE
   ============================================================ */
function renderKpi(d) {
  const strip = $("#kpitape"); strip.innerHTML = "";
  const find = (p, title) => (p?.items || []).find(it => (it.title || "") === title) || null; const out = [];
  const idxr = (p, title, label) => { const it = find(p, title); if (it) out.push({ label, value: it.value, delta: it.extra?.chg_pct }); };
  idxr(d.ind, "SSE Composite", pick("Shanghai","上证")); idxr(d.ind, "ChiNext", "ChiNext"); idxr(d.fx, "USD/CNY", "USD/CNY");
  const push = (p, title, label) => { const it = find(p, title); if (it) out.push({ label, value: it.value }); };
  push(d.nbs, "CPI YoY", pick("CPI YoY","CPI")); push(d.trade, "Exports YoY", pick("Exports YoY","出口")); push(d.prop, "New Home Prices YoY", pick("Home Prices YoY","房价"));
  out.forEach(k => { const cell = el("div", "kpi"); cell.appendChild(el("span", "kpi-label", esc(k.label)));
    const dn = k.delta != null ? Number(k.delta) : parseFloat(String(k.value).replace(/[^0-9.\-]/g, ""));
    const cls = !Number.isNaN(dn) && dn !== 0 ? (dn > 0 ? "up" : "down") : "";
    cell.appendChild(el("span", `kpi-value ${k.delta != null ? "" : cls}`, esc(k.value ?? "—")));
    if (k.delta != null && k.delta !== "" && !Number.isNaN(Number(k.delta))) { const n = Number(k.delta);
      cell.appendChild(el("span", `kpi-delta ${n > 0 ? "up" : n < 0 ? "down" : ""}`, `${n > 0 ? "▲" : "▼"}${Math.abs(n).toFixed(2)}%`)); }
    strip.appendChild(cell); });
}

/* ============================================================
   TRENDING — bilingual + lazy per-card history
   ============================================================ */
const TREND_DEFS = [["baidu_top", ["Baidu Top","百度热搜"]], ["weibo_hot", ["Weibo Hot","微博热搜"]], ["tencent_wechat_hot", ["WeChat Hot","微信热点"]]];
let trendNavs = {};
async function initTrending() {
  const grid = $("#trending-grid"); grid.innerHTML = ""; trendNavs = {};
  await Promise.all(TREND_DEFS.map(async ([key, name]) => {
    let live = { as_of: "", items: [] }; try { live = await loadLive(`${key}.json`); } catch {}
    const card = el("div", "card"); const head = el("div", "card-head");
    head.appendChild(el("h3", "card-title", esc(pick(name[0], name[1])))); const bar = el("div", "histbar"); head.appendChild(bar); card.appendChild(head);
    const ul = el("ul", "dlist"); card.appendChild(ul); grid.appendChild(card);
    trendNavs[key] = new HistoryNav(bar, { as_of: live.as_of, items: live.items || [] }, `${key}.json`, (entry) => renderTrendList(ul, entry));
  }));
}
function renderTrendList(ul, entry) {
  ul.innerHTML = "";
  (entry.items || []).slice(0, 10).forEach((it, i) => {
    const zh = String(it.title || "").replace(/^\d+\.\s*/, ""), en = it.extra?.translation || "";
    const primary = LANG === "zh" ? zh : (en || zh), secondary = LANG === "zh" ? (en && en !== primary ? en : "") : (zh && zh !== primary ? zh : "");
    const li = el("li"); li.appendChild(el("span", "rk", String(i + 1)));
    const nm = el("div", "nm"); const tt = el("div", "nm-title"); tt.innerHTML = it.url ? `<a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(primary)}</a>` : esc(primary); nm.appendChild(tt);
    if (secondary) nm.appendChild(el("div", "nm-sub", esc(secondary))); li.appendChild(nm);
    const heat = formatHeat(it.value); if (heat) li.appendChild(el("span", "heat", esc(heat))); ul.appendChild(li);
  });
}

/* ============================================================
   PRESS + LadyMax
   ============================================================ */
const NEWS_DEFS = [["xinhua_news", ["Xinhua 新华社","新华社"]], ["thepaper_news", ["The Paper 澎湃","澎湃新闻"]]];
let newsNavs = {};
async function initNews() {
  const grid = $("#news-grid"); grid.innerHTML = ""; newsNavs = {};
  await Promise.all(NEWS_DEFS.map(async ([key, name]) => {
    let live = { as_of: "", items: [] }; try { live = await loadLive(`${key}.json`); } catch {}
    const card = el("div", "card news-card"); const head = el("div", "card-head");
    head.appendChild(el("h3", "card-title", esc(pick(name[0], name[1])))); const bar = el("div", "histbar"); head.appendChild(bar); card.appendChild(head);
    const body = el("div", "news-body"); card.appendChild(body); grid.appendChild(card);
    newsNavs[key] = new HistoryNav(bar, { as_of: live.as_of, items: live.items || [] }, `${key}.json`, (entry) => renderNewsList(body, entry));
  }));
  let lady = { items: [] }; try { lady = await loadLive("ladymax_news.json"); } catch {}
  window.__lady = lady; renderLadymax();
}
function renderNewsList(body, entry) {
  body.innerHTML = "";
  (entry.items || []).slice(0, 8).forEach(it => {
    const en = it.extra?.translation || "", zh = it.title || "";
    const primary = LANG === "zh" ? zh : (en || zh), secondary = LANG === "zh" ? (en && en !== primary ? en : "") : (zh && zh !== primary ? zh : "");
    const n = el("div", "nitem"); if (it.extra?.category) n.appendChild(el("div", "nitem-cat", esc(it.extra.category)));
    const ti = el("div", "nitem-title"); ti.innerHTML = it.url ? `<a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(primary)}</a>` : esc(primary); n.appendChild(ti);
    if (secondary) n.appendChild(el("div", "nitem-sub", esc(secondary)));
    if (it.extra?.source_name) n.appendChild(el("div", "nitem-meta", esc(it.extra.source_name))); body.appendChild(n);
  });
}
function renderLadymax() {
  const row = $("#ladymax-row"); row.innerHTML = "";
  (window.__lady?.items || []).filter(it => it.extra?.image).slice(0, 8).forEach(it => {
    const en = it.extra?.translation || "", zh = it.title || "";
    const primary = LANG === "zh" ? zh : (en || zh), secondary = LANG === "zh" ? (en && en !== primary ? en : "") : (zh && zh !== primary ? zh : "");
    const a = el("a", "film"); a.href = it.url || "#"; a.target = "_blank"; a.rel = "noopener";
    const img = el("img", "film-img"); img.src = it.extra.image; img.alt = ""; img.loading = "lazy"; img.addEventListener("error", () => a.remove()); a.appendChild(img);
    const b = el("div", "film-body"); if (it.extra?.category) b.appendChild(el("div", "film-cat", esc(it.extra.category)));
    b.appendChild(el("div", "film-title", esc(primary))); if (secondary) b.appendChild(el("div", "film-sub", esc(secondary))); a.appendChild(b); row.appendChild(a);
  });
}

/* ============================================================
   MARKETS + MACRO (sparklines deferred to idle)
   ============================================================ */
function deltaSpan(pct) { if (pct == null || pct === "") return ""; const n = Number(pct); if (Number.isNaN(n)) return "";
  return `<span class="delta ${n > 0 ? "up" : n < 0 ? "down" : ""}">${n > 0 ? "▲" : n < 0 ? "▼" : "·"}${Math.abs(n).toFixed(2)}%</span>`; }
function metricCard(title, items, { showDelta = true, snaps = null } = {}) {
  const card = el("div", "card"); const head = el("div", "card-head"); head.appendChild(el("h3", "card-title", esc(title))); card.appendChild(head);
  const ul = el("ul", "dlist");
  (items || []).forEach(it => { const li = el("li"); const nm = el("span", "nm");
    nm.innerHTML = it.url ? `<a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.title)}</a>` : esc(it.title); li.appendChild(nm);
    const val = el("span", "val"); const sp = snaps ? sparkline(seriesFrom(snaps, it.title)) : "";
    const unit = it.extra?.unit ? ` <span class="heat">${esc(it.extra.unit)}</span>` : "";
    val.innerHTML = `${sp}${esc(it.value ?? "—")}${unit}${showDelta ? deltaSpan(it.extra?.chg_pct) : ""}`; li.appendChild(val); ul.appendChild(li); });
  card.appendChild(ul); return card;
}
async function initMarkets() {
  const [ind, fx, com] = await Promise.all([loadLive("indices.json").catch(() => ({ items: [] })), loadLive("fx.json").catch(() => ({ items: [] })), loadLive("commodities.json").catch(() => ({ items: [] }))]);
  window.__mkt = { ...(window.__mkt || {}), ind, fx, com }; renderMarkets();
}
async function loadMarketSparklines() {     // deferred to idle
  const [indS, fxS] = await Promise.all([loadHistFile("indices.json"), loadHistFile("fx.json")]);
  window.__mkt = { ...(window.__mkt || {}), indS, fxS }; renderMarkets();
}
function renderMarkets() {
  const m = window.__mkt || {}; const g = $("#markets-grid"); g.innerHTML = "";
  g.appendChild(metricCard(pick("Indices","股指"), m.ind?.items, { snaps: m.indS }));
  g.appendChild(metricCard(pick("FX","汇率"), m.fx?.items, { snaps: m.fxS }));
  g.appendChild(metricCard(pick("Commodities","大宗商品"), m.com?.items));
}
async function initMacro() {
  const [pboc, nbs, trade, prop] = await Promise.all([loadLive("pboc_rates.json").catch(() => ({ items: [] })), loadLive("nbs_monthly.json").catch(() => ({ items: [] })), loadLive("trade_data.json").catch(() => ({ items: [] })), loadLive("property.json").catch(() => ({ items: [] }))]);
  window.__macro = { pboc, nbs, trade, prop }; renderKpi({ ind: window.__mkt?.ind, fx: window.__mkt?.fx, nbs, trade, prop }); renderMacro();
}
function renderMacro() {
  const m = window.__macro || {}; const g = $("#macro-grid"); g.innerHTML = "";
  g.appendChild(metricCard(pick("PBOC Rates","央行利率"), m.pboc?.items, { showDelta: false }));
  g.appendChild(metricCard(pick("Monthly · CPI/PPI/PMI","月度指标"), m.nbs?.items, { showDelta: false }));
  g.appendChild(metricCard(pick("Trade","贸易"), m.trade?.items, { showDelta: false }));
  g.appendChild(metricCard(pick("Property","房价"), m.prop?.items, { showDelta: false }));
}

/* ============================================================
   PRIMARY SOURCES — pillar filter + lazy history
   ============================================================ */
let GOV = [], govPillar = "all";
async function initSources() {
  let live = { as_of: "", items: [] }; try { live = await loadLive("gov_registry.json"); } catch {}
  GOV = live.items || []; renderPillarTabs(); renderSources();
  new HistoryNav($("#registry-hist"), { as_of: live.as_of, items: live.items || [] }, "gov_registry.json",
    (entry) => { GOV = entry.items || []; renderPillarTabs(); renderSources(); });
}
function renderPillarTabs() {
  const counts = { all: GOV.length }; GOV.forEach(it => { const p = it.extra?.pillar || "other"; counts[p] = (counts[p] || 0) + 1; });
  if (govPillar !== "all" && !counts[govPillar]) govPillar = "all";
  const tabs = $("#pillar-tabs"); tabs.innerHTML = "";
  const mk = (key, label, color) => { const b = el("button", "ptab" + (govPillar === key ? " is-active" : ""));
    if (color) { const dot = el("span", "dot"); dot.style.background = color; b.appendChild(dot); }
    b.appendChild(el("span", "", esc(label))); b.appendChild(el("span", "n", `${counts[key] || 0}`));
    b.addEventListener("click", () => { govPillar = key; renderPillarTabs(); renderSources(); }); return b; };
  tabs.appendChild(mk("all", pick("All","全部"), null));
  Object.keys(PILLARS).forEach(k => { if (counts[k]) tabs.appendChild(mk(k, pillarName(k), pillarColor(k))); });
}
function renderSources() {
  const list = $("#src-list"); list.innerHTML = "";
  const seen = new Set();
  GOV.filter(it => govPillar === "all" || it.extra?.pillar === govPillar)
     .filter(it => { const k = (it.extra?.translation || it.title || "").trim().toLowerCase(); if (!k || seen.has(k)) return false; seen.add(k); return true; })
     .slice(0, 40).forEach(it => {
    const ex = it.extra || {}; const card = el("article", "src"); const top = el("div", "src-top");
    const dot = el("span", "src-dot"); dot.style.background = pillarColor(ex.pillar); top.appendChild(dot);
    top.appendChild(el("span", "src-agency", esc(pick(ex.agency, ex.agency_zh) || ex.agency || "")));
    if (ex.pillar) top.appendChild(el("span", "src-pillar", esc(pillarName(ex.pillar)))); card.appendChild(top);
    const en = ex.translation || "", zh = it.title || "";
    const primary = LANG === "zh" ? zh : (en || zh), secondary = LANG === "zh" ? (en && en !== primary ? en : "") : (zh && zh !== primary ? zh : "");
    const ti = el("p", "src-title"); ti.innerHTML = it.url ? `<a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(primary)}</a>` : esc(primary); card.appendChild(ti);
    if (secondary) card.appendChild(el("p", "src-sub", esc(secondary))); list.appendChild(card);
  });
}

/* ============================================================
   TICKER
   ============================================================ */
function initTicker() {
  const items = []; const d = BRIEFS[0];
  if (d) (d.top_stories || []).slice(0, 14).forEach(s => items.push({ text: LANG === "zh" ? (s.primary_title || s.english_title) : (s.english_title || s.primary_title), url: s.url, src: (parseList(s.platforms).map(p => PF[p] || p)[0]) || "CN" }));
  const track = $("#ticker-content");
  const make = () => items.forEach(it => { const a = el("a"); a.href = it.url || "#"; a.target = "_blank"; a.rel = "noopener";
    a.innerHTML = `<span class="src">${esc(it.src)}</span><span>${esc(it.text)}</span>`; track.appendChild(a); });
  track.innerHTML = ""; make(); make();
}

/* ============================================================
   TAG RESULTS VIEW (surfaced from search / chips / entities)
   ============================================================ */
let TAGS = null;
async function ensureTags() { if (TAGS) return TAGS; try { TAGS = (await loadLive("tags_index.json")).tags || {}; } catch { TAGS = {}; } return TAGS; }
async function openTagView(term) {
  await ensureTags(); const tags = TAGS || {}; const q = String(term || "").trim().toLowerCase();
  let rec = Object.values(tags).find(tg => (tg.label || "").toLowerCase() === q) || Object.values(tags).find(tg => (tg.label || "").toLowerCase().includes(q));
  let title = term, stories = [];
  if (rec) { title = rec.label; stories = (rec.stories || []).slice(); }
  if (!stories.length) {
    const seen = new Set();
    Object.values(tags).forEach(tg => (tg.stories || []).forEach(s => { if (`${s.title} ${s.english_title}`.toLowerCase().includes(q)) { const k = s.url || s.title; if (!seen.has(k)) { seen.add(k); stories.push(s); } } }));
  }
  stories.sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")));
  renderTagView(title, stories);
}
function renderTagView(title, stories) {
  $("#tagview-title").textContent = title;
  $("#tagview-count").textContent = `${stories.length} ${LANG === "zh" ? "条" : (stories.length === 1 ? "story" : "stories")}`;
  const list = $("#tagview-list"); list.innerHTML = "";
  if (!stories.length) list.appendChild(el("div", "palette-empty", LANG === "zh" ? "未找到相关报道" : "No stories found"));
  stories.forEach(s => {
    const primary = LANG === "zh" ? (s.title || s.english_title) : (s.english_title || s.title);
    const secondary = LANG === "zh" ? (s.english_title && s.english_title !== primary ? s.english_title : "") : (s.title && s.title !== primary ? s.title : "");
    const row = el("article", "tvrow"); const meta = el("div", "tvrow-meta");
    if (s.date) meta.appendChild(el("span", "tvrow-date", esc(s.date)));
    const srcs = parseList(s.platforms).map(p => PF[p] || p); (srcs.length ? srcs : [s.category || ""]).filter(Boolean).slice(0, 3).forEach(x => meta.appendChild(el("span", "tvrow-src", esc(x))));
    row.appendChild(meta);
    const ti = el("p", "tvrow-title"); ti.innerHTML = s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(primary)}</a>` : esc(primary); row.appendChild(ti);
    if (secondary) row.appendChild(el("p", "tvrow-sub", esc(secondary))); list.appendChild(row);
  });
  const tv = $("#tagview"); tv.hidden = false; tv.scrollIntoView({ behavior: "smooth", block: "start" });
}
$("#tagview-close").addEventListener("click", () => { $("#tagview").hidden = true; });

/* ============================================================
   COMMAND PALETTE
   ============================================================ */
let PAL_SEL = 0, PAL_ROWS = [];
function openPalette(prefill = "") { $("#palette").hidden = false; const q = $("#palette-q"); q.value = prefill; q.focus(); q.select(); ensureTags().then(() => runPalette(prefill)); }
function closePalette() { $("#palette").hidden = true; }
function runPalette(query) {
  const q = query.trim().toLowerCase(); const res = $("#palette-results"); res.innerHTML = ""; PAL_ROWS = []; PAL_SEL = 0; const tags = TAGS || {};
  const tagHits = Object.values(tags).filter(tg => !q || (tg.label || "").toLowerCase().includes(q)).sort((a, b) => b.count - a.count).slice(0, 6);
  const storyHits = []; Object.values(tags).forEach(tg => (tg.stories || []).forEach(s => { if (!q || `${s.title} ${s.english_title}`.toLowerCase().includes(q)) storyHits.push(s); }));
  const seen = new Set(); const stories = storyHits.filter(s => { const k = s.url || s.title; if (seen.has(k)) return false; seen.add(k); return true; }).slice(0, 10);
  if (!tagHits.length && !stories.length) { res.appendChild(el("div", "palette-empty", LANG === "zh" ? "未找到结果" : "No results")); return; }
  if (tagHits.length) { res.appendChild(el("div", "pr-group", LANG === "zh" ? "主题标签 — 查看相关报道" : "Themes & tags — show stories"));
    tagHits.forEach(tg => addRow(res, esc(tg.label), `${tg.count} ${LANG === "zh" ? "条" : "stories"}`, "✦", () => { closePalette(); openTagView(tg.label); })); }
  if (stories.length) { res.appendChild(el("div", "pr-group", LANG === "zh" ? "存档报道 — 打开来源" : "Archived stories — open source"));
    stories.forEach(s => { const primary = LANG === "zh" ? (s.title || s.english_title) : (s.english_title || s.title);
      addRow(res, esc(primary), esc(`${s.date || ""} · ${s.category || ""}`), "↗", () => { if (s.url) window.open(s.url, "_blank", "noopener"); }); }); }
  highlightRow();
}
function addRow(container, title, sub, icon, onAct) {
  const row = el("div", "pr-item"); row.appendChild(el("div", "pr-icon", icon)); const main = el("div", "pr-main");
  main.appendChild(el("div", "pr-title", title)); if (sub) main.appendChild(el("div", "pr-sub", sub)); row.appendChild(main);
  row.addEventListener("click", onAct); row._act = onAct; container.appendChild(row); PAL_ROWS.push(row);
}
function highlightRow() { PAL_ROWS.forEach((r, i) => r.classList.toggle("is-sel", i === PAL_SEL)); PAL_ROWS[PAL_SEL]?.scrollIntoView({ block: "nearest" }); }
$("#search-trigger").addEventListener("click", () => openPalette(""));
$("#palette").addEventListener("click", (e) => { if (e.target.id === "palette") closePalette(); });
$("#palette-q").addEventListener("input", (e) => runPalette(e.target.value));
$("#palette-q").addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown") { e.preventDefault(); PAL_SEL = Math.min(PAL_SEL + 1, PAL_ROWS.length - 1); highlightRow(); }
  else if (e.key === "ArrowUp") { e.preventDefault(); PAL_SEL = Math.max(PAL_SEL - 1, 0); highlightRow(); }
  else if (e.key === "Enter") PAL_ROWS[PAL_SEL]?._act?.();
  else if (e.key === "Escape") closePalette();
});
document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openPalette(""); }
  else if (e.key === "Escape" && !$("#palette").hidden) closePalette();
  else if (!$("#palette").hidden) return;
  else if (e.key === "ArrowLeft" && document.activeElement === document.body) $("#tm-prev").click();
  else if (e.key === "ArrowRight" && document.activeElement === document.body) $("#tm-next").click();
});

/* ============================================================
   chrome
   ============================================================ */
function initChrome() {
  const links = $$(".navrail a"); const map = new Map(links.map(a => [a.getAttribute("href").slice(1), a]));
  const io = new IntersectionObserver((entries) => { entries.forEach(en => { if (en.isIntersecting) { links.forEach(l => l.classList.remove("is-active")); map.get(en.target.id)?.classList.add("is-active"); } }); }, { rootMargin: "-45% 0px -50% 0px", threshold: 0 });
  ["brief","trending","news","markets","macro","sources"].forEach(id => { const n = document.getElementById(id); if (n) io.observe(n); });
  const top = $("#to-top"); window.addEventListener("scroll", () => { top.hidden = window.scrollY < 600; }, { passive: true });
  top.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
}
function setLive(ok) { $("#live-dot").classList.toggle("stale", !ok);
  $("#live-text").textContent = ok ? new Date().toLocaleTimeString(LANG === "zh" ? "zh-CN" : "en-US", { hour: "2-digit", minute: "2-digit" }) : (LANG === "zh" ? "离线" : "stale"); }
function rerenderAll() {
  buildTimeline(); renderBrief();
  Object.values(trendNavs).forEach(nav => nav.show());
  Object.values(newsNavs).forEach(nav => nav.show());
  renderLadymax(); renderMarkets();
  renderKpi({ ind: window.__mkt?.ind, fx: window.__mkt?.fx, nbs: window.__macro?.nbs, trade: window.__macro?.trade, prop: window.__macro?.prop });
  renderMacro(); renderPillarTabs(); renderSources(); initTicker();
}

/* light live refresh — never touches history */
async function refreshLive() {
  try {
    if (briefIndex === 0) { try { const dg = await loadLive("daily_digest.json"); if (dg) { BRIEFS[0] = dg; renderBrief(); initTicker(); } } catch {} }
    await initMarkets(); await initMacro(); setLive(true);
  } catch { setLive(false); }
}

/* ============================================================
   BOOT
   ============================================================ */
async function boot() {
  applyLang(); initChrome();
  await Promise.all([initBrief(), initTrending(), initNews(), initMarkets(), initSources()]);
  await initMacro(); initTicker(); setLive(true);
  idle(loadMarketSparklines);   // sparklines after first paint
  idle(loadEditions);           // editions strip after first paint
  setInterval(refreshLive, 90000);
}
boot();
