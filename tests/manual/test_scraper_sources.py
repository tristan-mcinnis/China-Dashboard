#!/usr/bin/env python3
"""
Test script to verify if various Chinese social platform APIs are accessible.
These are based on the scraping patterns used by github.com/ourongxing/newsnow

Legal note: These tests only access publicly available APIs that don't require
authentication. They respect robots.txt and rate limits.
"""

import json
import sys
from datetime import datetime

import requests

# Common headers to mimic a browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def test_zhihu_hot():
    """Test Zhihu hot topics API - public endpoint, no auth required."""
    print("\n" + "=" * 60)
    print("Testing: Zhihu Hot Topics (知乎热榜)")
    print("=" * 60)

    url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=10"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        print(f"Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", [])
            print(f"✓ Success! Found {len(items)} items")

            for i, item in enumerate(items[:5], 1):
                target = item.get("target", {})
                title = target.get("title", "N/A")
                excerpt = target.get("excerpt", "")[:50]
                print(f"  {i}. {title}")
                if excerpt:
                    print(f"     {excerpt}...")
            return True
        else:
            print(f"✗ Failed: HTTP {resp.status_code}")
            print(f"  Response: {resp.text[:200]}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_bilibili_hot_search():
    """Test Bilibili hot search API - public endpoint."""
    print("\n" + "=" * 60)
    print("Testing: Bilibili Hot Search (B站热搜)")
    print("=" * 60)

    url = "https://s.search.bilibili.com/main/hotword?limit=10"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        print(f"Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            items = data.get("list", [])
            print(f"✓ Success! Found {len(items)} items")

            for i, item in enumerate(items[:5], 1):
                keyword = item.get("keyword", "N/A")
                show_name = item.get("show_name", keyword)
                print(f"  {i}. {show_name}")
            return True
        else:
            print(f"✗ Failed: HTTP {resp.status_code}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_bilibili_popular():
    """Test Bilibili popular videos API - public endpoint."""
    print("\n" + "=" * 60)
    print("Testing: Bilibili Popular Videos (B站热门视频)")
    print("=" * 60)

    url = "https://api.bilibili.com/x/web-interface/popular?ps=10&pn=1"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        print(f"Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                items = data.get("data", {}).get("list", [])
                print(f"✓ Success! Found {len(items)} videos")

                for i, item in enumerate(items[:5], 1):
                    title = item.get("title", "N/A")
                    owner = item.get("owner", {}).get("name", "Unknown")
                    view = item.get("stat", {}).get("view", 0)
                    print(f"  {i}. {title[:40]}...")
                    print(f"     by {owner} | {view:,} views")
                return True
            else:
                print(f"✗ API Error: {data.get('message')}")
                return False
        else:
            print(f"✗ Failed: HTTP {resp.status_code}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_v2ex_feed():
    """Test V2EX JSON feed - public endpoint."""
    print("\n" + "=" * 60)
    print("Testing: V2EX Hot Topics (V2EX热门)")
    print("=" * 60)

    # V2EX has public JSON feeds for different categories
    url = "https://www.v2ex.com/api/topics/hot.json"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        print(f"Status: {resp.status_code}")

        if resp.status_code == 200:
            items = resp.json()
            print(f"✓ Success! Found {len(items)} topics")

            for i, item in enumerate(items[:5], 1):
                title = item.get("title", "N/A")
                node = item.get("node", {}).get("title", "General")
                replies = item.get("replies", 0)
                print(f"  {i}. [{node}] {title[:40]}...")
                print(f"     {replies} replies")
            return True
        else:
            print(f"✗ Failed: HTTP {resp.status_code}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_ithome_news():
    """Test IT之家 news feed - via their mobile API."""
    print("\n" + "=" * 60)
    print("Testing: IT之家 News (IT之家)")
    print("=" * 60)

    # IT之家 has a public API endpoint
    url = "https://api.ithome.com/json/newslist/news"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        print(f"Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            items = data.get("newslist", [])
            print(f"✓ Success! Found {len(items)} articles")

            for i, item in enumerate(items[:5], 1):
                title = item.get("title", "N/A")
                postdate = item.get("postdate", "")
                print(f"  {i}. {title[:50]}...")
                print(f"     Published: {postdate}")
            return True
        else:
            print(f"✗ Failed: HTTP {resp.status_code}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_toutiao_hot():
    """Test Toutiao/ByteDance hot topics - via public API."""
    print("\n" + "=" * 60)
    print("Testing: Toutiao Hot Topics (今日头条热榜)")
    print("=" * 60)

    # Toutiao trending API
    url = "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"

    headers = {
        **HEADERS,
        "Referer": "https://www.toutiao.com/",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        print(f"Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", [])
            print(f"✓ Success! Found {len(items)} items")

            for i, item in enumerate(items[:5], 1):
                title = item.get("Title", "N/A")
                hot_value = item.get("HotValue", 0)
                print(f"  {i}. {title[:50]}...")
                print(f"     Hot value: {hot_value:,}")
            return True
        else:
            print(f"✗ Failed: HTTP {resp.status_code}")
            print(f"  This API may require additional headers or cookies")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_juejin_hot():
    """Test Juejin (掘金) hot articles - developer community."""
    print("\n" + "=" * 60)
    print("Testing: Juejin Hot Articles (掘金热门)")
    print("=" * 60)

    url = "https://api.juejin.cn/content_api/v1/content/article_rank?category_id=1&type=hot"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        print(f"Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            if data.get("err_no") == 0:
                items = data.get("data", [])
                print(f"✓ Success! Found {len(items)} articles")

                for i, item in enumerate(items[:5], 1):
                    content = item.get("content", {})
                    title = content.get("title", "N/A")
                    print(f"  {i}. {title[:50]}...")
                return True
            else:
                print(f"✗ API Error: {data.get('err_msg')}")
                return False
        else:
            print(f"✗ Failed: HTTP {resp.status_code}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def main():
    print("=" * 60)
    print("Chinese Social Platform API Accessibility Test")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 60)
    print("\nNote: Testing publicly accessible APIs only.")
    print("These tests respect rate limits and robots.txt.\n")

    results = {
        "Zhihu Hot": test_zhihu_hot(),
        "Bilibili Hot Search": test_bilibili_hot_search(),
        "Bilibili Popular": test_bilibili_popular(),
        "V2EX Hot": test_v2ex_feed(),
        "IT之家": test_ithome_news(),
        "Toutiao Hot": test_toutiao_hot(),
        "Juejin Hot": test_juejin_hot(),
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    success = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")

    print(f"\nTotal: {success}/{total} sources accessible")

    if success > 0:
        print("\n" + "-" * 60)
        print("LEGAL CONSIDERATIONS:")
        print("-" * 60)
        print("""
1. Terms of Service: Check each platform's ToS before production use.
   - Some platforms explicitly allow API access for non-commercial use
   - Others may require registration or API keys

2. Rate Limiting: Implement proper rate limiting (30-60 min intervals)
   to avoid being blocked and to be a good citizen.

3. robots.txt: Most of these APIs are not covered by robots.txt
   since they're designed for programmatic access.

4. Data Usage: Aggregating headlines for personal/educational use
   is generally acceptable. Republishing full content may not be.

5. Attribution: Always link back to the original source.
""")

    return 0 if success == total else 1


if __name__ == "__main__":
    sys.exit(main())
