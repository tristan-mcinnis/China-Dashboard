async function loadJSON(path) {
  const bust = `?t=${Date.now()}`;
  const res = await fetch(`${path}${bust}`);
  if (!res.ok) throw new Error(`fetch ${path} ${res.status}`);
  return res.json();
}

function fmtPct(value) {
  if (value === null || value === undefined) return "";
  const number = Number(value);
  if (Number.isNaN(number)) return "";
  const sign = number > 0 ? "▲" : number < 0 ? "▼" : "•";
  return ` ${sign} ${number.toFixed(2)}%`;
}

const HEADLINE_LIMIT = 5;

const XINHUA_CATEGORY_LABELS = new Map([
  ["要闻", { zh: "要闻", en: "Top News" }],
  ["国内", { zh: "国内", en: "Domestic" }],
  ["国际", { zh: "国际", en: "International" }],
  ["财经", { zh: "财经", en: "Finance" }],
  ["科技", { zh: "科技", en: "Technology" }],
]);

function getCategoryLabels(category) {
  const key = (category || "").trim();
  if (!key) {
    return { zh: "综合", en: "News" };
  }

  const mapping = XINHUA_CATEGORY_LABELS.get(key);
  if (mapping) {
    return mapping;
  }

  return { zh: key, en: "News" };
}

function formatHeadlineSubtitle(count) {
  if (count <= 0) {
    return "No headlines available";
  }
  if (count === 1) {
    return "Top headline";
  }
  return `Top ${count} headlines`;
}

function toMobileWeiboUrl(url) {
  if (!url || typeof url !== "string") return url;
  if (url.startsWith("https://m.weibo.cn/")) return url;

  try {
    const parsed = new URL(url);
    const host = parsed.hostname.toLowerCase();
    const isWeiboSearch =
      (host === "s.weibo.com" || host === "weibo.com") && parsed.pathname.startsWith("/weibo");

    if (!isWeiboSearch) {
      return url;
    }

    const query = parsed.searchParams.get("q");
    if (!query) {
      return url;
    }

    const encoded = encodeURIComponent(`100103type=1&q=${query}`);
    return `https://m.weibo.cn/search?containerid=${encoded}&v_p=42`;
  } catch (error) {
    return url;
  }
}

function formatNewsDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("zh-CN", {
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderWeatherStrip(container, payload) {
  const items = Array.isArray(payload?.items) ? payload.items : [];
  container.innerHTML = "";

  if (items.length === 0) {
    container.textContent = "Weather unavailable";
    return;
  }

  items.forEach((item, index) => {
    const wrapper = document.createElement("span");
    wrapper.className = "weather-item";

    const code = (item.code || item.name || "").toString().toUpperCase();
    const temperature =
      typeof item.temperature === "number" && Number.isFinite(item.temperature)
        ? `${Math.round(item.temperature)}°C`
        : "—";
    const label = document.createElement("span");
    label.className = "weather-label";
    label.textContent = `${code}: ${temperature}`;

    const icon = document.createElement("span");
    icon.className = "weather-icon";
    icon.textContent = item.icon || "•";
    if (item.condition) {
      icon.title = item.condition;
      wrapper.setAttribute("aria-label", `${code}: ${temperature} ${item.condition}`);
    } else {
      icon.setAttribute("aria-hidden", "true");
    }

    wrapper.appendChild(label);
    wrapper.appendChild(document.createTextNode(" "));
    wrapper.appendChild(icon);

    container.appendChild(wrapper);

    if (index < items.length - 1) {
      const divider = document.createElement("span");
      divider.className = "weather-divider";
      divider.textContent = "/";
      container.appendChild(divider);
    }
  });
}

function setLastRefresh() {
  const el = document.getElementById("last-refresh");
  if (!el) {
    return;
  }

  const now = new Date();
  const timeString = now.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  el.textContent = `Updated ${timeString}`;
}

function formatSnapshotTimestamp(value) {
  if (!value) {
    return "No snapshots";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString("zh-CN", {
    hour12: false,
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

class HistoryController {
  constructor({ container, prevButton, nextButton, timestampElement, render }) {
    this.container = container || null;
    this.prevButton = prevButton || null;
    this.nextButton = nextButton || null;
    this.timestampElement = timestampElement || null;
    this.renderEntry = typeof render === "function" ? render : () => {};
    this.entries = [];
    this.index = 0;

    if (this.prevButton) {
      this.prevButton.addEventListener("click", () => this.goOlder());
    }

    if (this.nextButton) {
      this.nextButton.addEventListener("click", () => this.goNewer());
    }

    this.update();
  }

  setEntries(entries) {
    const safeEntries = Array.isArray(entries) ? entries : [];
    const currentAsOf = this.entries?.[this.index]?.as_of || null;

    this.entries = safeEntries;

    let newIndex = 0;
    if (currentAsOf) {
      const foundIndex = this.entries.findIndex((entry) => entry?.as_of === currentAsOf);
      if (foundIndex >= 0) {
        newIndex = foundIndex;
      }
    }

    if (newIndex >= this.entries.length) {
      newIndex = this.entries.length > 0 ? this.entries.length - 1 : 0;
    }

    this.index = newIndex;
    this.update();
  }

  goOlder() {
    if (this.index < this.entries.length - 1) {
      this.index += 1;
      this.update();
    }
  }

  goNewer() {
    if (this.index > 0) {
      this.index -= 1;
      this.update();
    }
  }

  update() {
    const entry = this.entries[this.index] || null;
    this.renderEntry(entry);
    this.updateTimestamp(entry);
    this.updateButtons();
  }

  updateTimestamp(entry) {
    if (!this.timestampElement) {
      return;
    }

    if (!entry) {
      if (this.entries.length === 0) {
        this.timestampElement.textContent = "No snapshots";
        this.timestampElement.removeAttribute("title");
      } else {
        this.timestampElement.textContent = "—";
        this.timestampElement.removeAttribute("title");
      }
      return;
    }

    const formatted = formatSnapshotTimestamp(entry.as_of);
    this.timestampElement.textContent = formatted;
    if (entry.as_of) {
      this.timestampElement.setAttribute("title", entry.as_of);
    } else {
      this.timestampElement.removeAttribute("title");
    }
  }

  updateButtons() {
    const atNewest = this.index === 0;
    const atOldest = this.index >= this.entries.length - 1;

    this.setButtonState(this.nextButton, atNewest);
    this.setButtonState(this.prevButton, atOldest);
  }

  setButtonState(button, disabled) {
    if (!button) {
      return;
    }

    button.disabled = disabled;
    button.classList.toggle("is-disabled", disabled);

    if (disabled) {
      button.setAttribute("aria-disabled", "true");
    } else {
      button.removeAttribute("aria-disabled");
    }
  }
}

function renderTrendList(entry, listElement, { transformUrl } = {}) {
  if (!listElement) {
    return;
  }

  listElement.innerHTML = "";

  const items = Array.isArray(entry?.items) ? entry.items.slice(0, 10) : [];

  if (items.length === 0) {
    const li = document.createElement("li");
    li.className = "muted";
    li.textContent = "No data available.";
    listElement.appendChild(li);
    return;
  }

  const transform = typeof transformUrl === "function" ? transformUrl : (value) => value;

  items.forEach((item) => {
    if (!item || typeof item !== "object") {
      return;
    }

    const li = document.createElement("li");
    const rawTitle = typeof item.title === "string" ? item.title : String(item.title ?? "");
    const cleanTitle = rawTitle.replace(/^\d+\.\s*/, "");
    const translation = item?.extra?.translation || "";
    const value = item?.value || "";
    const transformedUrl = transform(item?.url || "");
    const href = (typeof transformedUrl === "string" && transformedUrl.trim()) ? transformedUrl : "#";

    const link = document.createElement("a");
    link.href = href;

    if (href !== "#") {
      link.target = "_blank";
      link.rel = "noopener";
    } else {
      link.setAttribute("aria-disabled", "true");
    }

    if (translation) {
      link.className = "bilingual-text";

      const zh = document.createElement("div");
      zh.className = "chinese-text";
      zh.textContent = cleanTitle;

      const en = document.createElement("div");
      en.className = "english-text";
      en.textContent = translation;

      link.appendChild(zh);
      link.appendChild(en);
      li.classList.add("has-translation");
    } else {
      link.textContent = cleanTitle;
    }

    li.appendChild(link);

    const meta = document.createElement("span");
    meta.className = "muted";
    meta.textContent = value;
    li.appendChild(meta);

    listElement.appendChild(li);
  });
}

function renderXinhuaSnapshot(entry, container) {
  if (!container) {
    return;
  }

  container.innerHTML = "";

  const categories = new Map();
  const items = Array.isArray(entry?.items) ? entry.items : [];

  items.forEach((item) => {
    const category = item?.extra?.category || "综合";
    if (!categories.has(category)) {
      categories.set(category, []);
    }
    categories.get(category).push(item);
  });

  if (categories.size === 0) {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="card-header">
        <h3 class="card-title">Xinhua RSS</h3>
        <div class="card-subtitle">Feed unavailable</div>
      </div>
      <div class="card-content">
        <p class="muted">No recent items fetched.</p>
      </div>
    `;
    container.appendChild(card);
    return;
  }

  categories.forEach((categoryItems, category) => {
    categoryItems.sort((a, b) => {
      const aTime = new Date(a?.extra?.published ?? 0).getTime();
      const bTime = new Date(b?.extra?.published ?? 0).getTime();
      return bTime - aTime;
    });

    const labels = getCategoryLabels(category);
    const limitedItems = categoryItems.slice(0, HEADLINE_LIMIT);

    const card = document.createElement("div");
    card.className = "card";

    const header = document.createElement("div");
    header.className = "card-header";

    const title = document.createElement("h3");
    title.className = "card-title card-title-bilingual";

    const titleZh = document.createElement("span");
    titleZh.className = "card-title-zh";
    titleZh.textContent = labels.zh;

    const titleEn = document.createElement("span");
    titleEn.className = "card-title-en";
    titleEn.textContent = labels.en;

    title.appendChild(titleZh);
    title.appendChild(titleEn);

    const subtitle = document.createElement("div");
    subtitle.className = "card-subtitle";
    subtitle.textContent = formatHeadlineSubtitle(limitedItems.length);

    header.appendChild(title);
    header.appendChild(subtitle);
    card.appendChild(header);

    const content = document.createElement("div");
    content.className = "card-content";

    if (limitedItems.length === 0) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "No stories available.";
      content.appendChild(empty);
    } else {
      const ul = document.createElement("ul");
      ul.className = "data-list";

      limitedItems.forEach((item) => {
        const li = document.createElement("li");
        li.classList.add("news-item");

        const link = document.createElement("a");
        const href = (item?.url || "").trim();
        if (href) {
          link.href = href;
          link.target = "_blank";
          link.rel = "noopener";
        } else {
          link.href = "#";
          link.setAttribute("aria-disabled", "true");
        }

        const rawTitle = (item?.title || "").trim() || "(无标题)";
        const translation = item?.extra?.translation || "";

        if (translation) {
          link.className = "bilingual-text";

          const zh = document.createElement("div");
          zh.className = "chinese-text";
          zh.textContent = rawTitle;

          const en = document.createElement("div");
          en.className = "english-text";
          en.textContent = translation;

          link.appendChild(zh);
          link.appendChild(en);
        } else {
          link.textContent = rawTitle;
        }

        li.appendChild(link);

        const published = formatNewsDate(item?.extra?.published);
        if (published) {
          const meta = document.createElement("div");
          meta.className = "news-meta";
          meta.textContent = `发布时间 ${published}`;
          if (item?.extra?.source_feed) {
            meta.setAttribute("title", item.extra.source_feed);
          }
          li.appendChild(meta);
        }

        const summary = (item?.extra?.summary || "").trim();
        if (summary) {
          const summaryEl = document.createElement("div");
          summaryEl.className = "news-summary";
          summaryEl.textContent = summary;
          li.appendChild(summaryEl);
        }

        ul.appendChild(li);
      });

      content.appendChild(ul);
    }

    card.appendChild(content);
    container.appendChild(card);
  });
}

function entryTimestamp(entry) {
  if (!entry || typeof entry !== "object") {
    return 0;
  }

  const value = entry.as_of;
  if (!value) {
    return 0;
  }

  const ms = new Date(value).getTime();
  if (Number.isNaN(ms)) {
    return 0;
  }

  return ms;
}

function normaliseEntry(entry, fallbackSource) {
  if (!entry || typeof entry !== "object") {
    return null;
  }

  const asOf = typeof entry.as_of === "string" ? entry.as_of : "";

  return {
    as_of: asOf,
    source: entry.source || fallbackSource || "",
    items: Array.isArray(entry.items) ? entry.items : [],
  };
}

async function loadHistoryEntries(latestPath, historyPath) {
  try {
    const historyPromise = loadJSON(historyPath).catch(() => null);
    const latestPromise = loadJSON(latestPath).catch(() => null);
    const [historyPayload, latestPayload] = await Promise.all([historyPromise, latestPromise]);

    const entriesByKey = new Map();
    const fallbackSource = latestPayload?.source || historyPayload?.source || "";

    if (historyPayload && Array.isArray(historyPayload.entries)) {
      historyPayload.entries.forEach((entry) => {
        const normalised = normaliseEntry(entry, fallbackSource);
        if (!normalised) {
          return;
        }

        const key = normalised.as_of || `history-${entriesByKey.size}`;
        if (!entriesByKey.has(key)) {
          entriesByKey.set(key, normalised);
        }
      });
    }

    if (latestPayload) {
      const normalisedLatest = normaliseEntry(latestPayload, fallbackSource);
      if (normalisedLatest) {
        const key = normalisedLatest.as_of || `latest-${entriesByKey.size}`;
        if (!entriesByKey.has(key)) {
          entriesByKey.set(key, normalisedLatest);
        }
      }
    }

    const entries = Array.from(entriesByKey.values());
    entries.sort((a, b) => entryTimestamp(b) - entryTimestamp(a));
    return entries;
  } catch (error) {
    console.error(error);
    return [];
  }
}

function createHistoryControllers() {
  const controllers = {};

  const baiduList = document.getElementById("baidu");
  controllers.baidu = new HistoryController({
    container: baiduList,
    prevButton: document.getElementById("baidu-prev"),
    nextButton: document.getElementById("baidu-next"),
    timestampElement: document.getElementById("baidu-timestamp"),
    render: (entry) => renderTrendList(entry, baiduList, {}),
  });

  const weiboList = document.getElementById("weibo");
  controllers.weibo = new HistoryController({
    container: weiboList,
    prevButton: document.getElementById("weibo-prev"),
    nextButton: document.getElementById("weibo-next"),
    timestampElement: document.getElementById("weibo-timestamp"),
    render: (entry) => renderTrendList(entry, weiboList, { transformUrl: toMobileWeiboUrl }),
  });

  const wechatList = document.getElementById("wechat");
  controllers.wechat = new HistoryController({
    container: wechatList,
    prevButton: document.getElementById("wechat-prev"),
    nextButton: document.getElementById("wechat-next"),
    timestampElement: document.getElementById("wechat-timestamp"),
    render: (entry) => renderTrendList(entry, wechatList, {}),
  });

  const xinhuaGrid = document.getElementById("xinhua-news");
  controllers.xinhua = new HistoryController({
    container: xinhuaGrid,
    prevButton: document.getElementById("xinhua-prev"),
    nextButton: document.getElementById("xinhua-next"),
    timestampElement: document.getElementById("xinhua-timestamp"),
    render: (entry) => renderXinhuaSnapshot(entry, xinhuaGrid),
  });

  return controllers;
}

const historyControllers = createHistoryControllers();

async function render() {
  try {
    const [indices, fx, weather, baiduHistory, weiboHistory, wechatHistory, xinhuaHistory] =
      await Promise.all([
        loadJSON("data/indices.json"),
        loadJSON("data/fx.json"),
        loadJSON("data/weather.json").catch(() => ({ items: [] })),
        loadHistoryEntries("data/baidu_top.json", "data/history/baidu_top.json"),
        loadHistoryEntries("data/weibo_hot.json", "data/history/weibo_hot.json"),
        loadHistoryEntries(
          "data/tencent_wechat_hot.json",
          "data/history/tencent_wechat_hot.json",
        ),
        loadHistoryEntries("data/xinhua_news.json", "data/history/xinhua_news.json"),
      ]);

    const ulIdx = document.getElementById("indices");
    if (ulIdx) {
      ulIdx.innerHTML = "";
      indices.items.forEach((item) => {
        const li = document.createElement("li");
        li.innerHTML = `<a href="${item.url}" target="_blank" rel="noopener">${item.title}</a> — <strong>${
          item.value ?? "—"
        }</strong><span class="muted">${fmtPct(item.extra?.chg_pct)}</span>`;
        ulIdx.appendChild(li);
      });
    }

    const ulFx = document.getElementById("fx");
    if (ulFx) {
      ulFx.innerHTML = "";
      fx.items.forEach((item) => {
        const li = document.createElement("li");
        li.innerHTML = `<a href="${item.url}" target="_blank" rel="noopener">${item.title}</a> — <strong>${
          item.value ?? "—"
        }</strong><span class="muted">${fmtPct(item.extra?.chg_pct)}</span>`;
        ulFx.appendChild(li);
      });
    }

    const weatherStrip = document.getElementById("weather-strip");
    if (weatherStrip) {
      renderWeatherStrip(weatherStrip, weather);
    }

    if (historyControllers.baidu) {
      historyControllers.baidu.setEntries(baiduHistory);
    }

    if (historyControllers.weibo) {
      historyControllers.weibo.setEntries(weiboHistory);
    }

    if (historyControllers.wechat) {
      historyControllers.wechat.setEntries(wechatHistory);
    }

    if (historyControllers.xinhua) {
      historyControllers.xinhua.setEntries(xinhuaHistory);
    }

    setLastRefresh();
  } catch (error) {
    console.error(error);
  }
}

// Theme switching functionality
function initTheme() {
  const themeToggle = document.getElementById('theme-toggle');
  const logoImage = document.getElementById('logo-image');
  const themeIcon = themeToggle.querySelector('.theme-icon');

  // Check for saved theme preference or default to 'dark'
  const currentTheme = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', currentTheme);

  // Update logo and icon based on current theme
  updateThemeElements(currentTheme, logoImage, themeIcon);

  // Theme toggle click handler
  themeToggle.addEventListener('click', () => {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeElements(newTheme, logoImage, themeIcon);
  });
}

function updateThemeElements(theme, logoImage, themeIcon) {
  if (theme === 'light') {
    logoImage.src = 'logo/white_logo.png';
    themeIcon.textContent = '◐';
  } else {
    logoImage.src = 'logo/black_logo.jpeg';
    themeIcon.textContent = '◑';
  }
}

// Initialize theme when DOM is loaded
document.addEventListener('DOMContentLoaded', initTheme);

render();
setInterval(render, 60_000);
