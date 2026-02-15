"""Fetch regulatory announcements from Chinese government agencies (CSRC, CAC, SAMR)."""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import re

import requests

from collectors.common import base_headers, schema, translate_text, write_with_history

OUT = "docs/data/gov_regulatory.json"
HISTORY = "docs/data/history/gov_regulatory.json"
REQUEST_TIMEOUT = 15

# Regulatory agency sources
SOURCES = [
    {
        "name": "CSRC",
        "name_zh": "证监会",
        "url": "http://www.csrc.gov.cn/csrc/c100028/common_list.shtml",
        "api_url": "http://www.csrc.gov.cn/searchList/a]2420a1acf6964016b05498e9f498e186",
        "description": "China Securities Regulatory Commission",
    },
    {
        "name": "CAC",
        "name_zh": "网信办",
        "url": "http://www.cac.gov.cn/index.htm",
        "description": "Cyberspace Administration of China",
    },
    {
        "name": "SAMR",
        "name_zh": "市场监管总局",
        "url": "https://www.samr.gov.cn/xw/",
        "description": "State Administration for Market Regulation",
    },
]


def scrape_csrc():
    """Scrape CSRC announcements."""
    items = []
    try:
        resp = requests.get(
            "http://www.csrc.gov.cn/csrc/c100028/common_list.shtml",
            headers=base_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            resp.encoding = "utf-8"
            # Extract announcement titles and dates
            pattern = r'<a[^>]*href="([^"]*)"[^>]*title="([^"]*)"'
            matches = re.findall(pattern, resp.text)
            for href, title in matches[:8]:
                if not title.strip():
                    continue
                url = href if href.startswith("http") else f"http://www.csrc.gov.cn{href}"
                translation = translate_text(title)
                items.append({
                    "title": title.strip(),
                    "value": "",
                    "url": url,
                    "extra": {
                        "agency": "CSRC",
                        "agency_zh": "证监会",
                        "translation": translation,
                    },
                })
    except Exception:
        pass
    return items


def scrape_cac():
    """Scrape CAC announcements."""
    items = []
    try:
        resp = requests.get(
            "http://www.cac.gov.cn/index.htm",
            headers=base_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            resp.encoding = "utf-8"
            pattern = r'<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, resp.text)
            seen = set()
            for href, title in matches:
                title = title.strip()
                if not title or len(title) < 8 or title in seen:
                    continue
                # Filter for news-like content
                if any(c in title for c in ["通知", "公告", "意见", "规定", "办法", "条例", "政策", "发布", "会议"]):
                    seen.add(title)
                    url = href if href.startswith("http") else f"http://www.cac.gov.cn{href}"
                    translation = translate_text(title)
                    items.append({
                        "title": title,
                        "value": "",
                        "url": url,
                        "extra": {
                            "agency": "CAC",
                            "agency_zh": "网信办",
                            "translation": translation,
                        },
                    })
                    if len(items) >= 5:
                        break
    except Exception:
        pass
    return items


def scrape_samr():
    """Scrape SAMR news."""
    items = []
    try:
        resp = requests.get(
            "https://www.samr.gov.cn/xw/zj/",
            headers=base_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            resp.encoding = "utf-8"
            pattern = r'<a[^>]*href="([^"]*)"[^>]*title="([^"]*)"'
            matches = re.findall(pattern, resp.text)
            for href, title in matches[:5]:
                if not title.strip():
                    continue
                url = href if href.startswith("http") else f"https://www.samr.gov.cn{href}"
                translation = translate_text(title)
                items.append({
                    "title": title.strip(),
                    "value": "",
                    "url": url,
                    "extra": {
                        "agency": "SAMR",
                        "agency_zh": "市场监管总局",
                        "translation": translation,
                    },
                })
    except Exception:
        pass
    return items


def main() -> None:
    items = []
    items.extend(scrape_csrc())
    items.extend(scrape_cac())
    items.extend(scrape_samr())

    if not items:
        # Provide at least placeholder entries
        for src in SOURCES:
            items.append({
                "title": f"{src['name_zh']} — 暂无最新公告",
                "value": "",
                "url": src["url"],
                "extra": {
                    "agency": src["name"],
                    "agency_zh": src["name_zh"],
                    "translation": f"{src['name']} — No recent announcements",
                    "stale": True,
                },
            })

    agencies = list({item.get("extra", {}).get("agency", "") for item in items if item.get("extra", {}).get("agency")})
    source = f"Gov Regulatory ({', '.join(sorted(agencies))})" if agencies else "Gov Regulatory"
    write_with_history(OUT, HISTORY, schema(source=source, items=items), min_items=1)


if __name__ == "__main__":
    main()
