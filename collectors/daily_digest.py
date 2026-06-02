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

# Trending platforms contribute to cross-platform salience scoring.
SOCIAL_SOURCES = ["baidu_top", "weibo_hot", "tencent_wechat_hot"]
PLATFORM_LABELS = {
    "baidu_top": "Baidu",
    "weibo_hot": "Weibo",
    "tencent_wechat_hot": "WeChat",
    "xinhua_news": "Xinhua",
    "thepaper_news": "The Paper",
    "gov_regulatory": "Regulatory",
}
MAX_STORIES = 8


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

    def add_appearance(title: str, url: str, platform: str, rank: int, desc: str):
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
                return
        clusters.append(
            {
                "primary_title": clean,
                "norm": norm,
                "url": url,
                "description": desc or "",
                "platforms": {platform},
                "appearances": [{"platform": platform, "rank": rank}],
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
            )

    # Regulatory announcements always matter for a China brief
    for idx, item in enumerate(data.get("gov_regulatory", {}).get("items", [])):
        extra = item.get("extra") or {}
        agency = extra.get("agency_zh") or extra.get("agency") or ""
        add_appearance(
            item.get("title", ""),
            item.get("url", ""),
            "gov_regulatory",
            idx + 1,
            f"{agency} announcement",
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
    if "gov_regulatory" in platforms:
        return "regulatory"
    if any(p in platforms for p in ("xinhua_news", "thepaper_news")):
        return "news"
    return "social"


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
        plats = ", ".join(PLATFORM_LABELS.get(p, p) for p in s["platforms"])
        desc = (s.get("description") or "")[:160]
        story_lines.append(f'{i}. [{plats}] {s["primary_title"]} — {desc}')

    prompt = (
        f"You are a China analyst writing a concise daily intelligence brief for "
        f"{beijing_date} (Beijing time). Below are the most salient trending topics, "
        f"news headlines and regulatory items, already ranked by cross-platform salience, "
        f"plus a market snapshot.\n\n"
        f"MARKET SNAPSHOT: {market or 'n/a'}\n\n"
        f"RANKED ITEMS:\n" + "\n".join(story_lines) + "\n\n"
        "Return STRICT JSON with this shape:\n"
        "{\n"
        '  "headline": "<=90 char English top-of-mind takeaway",\n'
        '  "narrative": "2-3 short paragraphs of plain-English analysis of what these signals mean",\n'
        '  "narrative_zh": "上述内容的简体中文摘要(2-3段)",\n'
        '  "themes": ["3-6 short theme tags"],\n'
        '  "entities": ["key people/orgs/places mentioned"],\n'
        '  "stories": [{"index": <1-based index above>, "english_title": "concise EN title", '
        '"why_it_matters": "one sentence on significance"}]\n'
        "}\n"
        "Cover every ranked item in stories. Be neutral and factual. JSON only."
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
                overrides[idx - 1] = {
                    "english_title": (s.get("english_title") or "").strip(),
                    "why_it_matters": (s.get("why_it_matters") or "").strip(),
                }
        meta = {
            "headline": (parsed.get("headline") or "").strip(),
            "narrative": (parsed.get("narrative") or "").strip(),
            "narrative_zh": (parsed.get("narrative_zh") or "").strip(),
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
        f"# China Daily Digest — {digest['time_label']}",
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
    lines += ["## Top stories", ""]
    for s in digest["top_stories"]:
        plats = ", ".join(PLATFORM_LABELS.get(p, p) for p in s["platforms"])
        title = s.get("english_title") or s["primary_title"]
        lines.append(f"{s['rank']}. **{title}**  ")
        lines.append(f"   {s['primary_title']} · _{plats}_ (salience {s['weight']})  ")
        if s.get("why_it_matters"):
            lines.append(f"   {s['why_it_matters']}  ")
        if s.get("url"):
            lines.append(f"   <{s['url']}>")
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


def build_digest() -> dict:
    sources = [
        "baidu_top", "weibo_hot", "tencent_wechat_hot",
        "xinhua_news", "thepaper_news", "ladymax_news",
        "gov_regulatory", "indices", "fx",
    ]
    data = {name: _load(name) for name in sources}

    now = datetime.now(timezone(timedelta(hours=8)))
    slot, label = _slot(now.hour)
    market = _market_snapshot(data)

    candidates = _collect_candidates(data)
    stories = candidates[:MAX_STORIES]

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
        top_stories.append(
            {
                "rank": i + 1,
                "weight": s["weight"],
                "platforms": s["platforms"],
                "platform_count": s["platform_count"],
                "primary_title": s["primary_title"],
                "english_title": override.get("english_title", ""),
                "why_it_matters": override.get("why_it_matters", ""),
                "category": _categorize(s["primary_title"], s["platforms"]),
                "url": s["url"],
                "appearances": s["appearances"],
            }
        )

    digest = {
        "digest_type": slot,
        "as_of": now_iso_tz8(),
        "date": now.strftime("%Y-%m-%d"),
        "time_label": label,
        "beijing_time": now.strftime("%H:%M"),
        "generated_by": generated_by,
        "headline": meta["headline"],
        "narrative": meta["narrative"],
        "narrative_zh": meta["narrative_zh"],
        "market_snapshot": market,
        "themes": meta["themes"],
        "entities": meta["entities"],
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


def main() -> None:
    digest = build_digest()

    write_json(DIGEST_JSON, digest, indent=2, min_items=0)
    _write_text(DIGEST_MD, _render_markdown(digest))

    archive_path = f"{ARCHIVE_DIR}/{digest['date']}/{digest['digest_type']}.json"
    write_json(archive_path, digest, indent=2, min_items=0)

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
