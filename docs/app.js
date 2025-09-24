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
    const [indices, fx, baidu, weibo, wechat, weather] = await Promise.all([
      loadJSON("data/indices.json"),
      loadJSON("data/fx.json"),
      loadJSON("data/baidu_top.json"),
      loadJSON("data/weibo_hot.json"),
      loadJSON("data/tencent_wechat_hot.json"),
      loadJSON("data/weather.json").catch(() => ({ items: [] })),
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

    setLastRefresh();
  } catch (error) {
    console.error(error);
  }
}

render();
setInterval(render, 60_000);
