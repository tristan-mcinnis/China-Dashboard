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
  if (el) {
    const now = new Date();
    const timeString = now.toLocaleTimeString("en-US", {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
    el.textContent = `Updated ${timeString}`;
  }
}

async function render() {
  try {
    const [indices, fx, baidu, weibo, wechat, weather, xinhua] = await Promise.all([
      loadJSON("data/indices.json"),
      loadJSON("data/fx.json"),
      loadJSON("data/baidu_top.json"),
      loadJSON("data/weibo_hot.json"),
      loadJSON("data/tencent_wechat_hot.json"),
      loadJSON("data/weather.json").catch(() => ({ items: [] })),
      loadJSON("data/xinhua_news.json").catch(() => ({ items: [] })),
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

    const olBaidu = document.getElementById("baidu");
    if (olBaidu) {
      olBaidu.innerHTML = "";
      baidu.items.slice(0, 10).forEach((item) => {
        const li = document.createElement("li");
        const cleanTitle = item.title.replace(/^\d+\.\s*/, '');
        const translation = item.extra?.translation || '';

        if (translation) {
          li.innerHTML = `
            <a href="${item.url}" target="_blank" rel="noopener" class="bilingual-text">
              <div class="chinese-text">${cleanTitle}</div>
              <div class="english-text">${translation}</div>
            </a>
            <span class="muted">${item.value || ""}</span>`;
          li.classList.add("has-translation");
        } else {
          li.innerHTML = `<a href="${item.url}" target="_blank" rel="noopener">${cleanTitle}</a> <span class="muted">${
            item.value || ""
          }</span>`;
        }
        olBaidu.appendChild(li);
      });
    }

    const olWeibo = document.getElementById("weibo");
    if (olWeibo) {
      olWeibo.innerHTML = "";
      weibo.items.slice(0, 10).forEach((item) => {
        const li = document.createElement("li");
        const cleanTitle = item.title.replace(/^\d+\.\s*/, '');
        const translation = item.extra?.translation || '';
        const link = toMobileWeiboUrl(item.url);

        if (translation) {
          li.innerHTML = `
            <a href="${link}" target="_blank" rel="noopener" class="bilingual-text">
              <div class="chinese-text">${cleanTitle}</div>
              <div class="english-text">${translation}</div>
            </a>
            <span class="muted">${item.value || ""}</span>`;
          li.classList.add("has-translation");
        } else {
          li.innerHTML = `<a href="${link}" target="_blank" rel="noopener">${cleanTitle}</a> <span class="muted">${
            item.value || ""
          }</span>`;
        }
        olWeibo.appendChild(li);
      });
    }

    const olWechat = document.getElementById("wechat");
    if (olWechat) {
      olWechat.innerHTML = "";
      wechat.items.slice(0, 10).forEach((item) => {
        const li = document.createElement("li");
        const cleanTitle = item.title.replace(/^\d+\.\s*/, '');
        const translation = item.extra?.translation || '';

        if (translation) {
          li.innerHTML = `
            <a href="${item.url}" target="_blank" rel="noopener" class="bilingual-text">
              <div class="chinese-text">${cleanTitle}</div>
              <div class="english-text">${translation}</div>
            </a>
            <span class="muted">${item.value || ""}</span>`;
          li.classList.add("has-translation");
        } else {
          li.innerHTML = `<a href="${item.url}" target="_blank" rel="noopener">${cleanTitle}</a> <span class="muted">${
            item.value || ""
          }</span>`;
        }
        olWechat.appendChild(li);
      });
    }

    const weatherStrip = document.getElementById("weather-strip");
    if (weatherStrip) {
      renderWeatherStrip(weatherStrip, weather);
    }

    const xinhuaGrid = document.getElementById("xinhua-news");
    if (xinhuaGrid) {
      xinhuaGrid.innerHTML = "";

      const categories = new Map();
      const items = Array.isArray(xinhua?.items) ? xinhua.items : [];

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
        xinhuaGrid.appendChild(card);
      } else {
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
          xinhuaGrid.appendChild(card);
        });
      }
    }

    setLastRefresh();
  } catch (error) {
    console.error(error);
  }
}

render();
setInterval(render, 60_000);
