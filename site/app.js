async function loadJSON(path) {
  const bust = `?t=${Date.now()}`;
  const res = await fetch(`../${path}${bust}`);
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

function setLastRefresh() {
  const el = document.getElementById("last-refresh");
  if (el) {
    el.textContent = `Last refresh: ${new Date().toLocaleString("zh-CN", { hour12: false })}`;
  }
}

async function render() {
  try {
    const [indices, fx, baidu, weibo] = await Promise.all([
      loadJSON("data/indices.json"),
      loadJSON("data/fx.json"),
      loadJSON("data/baidu_top.json"),
      loadJSON("data/weibo_hot.json"),
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
        li.innerHTML = `<a href="${item.url}" target="_blank" rel="noopener">${item.title}</a> <span class="muted">${
          item.value || ""
        }</span>`;
        olBaidu.appendChild(li);
      });
    }

    const olWeibo = document.getElementById("weibo");
    if (olWeibo) {
      olWeibo.innerHTML = "";
      weibo.items.slice(0, 10).forEach((item) => {
        const li = document.createElement("li");
        li.innerHTML = `<a href="${item.url}" target="_blank" rel="noopener">${item.title}</a> <span class="muted">${
          item.value || ""
        }</span>`;
        olWeibo.appendChild(li);
      });
    }

    setLastRefresh();
  } catch (error) {
    console.error(error);
  }
}

render();
setInterval(render, 60_000);
