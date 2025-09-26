"""Collector for LadyMax (时尚头条网) mobile headlines with translations."""

from __future__ import annotations

import re
import sys
from datetime import timedelta, timezone
from html import unescape
from pathlib import Path
from typing import List
from urllib.parse import urljoin

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from bs4 import BeautifulSoup  # type: ignore
from dateutil import parser as dateparser  # type: ignore
from dotenv import load_dotenv

load_dotenv()

from collectors.common import (
    backoff_sleep,
    base_headers,
    schema,
    translate_text,
    write_with_history,
)

OUT = "docs/data/ladymax_news.json"
HISTORY_OUT = "docs/data/history/ladymax_news.json"
BASE_URL = "http://m.ladymax.cn/"
MAX_ITEMS = 21
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3


def _normalise_datetime(raw: str) -> str:
    if not raw:
        return ""

    text = unescape(raw).strip()
    if not text:
        return ""

    cleaned = (
        text.replace("年", "-")
        .replace("月", "-")
        .replace("日", " ")
        .replace("时", ":")
        .replace("点", ":")
        .replace("分", ":")
        .replace("秒", "")
    )
    cleaned = cleaned.replace("上午", " AM ").replace("下午", " PM ")
    cleaned = re.sub(r"[\u4e00-\u9fff]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not any(char.isdigit() for char in cleaned):
        return ""

    try:
        dt = dateparser.parse(cleaned, dayfirst=False, yearfirst=True)
        if not dt:
            return ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return ""


def _guess_category_from_url(url: str) -> str:
    path = url.lower()
    if "/fashion/" in path:
        return "时尚"
    if "/business/" in path:
        return "商业"
    if "/retail/" in path:
        return "零售"
    if "/innovation/" in path or "/tech/" in path:
        return "创新"
    if "/analysis/" in path or "/report/" in path:
        return "分析"
    if "/watch/" in path:
        return "腕表"
    if "/jewelry/" in path:
        return "珠宝"
    if "/beauty/" in path:
        return "美妆"
    if "/sustainability/" in path:
        return "可持续"
    if "/lifestyle/" in path:
        return "生活方式"
    return "资讯"


def _extract_summary(node: BeautifulSoup, title: str) -> str:
    title = title.strip()
    seen = {title}
    candidates: List[str] = []

    for tag in node.find_all(["p", "div", "span"], limit=6):
        text = unescape(tag.get_text(" ", strip=True))
        text = re.sub(r"\s+", " ", text).strip()
        if not text or text in seen:
            continue
        if len(text) < 10:
            continue
        if text.startswith(title) or title.startswith(text):
            continue
        if text not in candidates:
            candidates.append(text)

    return candidates[0][:300] if candidates else ""


def _extract_datetime(node: BeautifulSoup) -> str:
    for tag in node.find_all(["time", "span", "em", "i"], limit=6):
        text = tag.get_text(" ", strip=True)
        if not text:
            continue
        normalised = _normalise_datetime(text)
        if normalised:
            return normalised
    return ""


def _fetch_homepage() -> str:
    headers = base_headers()
    headers.update(
        {
            "Referer": BASE_URL,
            "Connection": "keep-alive",
        }
    )

    session = requests.Session()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(BASE_URL, headers=headers, timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                print(f"LadyMax homepage returned HTTP {response.status_code}")
                backoff_sleep(attempt)
                continue
            response.encoding = response.apparent_encoding or response.encoding
            return response.text
        except requests.RequestException as exc:
            print(f"LadyMax homepage fetch error: {exc}")
            backoff_sleep(attempt)

    return ""


def _parse_articles(html: str, max_items: int) -> List[dict]:
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    results: List[dict] = []
    seen_urls: set[str] = set()

    selectors = [
        "div.list-article a",
        "div.list_article a",
        "div.article-list a",
        "div.news-list a",
        "div.list_news a",
        "ul.list li a",
        "article a",
        "a[href]",
    ]

    for selector in selectors:
        for link in soup.select(selector):
            href = (link.get("href") or "").strip()
            title = link.get_text(" ", strip=True)

            if not href or not title:
                continue
            if href.startswith("javascript") or href.startswith("#"):
                continue

            absolute_url = urljoin(BASE_URL, href)
            if absolute_url in seen_urls:
                continue

            seen_urls.add(absolute_url)

            parent = link.find_parent(["li", "article", "div"]) or link
            summary = _extract_summary(parent, title)
            published = _extract_datetime(parent)
            category = _guess_category_from_url(absolute_url)

            results.append(
                {
                    "title": title.strip(),
                    "url": absolute_url,
                    "summary": summary,
                    "published": published,
                    "category": category,
                }
            )

            if len(results) >= max_items:
                return results

    return results


def fetch_ladymax_news(max_items: int = MAX_ITEMS) -> List[dict]:
    html = _fetch_homepage()
    articles = _parse_articles(html, max_items)

    items: List[dict] = []
    for article in articles:
        title = article.get("title", "").strip()
        translation = translate_text(title) if title else ""
        summary = article.get("summary", "").strip()
        if len(summary) > 300:
            summary = summary[:297] + "..."

        items.append(
            {
                "title": title or "(无标题)",
                "value": "",
                "url": article.get("url", ""),
                "extra": {
                    "category": article.get("category", ""),
                    "published": article.get("published", ""),
                    "summary": summary,
                    "source_feed": BASE_URL,
                    "source_name": "LadyMax 时尚头条网",
                    "translation": translation,
                },
            }
        )

    return items


def main() -> None:
    items = fetch_ladymax_news()
    payload = schema("LadyMax 时尚头条网", items)
    write_with_history(OUT, HISTORY_OUT, payload)


if __name__ == "__main__":
    main()
