"""Cumulative tag → stories index for the dashboard.

The live GitHub Pages site only keeps a rolling 3-snapshot window of JSON, but
Neon Postgres holds the full append-only history. This module maintains
``docs/data/tags_index.json``: a growing map of theme tag → stories seen over
time, so the dashboard can offer clickable tags that surface historical
stories *without* needing a backend to query Neon at request time.

Used by:
  - ``daily_digest.py``           appends each run's themed stories (forward fill)
  - ``backfill_tags_index.py``    one-time seed from Neon news_items (back fill)
"""

from __future__ import annotations

import json
import os
import re

INDEX_PATH = "docs/data/tags_index.json"

# Keep the index bounded so the committed JSON stays small and fast to fetch.
MAX_PER_TAG = 300

# Words too generic to be useful when matching a theme tag against a headline.
_STOP = {
    "the", "a", "an", "and", "of", "in", "on", "to", "for", "s", "with", "at",
    "by", "as", "is", "are", "amid", "over", "from", "china", "chinese",
    "chinas", "new", "policy", "issues", "case", "cases",
}


# Generic section/category names that leak in as "themes" on heuristic
# (non-DeepSeek) days. They duplicate the dashboard's section filter and make
# poor tags, so we never index them.
_GENERIC = {"social", "news", "markets", "market", "macro", "regulatory",
            "general", "other", "trending"}


def is_meaningful(tag: str) -> bool:
    return normalize_tag(tag) not in _GENERIC and len(tag_keywords(tag)) > 0


def normalize_tag(tag: str) -> str:
    """Canonical lowercase key for a tag (display label kept separately)."""
    return re.sub(r"\s+", " ", (tag or "").strip().lower())


def tag_keywords(tag: str) -> list[str]:
    """Significant tokens of a tag, used for substring-matching headlines.

    Handles both Latin words and CJK runs; drops stopwords and 1-char noise.
    """
    toks = re.findall(r"[a-z0-9]+|[一-鿿]+", (tag or "").lower())
    out = []
    for t in toks:
        if t in _STOP:
            continue
        # Latin tokens must be >1 char; CJK single chars are too ambiguous too.
        if len(t) > 1:
            out.append(t)
    return out


def story_text(story: dict) -> str:
    """All searchable text of a story record, lowercased."""
    keys = ("english_title", "primary_title", "title", "title_en", "why_it_matters")
    return " ".join(str(story.get(k, "")) for k in keys).lower()


def story_matches(story: dict, tag: str) -> bool:
    """True if any significant keyword of ``tag`` appears in the story text."""
    kws = tag_keywords(tag)
    if not kws:
        return False
    text = story_text(story)
    return any(k in text for k in kws)


def load_index(path: str = INDEX_PATH) -> dict:
    """Load the existing index, or a fresh empty one."""
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("tags"), dict):
                return data
        except Exception:
            pass
    return {"updated_at": None, "tags": {}}


def _story_key(s: dict) -> tuple[str, str]:
    """Identity for dedup: same day + same url (or title) = same story."""
    ident = (s.get("url") or s.get("english_title") or s.get("primary_title")
             or s.get("title") or "").strip().lower()
    return (s.get("date", ""), ident)


def make_record(story: dict, date: str) -> dict:
    """Compact, frontend-friendly story record for the index."""
    return {
        "date": date,
        "title": story.get("primary_title") or story.get("title") or "",
        "english_title": story.get("english_title") or story.get("title_en") or "",
        "url": story.get("url", ""),
        "platforms": story.get("platforms", []),
        "category": story.get("category", ""),
    }


def add_story(index: dict, tag: str, record: dict) -> bool:
    """Insert ``record`` under ``tag`` (most-recent first). Returns True if new."""
    key = normalize_tag(tag)
    if not key:
        return False
    entry = index["tags"].setdefault(key, {"label": tag, "count": 0, "stories": []})
    entry["label"] = tag  # keep latest display capitalization
    sk = _story_key(record)
    if any(_story_key(e) == sk for e in entry["stories"]):
        return False
    entry["stories"].insert(0, record)
    # Newest first, capped.
    entry["stories"].sort(key=lambda r: r.get("date", ""), reverse=True)
    entry["stories"] = entry["stories"][:MAX_PER_TAG]
    entry["count"] = len(entry["stories"])
    return True


def apply_digest(index: dict, themes: list[str], stories: list[dict], date: str) -> int:
    """Fold one digest's themed stories into ``index``. Returns # added.

    Each theme is attached to the stories whose headline mentions a keyword of
    that theme. If a theme matches nothing (it's a high-level synthesis label),
    the day's lead story is attached so the tag is never empty.
    """
    added = 0
    for theme in themes or []:
        if not is_meaningful(theme):
            continue
        matched = False
        for s in stories or []:
            if story_matches(s, theme):
                if add_story(index, theme, make_record(s, date)):
                    added += 1
                matched = True
        if not matched and stories:
            if add_story(index, theme, make_record(stories[0], date)):
                added += 1
    return added
