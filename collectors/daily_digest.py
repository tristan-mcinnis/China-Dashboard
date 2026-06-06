"""Daily digest generator.

Synthesizes all collector outputs in ``docs/data/`` into a single cross-source
brief that answers "what actually matters in China right now". Trending topics
are scored by cross-platform salience (a story that is hot on Baidu *and* Weibo
*and* WeChat outranks one that is hot on a single platform), news and regulatory
items are folded in, and a deterministic market snapshot is always attached.

DeepSeek (``deepseek-v4-flash``) is used to write a real narrative brief and concise
per-story "why it matters" lines. If ``DEEPSEEK_API_KEY`` is missing or the API
call fails, the generator falls back to a fully deterministic digest so the
pipeline never produces a broken or empty artifact.

Outputs (all under ``docs/data/``):
  - ``daily_digest.json``  rich, machine-readable feed (dashboard + other repos)
  - ``digest.md``          clean Markdown brief (paste into other digests / LLMs)
  - ``digest_archive/<date>/<slot>.json``  point-in-time snapshot
"""

from __future__ import annotations

import difflib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.common import now_iso_tz8, write_json
from collectors import tags_index as tags

try:  # OpenAI client is optional at import time; only needed for LLM synthesis
    from openai import OpenAI
except Exception:  # pragma: no cover - defensive
    OpenAI = None

DATA_DIR = "docs/data"
DIGEST_JSON = f"{DATA_DIR}/daily_digest.json"
DIGEST_MD = f"{DATA_DIR}/digest.md"
ARCHIVE_DIR = f"{DATA_DIR}/digest_archive"
# Consolidated, newest-first index of past briefs so the static dashboard can
# flip through earlier snapshots (the per-date/slot files can't be listed over
# GitHub Pages). Slimmed + bounded to keep the single fetch light.
HISTORY_JSON = f"{DATA_DIR}/digest_history.json"
HISTORY_LIMIT = 60

# Theme trend window: how a theme is moving relative to the past week of briefs.
THEME_TREND_WINDOW_DAYS = 7
THEME_RECURRING_DAYS = 3  # appeared on >= this many distinct prior days => recurring

# Trending platforms contribute to cross-platform salience scoring.
SOCIAL_SOURCES = ["baidu_top", "weibo_hot", "tencent_wechat_hot"]
PLATFORM_LABELS = {
    "baidu_top": "Baidu",
    "weibo_hot": "Weibo",
    "tencent_wechat_hot": "WeChat",
    "xinhua_news": "Xinhua",
    "thepaper_news": "The Paper",
    "gov_registry": "Gov Registry",
}
MAX_STORIES = 16

# Sinocism-style thematic blocks. Order here is the render order in the brief.
PILLARS = [
    ("politics", "High Politics & Ideology"),
    ("economy", "Economy & Markets"),
    ("tech", "Industry, Tech & Industrial Policy"),
    ("geopolitics", "U.S.–China & Geopolitics"),
    ("regulatory", "Regulatory Watch"),
    ("society", "What's Trending"),
]
PILLAR_LABELS = dict(PILLARS)
PILLAR_ORDER = [k for k, _ in PILLARS]

# Simplified-Chinese block labels for the bilingual brief.
PILLAR_LABELS_ZH = {
    "politics": "高层政治与意识形态",
    "economy": "经济与市场",
    "tech": "产业、科技与工业政策",
    "geopolitics": "中美关系与地缘政治",
    "regulatory": "监管动态",
    "society": "热点风向",
}

# Soft per-pillar caps so no single block (usually social-trending) crowds out the
# institutional reporting. Greedy selection over weight-sorted candidates fills the
# highest-salience item in each pillar first.
PILLAR_CAPS = {
    "politics": 3,
    "economy": 3,
    "tech": 2,
    "geopolitics": 3,
    "regulatory": 2,
    "society": 4,
}

# Default pillar for the legacy single-source feeds (DeepSeek may reclassify).
SOURCE_PILLAR_DEFAULT = {
    "baidu_top": "society",
    "weibo_hot": "society",
    "tencent_wechat_hot": "society",
    "xinhua_news": "politics",
    "thepaper_news": "society",
    # gov_registry items carry their own per-channel `pillar` (set in the seed),
    # so they are not defaulted here — see the ingestion loop in collect_clusters.
}


def _pillar_rank(pillar: str) -> int:
    """Institutional pillars outrank ``society`` when a story merges across feeds."""
    return 0 if pillar == "society" else 1


# --------------------------------------------------------------------------- #
# Loading & normalization
# --------------------------------------------------------------------------- #
def _load(name: str) -> dict:
    path = f"{DATA_DIR}/{name}.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"items": []}


def _clean_title(title: str) -> str:
    """Strip leading rank prefixes like ``1. `` and surrounding whitespace."""
    return re.sub(r"^\s*\d+[\.、]\s*", "", title or "").strip()


def _normalize(title: str) -> str:
    """Collapse to comparable form for fuzzy cross-platform matching."""
    return re.sub(r"\s+", "", _clean_title(title).lower())


_CJK_RE = re.compile(r"[㐀-鿿豈-﫿]")


def _has_cjk(text: str) -> bool:
    """True if the string contains Han characters (so it is a real ZH title)."""
    return bool(_CJK_RE.search(text or ""))


# Western desks whose name often gets baked into the headline ("FT: ...").
_KNOWN_OUTLETS = (
    "ft", "financial times", "wsj", "wall street journal", "bloomberg",
    "reuters", "scmp", "south china morning post", "nikkei", "the economist",
    "nyt", "new york times", "caixin", "yicai",
)


def _strip_outlet_prefix(title: str, source: str = "") -> str:
    """Drop a leading "Outlet:" / "Outlet -" tag so it does not duplicate the
    source badge already shown on the card (e.g. "FT: China-US Tech Truce")."""
    t = (title or "").strip()
    if not t:
        return t
    prefixes = set(_KNOWN_OUTLETS)
    if source:
        prefixes.add(source.strip().lower())
    m = re.match(r"\s*([A-Za-z][A-Za-z.&'’\s]{1,28}?)\s*[:\-–—]\s+", t)
    if m and m.group(1).strip().lower().rstrip(".") in prefixes:
        return t[m.end():].strip()
    return t


def _strip_emdashes(text: str, zh: bool = False) -> str:
    """Remove em/en dashes used as punctuation (Tristan dislikes them).

    English text gets a comma; Chinese text gets a full-width comma so the
    result still reads naturally.
    """
    if not text:
        return text
    sep = "，" if zh else ", "
    t = re.sub(r"\s*[—–]+\s*", sep, text)        # — / – / —— with surrounding spaces
    t = re.sub(r"，{2,}", "，", t)
    t = re.sub(r"(,\s*){2,}", ", ", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()


def _is_restatement(quote: str, *titles: str) -> bool:
    """True if a pull quote merely echoes a title (no new information)."""
    q = _normalize(quote)
    if not q:
        return True
    for t in titles:
        n = _normalize(t)
        if not n:
            continue
        if q in n or n in q:
            return True
        if difflib.SequenceMatcher(None, q, n).ratio() >= 0.7:
            return True
    return False


def _similar(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.6


# --------------------------------------------------------------------------- #
# Candidate stories & cross-platform salience
# --------------------------------------------------------------------------- #
def _collect_candidates(data: dict) -> list[dict]:
    """Build a list of candidate stories with cross-platform appearances.

    Social/trending items are clustered across platforms by fuzzy title match;
    news and regulatory items are added as single-source candidates so the
    brief is not purely social.
    """
    clusters: list[dict] = []

    def add_appearance(
        title: str,
        url: str,
        platform: str,
        rank: int,
        desc: str,
        *,
        pillar_hint: str = "society",
        source_label: str = "",
        english_hint: str = "",
    ):
        clean = _clean_title(title)
        norm = _normalize(title)
        if not norm:
            return
        for c in clusters:
            if _similar(norm, c["norm"]):
                c["appearances"].append({"platform": platform, "rank": rank})
                c["platforms"].add(platform)
                # Prefer the longest description we have seen for context.
                if desc and len(desc) > len(c["description"]):
                    c["description"] = desc
                if not c["url"]:
                    c["url"] = url
                # An institutional pillar/source outranks a generic social one.
                if _pillar_rank(pillar_hint) > _pillar_rank(c["pillar_hint"]):
                    c["pillar_hint"] = pillar_hint
                    if source_label:
                        c["source"] = source_label
                if source_label and not c["source"]:
                    c["source"] = source_label
                if english_hint and not c["english_hint"]:
                    c["english_hint"] = english_hint
                return
        clusters.append(
            {
                "primary_title": clean,
                "norm": norm,
                "url": url,
                "description": desc or "",
                "platforms": {platform},
                "appearances": [{"platform": platform, "rank": rank}],
                "pillar_hint": pillar_hint,
                "source": source_label,
                "english_hint": english_hint,
            }
        )

    # Social trending platforms (drive cross-platform salience)
    for src in SOCIAL_SOURCES:
        for idx, item in enumerate(data.get(src, {}).get("items", [])):
            extra = item.get("extra") or {}
            rank = extra.get("rank") or (idx + 1)
            add_appearance(
                item.get("title", ""),
                item.get("url", ""),
                src,
                rank,
                extra.get("description", "") or extra.get("summary", ""),
                pillar_hint="society",
            )

    # Top news headlines (single-source, lower base weight)
    for src in ("xinhua_news", "thepaper_news"):
        for idx, item in enumerate(data.get(src, {}).get("items", [])[:6]):
            extra = item.get("extra") or {}
            add_appearance(
                item.get("title", ""),
                item.get("url", ""),
                src,
                idx + 1,
                extra.get("summary", ""),
                pillar_hint=SOURCE_PILLAR_DEFAULT.get(src, "society"),
                english_hint=extra.get("translation", "") or "",
            )

    # Elite / institutional press — party organs, financial, tech, Western desks.
    # These feed the High-Politics, Economy, Tech and Geopolitics blocks.
    for idx, item in enumerate(data.get("elite_press", {}).get("items", [])):
        extra = item.get("extra") or {}
        add_appearance(
            item.get("title", ""),
            item.get("url", ""),
            "elite_press",
            idx + 1,
            extra.get("summary", ""),
            pillar_hint=extra.get("pillar", "society") or "society",
            source_label=extra.get("source", "") or "",
            english_hint=extra.get("translation", "") or "",
        )

    # Primary-source ministry/regulator channels (gov_registry). Each item carries
    # its own canonical `pillar` (set per channel in gov_registry_sources.json), so
    # an MFA briefing lands in geopolitics, a MOFCOM ruling in economy, a CSRC notice
    # in regulatory, etc. — rather than collapsing every channel into "regulatory".
    for idx, item in enumerate(data.get("gov_registry", {}).get("items", [])):
        extra = item.get("extra") or {}
        agency = extra.get("agency_zh") or extra.get("agency") or ""
        add_appearance(
            item.get("title", ""),
            item.get("url", ""),
            "gov_registry",
            idx + 1,
            f"{agency} announcement",
            pillar_hint=extra.get("pillar", "regulatory") or "regulatory",
            source_label=agency,
            english_hint=extra.get("translation", "") or "",
        )

    for c in clusters:
        c["platforms"] = sorted(c["platforms"])
        c["platform_count"] = len(c["platforms"])
        c["weight"] = round(_score(c), 2)
    clusters.sort(key=lambda c: c["weight"], reverse=True)
    return clusters


def _score(cluster: dict) -> float:
    """Higher = more salient. Rewards top ranks and cross-platform spread."""
    base = sum(max(1, 11 - a["rank"]) for a in cluster["appearances"])
    cross_platform_bonus = 1 + 0.6 * (cluster["platform_count"] - 1)
    return base * cross_platform_bonus


def _categorize(title: str, platforms: list[str]) -> str:
    if "gov_registry" in platforms:
        return "regulatory"
    if "elite_press" in platforms:
        return "press"
    if any(p in platforms for p in ("xinhua_news", "thepaper_news")):
        return "news"
    return "social"


def _select_balanced(candidates: list[dict]) -> list[dict]:
    """Pick a thematically balanced set, not just the top-N by social salience.

    Candidates arrive weight-sorted, so a greedy pass with per-pillar caps keeps
    the most salient item in each block while guaranteeing the institutional
    pillars (politics, economy, tech, geopolitics) are represented rather than
    being buried under high-velocity social-trending stories.
    """
    caps = dict(PILLAR_CAPS)
    selected: list[dict] = []
    for c in candidates:
        pillar = c.get("pillar_hint", "society")
        if caps.get(pillar, 0) <= 0:
            continue
        selected.append(c)
        caps[pillar] -= 1
        if len(selected) >= MAX_STORIES:
            break
    return selected


# --------------------------------------------------------------------------- #
# Market snapshot (deterministic, always available)
# --------------------------------------------------------------------------- #
def _fmt_pct(pct) -> str:
    if pct is None:
        return ""
    try:
        pct = float(pct)
    except (TypeError, ValueError):
        return ""
    arrow = "▲" if pct > 0 else "▼" if pct < 0 else "→"
    return f"{arrow}{abs(pct):.2f}%"


def _market_snapshot(data: dict) -> str:
    parts = []
    for item in data.get("indices", {}).get("items", [])[:3]:
        pct = _fmt_pct((item.get("extra") or {}).get("chg_pct"))
        parts.append(f"{item.get('title')} {item.get('value')} {pct}".strip())
    for item in data.get("fx", {}).get("items", [])[:2]:
        if item.get("title") in ("USD/CNY", "USD/CNH"):
            pct = _fmt_pct((item.get("extra") or {}).get("chg_pct"))
            parts.append(f"{item.get('title')} {item.get('value')} {pct}".strip())
    return " · ".join(p for p in parts if p)


# --------------------------------------------------------------------------- #
# DeepSeek synthesis (with deterministic fallback)
# --------------------------------------------------------------------------- #
def _deepseek_synthesis(stories: list[dict], market: str, beijing_date: str):
    """Return (meta, story_overrides) from DeepSeek, or None on any failure."""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print(
            "[digest] DEEPSEEK_API_KEY is not set — skipping LLM synthesis, "
            "falling back to the deterministic heuristic digest.",
            file=sys.stderr,
        )
        return None
    if OpenAI is None:
        print(
            "[digest] openai package is not importable — skipping LLM synthesis, "
            "falling back to the deterministic heuristic digest.",
            file=sys.stderr,
        )
        return None

    story_lines = []
    for i, s in enumerate(stories, 1):
        src = s.get("source") or ", ".join(
            PLATFORM_LABELS.get(p, p) for p in s["platforms"]
        )
        en = s.get("english_hint") or ""
        desc = (s.get("description") or "")[:220]
        title = s["primary_title"]
        if en and en != title:
            title = f"{title} ({en})"
        story_lines.append(
            f'{i}. [pillar={s["pillar_hint"]}; source={src}] {title} — {desc}'
        )

    pillar_keys = ", ".join(PILLAR_ORDER)
    prompt = (
        f"You are a sharp, sober China analyst writing the daily intelligence brief for "
        f"{beijing_date} (Beijing time), in the house style of an elite China newsletter "
        f"(à la Sinocism). Your readers are analysts, investors and policymakers who already "
        f"know the basic institutions — write peer-to-peer, no hand-holding. Treat the Party "
        f"as an effective, ideological, institutional actor: avoid both boosterism and alarmism, "
        f"apply measured skepticism to official triumphalism and to Western spin alike.\n\n"
        f"Below are the day's most salient items, each tagged with a provisional thematic "
        f"pillar and its source, plus a market snapshot.\n\n"
        f"MARKET SNAPSHOT: {market or 'n/a'}\n\n"
        f"RANKED ITEMS:\n" + "\n".join(story_lines) + "\n\n"
        f"Allowed pillar values: {pillar_keys}.\n\n"
        "PILLAR RULES:\n"
        "- Xi Jinping, the Politburo, Party ideology, personnel moves and "
        "anti-corruption cases belong in 'politics', even when they are also "
        "trending socially.\n"
        "- 'society' (What's Trending) is only for genuinely non-institutional "
        "viral culture, entertainment and consumer stories.\n"
        "- This is a CHINA brief. If an item has no real China angle (e.g. a purely "
        "foreign story like a Middle East ceasefire), set its pillar to 'drop'. Do "
        "NOT invent a China hook to keep it. Also 'drop' pure feel-good propaganda or "
        "trivia that carries no analytical signal.\n\n"
        "Do NOT use em dashes (—) anywhere in your output; use commas or full stops "
        "instead. The dashboard is fully bilingual, so every English field needs a "
        "natural Simplified Chinese counterpart (not a literal word-for-word gloss).\n\n"
        "Return STRICT JSON with this shape:\n"
        "{\n"
        '  "headline": "<=90 char English top-of-mind takeaway: the single biggest thing",\n'
        '  "headline_zh": "上述 headline 的简体中文版(<=40字)",\n'
        '  "narrative": "1-2 punchy paragraphs (the Lead-in): name the most important '
        'structural story of the day and say what it signals. Be specific and analytical, '
        'not a list. No filler like \'X is trending across platforms\'.",\n'
        '  "narrative_zh": "上述导读的简体中文版(1-2段)",\n'
        '  "themes": ["3-6 short theme tags"],\n'
        '  "entities": ["key people/orgs/places mentioned"],\n'
        '  "stories": [{"index": <1-based index above>, '
        '"pillar": "<one allowed pillar value, or \'drop\' to exclude. Reclassify if the provisional tag is wrong>", '
        '"english_title": "concise EN title; do NOT prefix the outlet name (the source is shown separately)", '
        '"why_it_matters": "one crisp sentence on why this matters / what to read between the lines", '
        '"why_it_matters_zh": "上一句 why_it_matters 的简体中文版", '
        '"pull_quote": "optional <=140 char quote or hard fact that ADDS information beyond the title. '
        'Must not restate the headline. Use \\"\\" if you have nothing genuinely new", '
        '"pull_quote_zh": "上一句 pull_quote 的简体中文版(若 pull_quote 为空则留空)"}]\n'
        "}\n"
        "Cover every ranked item in stories. JSON only."
    )

    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=[
                {"role": "system", "content": "You are a precise geopolitical news analyst. Output valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            # deepseek-v4-flash is a reasoning model: hidden reasoning tokens are
            # billed against max_tokens before any JSON is emitted. 2000 was too
            # tight — reasoning ate the budget and `content` came back empty,
            # silently forcing the heuristic fallback. Give generous headroom.
            max_tokens=8000,
            temperature=0.4,
            timeout=120,
        )
        parsed = json.loads(resp.choices[0].message.content)
        overrides = {}
        for s in parsed.get("stories", []):
            idx = s.get("index")
            if isinstance(idx, int) and 1 <= idx <= len(stories):
                pillar = (s.get("pillar") or "").strip().lower()
                overrides[idx - 1] = {
                    "english_title": _strip_emdashes((s.get("english_title") or "").strip()),
                    "why_it_matters": _strip_emdashes((s.get("why_it_matters") or "").strip()),
                    "why_it_matters_zh": _strip_emdashes((s.get("why_it_matters_zh") or "").strip(), zh=True),
                    "pull_quote": _strip_emdashes((s.get("pull_quote") or "").strip()),
                    "pull_quote_zh": _strip_emdashes((s.get("pull_quote_zh") or "").strip(), zh=True),
                    "pillar": pillar if pillar in PILLAR_LABELS or pillar == "drop" else "",
                }
        meta = {
            "headline": _strip_emdashes((parsed.get("headline") or "").strip()),
            "headline_zh": _strip_emdashes((parsed.get("headline_zh") or "").strip(), zh=True),
            "narrative": _strip_emdashes((parsed.get("narrative") or "").strip()),
            "narrative_zh": _strip_emdashes((parsed.get("narrative_zh") or "").strip(), zh=True),
            "themes": [t for t in parsed.get("themes", []) if t][:6],
            "entities": [e for e in parsed.get("entities", []) if e][:12],
        }
        return meta, overrides
    except Exception as exc:  # pragma: no cover - network/parse failures
        msg = str(exc)
        if api_key:
            msg = msg.replace(api_key, "***")
        print(f"DeepSeek synthesis failed, using heuristic fallback: {msg[:160]}")
        return None


def _heuristic_meta(stories: list[dict], market: str) -> dict:
    lead = stories[0]["primary_title"] if stories else "China daily snapshot"
    cross = [s for s in stories if s["platform_count"] >= 2]
    headline = (cross[0]["primary_title"] if cross else lead)[:90]
    themes = []
    for s in stories[:6]:
        themes.append(_categorize(s["primary_title"], s["platforms"]))
    themes = sorted(set(themes))
    narrative = (
        f"Top of mind: {lead}. "
        f"{len(cross)} stories are trending across multiple major platforms, "
        f"signalling broad public attention. "
        + (f"Markets: {market}." if market else "")
    ).strip()
    return {
        "headline": headline,
        "headline_zh": headline,
        "narrative": narrative,
        "narrative_zh": "本简报由跨平台热度自动汇总生成（未经语言模型润色）。",
        "themes": themes,
        "entities": [],
    }


# --------------------------------------------------------------------------- #
# Markdown rendering
# --------------------------------------------------------------------------- #
def _render_markdown(digest: dict) -> str:
    lines = [
        f"# China Daily Digest · {digest['time_label']}",
        "",
        f"_{digest['date']} · {digest['beijing_time']} Beijing · "
        f"generated by `{digest['generated_by']}`_",
        "",
        f"**{digest['headline']}**",
        "",
        digest["narrative"],
        "",
    ]
    if digest.get("market_snapshot"):
        lines += [f"**Markets:** {digest['market_snapshot']}", ""]
    if digest.get("themes"):
        lines += ["**Themes:** " + ", ".join(digest["themes"]), ""]

    # Group stories into Sinocism-style thematic blocks, in canonical order.
    pillars = digest.get("pillars") or [
        {"key": k, "label": v} for k, v in PILLARS
    ]
    stories = digest["top_stories"]
    for pillar in pillars:
        block = [s for s in stories if s.get("pillar") == pillar["key"]]
        if not block:
            continue
        lines += [f"## {pillar['label']}", ""]
        for s in block:
            plats = ", ".join(PLATFORM_LABELS.get(p, p) for p in s["platforms"])
            src = s.get("source") or plats
            title = s.get("english_title") or s["primary_title"]
            lines.append(f"- **{title}** _{src}_  ")
            # Only show the original-language line when it is a real ZH headline,
            # never an English restatement of the English title.
            if title != s["primary_title"] and _has_cjk(s["primary_title"]):
                lines.append(f"  {s['primary_title']}  ")
            if s.get("why_it_matters"):
                lines.append(f"  {s['why_it_matters']}  ")
            if s.get("pull_quote"):
                lines.append(f"  > {s['pull_quote']}  ")
            if s.get("url"):
                lines.append(f"  <{s['url']}>")
            lines.append("")
    lines += ["---", "", digest["disclaimer"], ""]
    return "\n".join(lines)


def _write_text(path: str, content: str) -> None:
    abs_path = os.path.abspath(path)
    if not abs_path.startswith(os.path.abspath(DATA_DIR)):
        raise ValueError(f"Refusing to write outside {DATA_DIR}: {path}")
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(content)


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def _slot(hour: int) -> tuple[str, str]:
    if hour < 11:
        return "morning", "Morning Brief"
    if hour < 16:
        return "midday", "Midday Brief"
    return "evening", "Evening Brief"


def _prior_briefs() -> list[tuple[str, list[dict]]]:
    """(date, top_stories) for each archived brief. Called before this run's
    archive is written, so it reflects strictly *prior* briefs."""
    out: list[tuple[str, list[dict]]] = []
    for path in Path(ARCHIVE_DIR).glob("*/*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        out.append((d.get("date", ""), d.get("top_stories", [])))
    return out


def _theme_in_story(theme: str, story: dict) -> bool:
    """Whether a story is about a theme. Same keyword relation the tag index /
    hashtag view uses, but with word-boundary matching so short tokens like
    "us" don't spuriously match "industry"."""
    from collectors.tags_index import story_text, tag_keywords

    text = story_text(story)
    for kw in tag_keywords(theme):
        if re.fullmatch(r"[a-z0-9]+", kw):  # Latin token: match whole word
            if re.search(rf"\b{re.escape(kw)}\b", text):
                return True
        elif kw in text:  # CJK run: no word boundaries to anchor
            return True
    return False


def _theme_trends(themes: list[str], today: str) -> dict:
    """Classify each of today's themes as new / rising / recurring by how many
    distinct prior days in the trailing week had a story about that theme.

    Keyword matching (not exact strings) is essential: DeepSeek rephrases themes
    every run ("US-China relations" vs "China-US tech competition"), so the same
    underlying topic only lines up at the keyword level."""
    briefs = _prior_briefs()
    try:
        t0 = datetime.strptime(today, "%Y-%m-%d").date()
    except ValueError:
        t0 = None

    out: dict[str, dict] = {}
    for theme in themes:
        days: set[str] = set()
        for date, stories in briefs:
            if not date or date == today:
                continue  # same-day runs don't count as "prior"
            if t0 is not None:
                try:
                    delta = (t0 - datetime.strptime(date, "%Y-%m-%d").date()).days
                except ValueError:
                    continue
                if not (0 < delta <= THEME_TREND_WINDOW_DAYS):
                    continue
            if any(_theme_in_story(theme, s) for s in stories):
                days.add(date)
        n = len(days)
        if n == 0:
            status = "new"
        elif n >= THEME_RECURRING_DAYS:
            status = "recurring"
        else:
            status = "rising"
        out[theme] = {"status": status, "days_seen": n}
    return out


def build_digest() -> dict:
    sources = [
        "baidu_top", "weibo_hot", "tencent_wechat_hot",
        "xinhua_news", "thepaper_news", "ladymax_news",
        "gov_registry", "elite_press", "indices", "fx",
    ]
    data = {name: _load(name) for name in sources}

    now = datetime.now(timezone(timedelta(hours=8)))
    slot, label = _slot(now.hour)
    market = _market_snapshot(data)

    candidates = _collect_candidates(data)
    stories = _select_balanced(candidates)

    synthesis = _deepseek_synthesis(stories, market, now.strftime("%Y-%m-%d"))
    generated_by = "deepseek-v4-flash"
    if synthesis is None:
        meta, overrides = _heuristic_meta(stories, market), {}
        generated_by = "heuristic"
        print(
            "[digest] generated_by=heuristic (DeepSeek synthesis unavailable). "
            "Set/refresh the DEEPSEEK_API_KEY secret to restore LLM synthesis.",
            file=sys.stderr,
        )
    else:
        meta, overrides = synthesis
        print("[digest] generated_by=deepseek-v4-flash", file=sys.stderr)

    top_stories = []
    for i, s in enumerate(stories):
        override = overrides.get(i, {})
        pillar = override.get("pillar") or s.get("pillar_hint") or "society"
        # DeepSeek flags items with no real China angle (or pure puff) as "drop".
        if pillar == "drop":
            continue

        source = s.get("source", "")
        primary_title = _strip_emdashes(_strip_outlet_prefix(s["primary_title"], source))
        english_title = _strip_emdashes(_strip_outlet_prefix(
            override.get("english_title", "") or s.get("english_hint", ""), source
        ))

        # Drop a pull quote that just echoes either title (adds no information).
        pull_quote = override.get("pull_quote", "")
        pull_quote_zh = override.get("pull_quote_zh", "")
        if _is_restatement(pull_quote, primary_title, english_title):
            pull_quote = ""
            pull_quote_zh = ""

        top_stories.append(
            {
                "rank": len(top_stories) + 1,
                "weight": s["weight"],
                "platforms": s["platforms"],
                "platform_count": s["platform_count"],
                "primary_title": primary_title,
                "english_title": english_title,
                "why_it_matters": override.get("why_it_matters", ""),
                "why_it_matters_zh": override.get("why_it_matters_zh", ""),
                "pull_quote": pull_quote,
                "pull_quote_zh": pull_quote_zh,
                "pillar": pillar,
                "pillar_label": PILLAR_LABELS.get(pillar, ""),
                "pillar_label_zh": PILLAR_LABELS_ZH.get(pillar, ""),
                "source": source,
                "category": _categorize(s["primary_title"], s["platforms"]),
                "url": s["url"],
                "appearances": s["appearances"],
            }
        )

    # Pillars actually present, in canonical render order (for the frontend blocks).
    present = {s["pillar"] for s in top_stories}
    pillars = [
        {"key": k, "label": PILLAR_LABELS[k], "label_zh": PILLAR_LABELS_ZH.get(k, "")}
        for k in PILLAR_ORDER if k in present
    ]

    digest = {
        "digest_type": slot,
        "as_of": now_iso_tz8(),
        "date": now.strftime("%Y-%m-%d"),
        "time_label": label,
        "beijing_time": now.strftime("%H:%M"),
        "generated_by": generated_by,
        "headline": meta["headline"],
        "headline_zh": meta.get("headline_zh", ""),
        "narrative": meta["narrative"],
        "narrative_zh": meta["narrative_zh"],
        "market_snapshot": market,
        "themes": meta["themes"],
        "theme_trends": _theme_trends(meta["themes"], now.strftime("%Y-%m-%d")),
        "entities": meta["entities"],
        "pillars": pillars,
        "top_stories": top_stories,
        "sources_summary": {
            name: len(data[name].get("items", [])) for name in sources
        },
        "disclaimer": (
            "Auto-generated from public Chinese sources for informational use only. "
            "Salience reflects cross-platform attention, not editorial endorsement."
        ),
    }
    return digest


def _slim_for_history(d: dict) -> dict:
    """Keep only the fields the dashboard brief actually renders, so the
    consolidated history file stays small even with dozens of snapshots."""
    stories = [
        {
            "primary_title": s.get("primary_title", ""),
            "english_title": s.get("english_title", ""),
            "why_it_matters": s.get("why_it_matters", ""),
            "why_it_matters_zh": s.get("why_it_matters_zh", ""),
            "pull_quote": s.get("pull_quote", ""),
            "pull_quote_zh": s.get("pull_quote_zh", ""),
            "pillar": s.get("pillar", ""),
            "platforms": s.get("platforms", []),
            "platform_count": s.get("platform_count", 0),
            "source": s.get("source", ""),
            "url": s.get("url", ""),
        }
        for s in d.get("top_stories", [])
    ]
    return {
        "as_of": d.get("as_of", ""),
        "date": d.get("date", ""),
        "time_label": d.get("time_label", ""),
        "beijing_time": d.get("beijing_time", ""),
        "digest_type": d.get("digest_type", ""),
        "generated_by": d.get("generated_by", ""),
        "headline": d.get("headline", ""),
        "headline_zh": d.get("headline_zh", ""),
        "narrative": d.get("narrative", ""),
        "narrative_zh": d.get("narrative_zh", ""),
        "market_snapshot": d.get("market_snapshot", ""),
        "themes": d.get("themes", []),
        "theme_trends": d.get("theme_trends", {}),
        "pillars": d.get("pillars", []),
        "top_stories": stories,
    }


def _rebuild_history() -> None:
    """Re-derive the newest-first brief history from the on-disk archive."""
    snaps: list[dict] = []
    for path in Path(ARCHIVE_DIR).glob("*/*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                snaps.append(json.load(f))
        except (OSError, json.JSONDecodeError):
            continue
    snaps.sort(key=lambda d: d.get("as_of", ""), reverse=True)
    entries = [_slim_for_history(d) for d in snaps[:HISTORY_LIMIT]]
    payload = {
        "as_of": now_iso_tz8(),
        "source": "daily_digest archive",
        "count": len(entries),
        "entries": entries,
    }
    write_json(HISTORY_JSON, payload, indent=2, min_items=0)


def main() -> None:
    digest = build_digest()

    write_json(DIGEST_JSON, digest, indent=2, min_items=0)
    _write_text(DIGEST_MD, _render_markdown(digest))

    archive_path = f"{ARCHIVE_DIR}/{digest['date']}/{digest['digest_type']}.json"
    write_json(archive_path, digest, indent=2, min_items=0)

    # Refresh the consolidated history index (reads the archive we just wrote).
    _rebuild_history()

    # Fold this run's themed stories into the cumulative tag index so the
    # dashboard's clickable tags accrue historical depth over time.
    try:
        index = tags.load_index()
        added = tags.apply_digest(
            index, digest.get("themes", []), digest.get("top_stories", []), digest["date"]
        )
        index["updated_at"] = digest["as_of"]
        write_json(tags.INDEX_PATH, index, indent=2, min_items=0)
        print(f"Tag index updated: +{added} story-tag links "
              f"({len(index['tags'])} tags) → {tags.INDEX_PATH}")
    except Exception as e:  # never let tag indexing break the digest
        print(f"::warning::Tag index update failed: {e}", file=sys.stderr)

    print(
        f"Daily digest written: {len(digest['top_stories'])} stories "
        f"({digest['generated_by']}) → {DIGEST_JSON}, {DIGEST_MD}"
    )


if __name__ == "__main__":
    main()
