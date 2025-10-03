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
BASE_URL = "http://www.ladymax.cn/"
MAX_ITEMS = 21
REQUEST_TIMEOUT = 20
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
    # Try with better headers to avoid anti-scraping blocks
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }

    session = requests.Session()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(BASE_URL, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
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

    # Look for news items in the main list div
    list_div = soup.find("div", {"id": "list"})
    if list_div:
        # Find all news items within div.i elements
        for item in list_div.find_all("div", class_="i"):
            # Get the link from the title link (class="tt")
            title_link = item.find("a", class_="tt")
            if not title_link:
                continue

            href = (title_link.get("href") or "").strip()

            # Extract title text (removing the metadata)
            full_text = title_link.get_text(" ", strip=True)
            # Split by the date pattern to get just the title
            if " / " in full_text:
                parts = full_text.split(" / ")
                if len(parts) >= 2:
                    title = " ".join(parts[1:]).strip()
                    # Extract date from the span.pubdate if it exists
                    date_span = title_link.find("span", class_="pubdate")
                    published = _normalise_datetime(date_span.get_text(strip=True)) if date_span else ""
                else:
                    title = full_text
                    published = ""
            else:
                title = full_text
                published = ""

            if not href or not title:
                continue
            if href.startswith("javascript") or href.startswith("#"):
                continue

            absolute_url = urljoin(BASE_URL, href)
            if absolute_url in seen_urls:
                continue

            seen_urls.add(absolute_url)

            # Try to get category from the span in the image link
            category = "资讯"
            img_link = item.find("a", class_="p")
            if img_link:
                cat_span = img_link.find("span")
                if cat_span:
                    category = cat_span.get_text(strip=True)

            results.append(
                {
                    "title": title.strip(),
                    "url": absolute_url,
                    "summary": "",  # No summary in this format
                    "published": published,
                    "category": category,
                }
            )

            if len(results) >= max_items:
                return results

    # Fallback to hotlink box for additional items if needed
    if len(results) < max_items:
        hotlink_div = soup.find("div", {"id": "hotlinkbox"})
        if hotlink_div:
            for link in hotlink_div.find_all("a", href=True):
                href = link.get("href", "").strip()
                title = link.get_text(" ", strip=True)

                if not href or not title:
                    continue
                if href.startswith("javascript") or href.startswith("#"):
                    continue

                absolute_url = urljoin(BASE_URL, href)
                if absolute_url in seen_urls:
                    continue

                seen_urls.add(absolute_url)

                results.append(
                    {
                        "title": title.strip(),
                        "url": absolute_url,
                        "summary": "",
                        "published": "",
                        "category": _guess_category_from_url(absolute_url),
                    }
                )

                if len(results) >= max_items:
                    break

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
