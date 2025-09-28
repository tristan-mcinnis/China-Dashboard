#!/usr/bin/env python3
"""
Article Fetcher - Gets full article content for proper summarization
"""

import requests
from bs4 import BeautifulSoup
import html2text
import re
from urllib.parse import urlparse
import time
import hashlib
import os
import json

# Cache directory for fetched articles
CACHE_DIR = "docs/data/article_cache"

def get_cache_key(url):
    """Generate cache key for URL"""
    return hashlib.md5(url.encode()).hexdigest()

def load_from_cache(url, max_age_hours=24):
    """Load article from cache if fresh enough"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_key = get_cache_key(url)
    cache_path = os.path.join(CACHE_DIR, f"{cache_key}.json")

    if os.path.exists(cache_path):
        # Check age
        cache_age = time.time() - os.path.getmtime(cache_path)
        if cache_age < (max_age_hours * 3600):
            with open(cache_path) as f:
                return json.load(f)
    return None

def save_to_cache(url, content):
    """Save article content to cache"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_key = get_cache_key(url)
    cache_path = os.path.join(CACHE_DIR, f"{cache_key}.json")

    cache_data = {
        "url": url,
        "fetched_at": time.time(),
        "content": content
    }

    with open(cache_path, 'w') as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)

def fetch_article_content(url, use_cache=True):
    """
    Fetch and extract main article content from URL
    Returns markdown-formatted article text
    """

    # Check cache first
    if use_cache:
        cached = load_from_cache(url)
        if cached:
            return cached.get('content', {})

    try:
        # Parse domain for site-specific handling
        domain = urlparse(url).netloc.lower()

        # Special handling for search result pages (not actual articles)
        if 'baidu.com/s' in url or 'weibo.cn/search' in url or 'google.com/rss' in url:
            # These are search/aggregation pages, not articles
            # We need to follow through to the actual article
            return fetch_search_result_article(url)

        # Standard article fetching
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = response.apparent_encoding or 'utf-8'
        html = response.text

        # Parse with BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        # Site-specific extraction
        content = extract_by_site(soup, domain, url)

        if content:
            # Convert to markdown
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = True
            h.body_width = 0  # Don't wrap lines

            markdown_content = h.handle(str(content))

            # Clean up markdown
            markdown_content = clean_markdown(markdown_content)

            result = {
                'url': url,
                'domain': domain,
                'title': extract_title(soup),
                'content': markdown_content,
                'length': len(markdown_content),
                'success': True
            }

            # Cache the result
            if use_cache:
                save_to_cache(url, result)

            return result

        else:
            return {
                'url': url,
                'domain': domain,
                'error': 'Could not extract article content',
                'success': False
            }

    except Exception as e:
        return {
            'url': url,
            'error': str(e),
            'success': False
        }

def fetch_search_result_article(search_url):
    """
    Handle search result pages by trying to get the first real article
    """
    domain = urlparse(search_url).netloc.lower()

    if 'baidu.com' in domain:
        # Baidu search results - try to get first result
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(search_url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find first organic result
            first_result = soup.find('div', {'id': '1'})  # Baidu numbers results
            if first_result:
                link = first_result.find('a')
                if link and link.get('href'):
                    # Baidu wraps links, need to extract real URL
                    real_url = extract_baidu_real_url(link['href'])
                    if real_url:
                        return fetch_article_content(real_url, use_cache=True)

            # Fallback: extract snippet text from search results
            snippets = []
            for i in range(1, 4):  # First 3 results
                result_div = soup.find('div', {'id': str(i)})
                if result_div:
                    text = result_div.get_text(strip=True)
                    snippets.append(text)

            if snippets:
                return {
                    'url': search_url,
                    'domain': 'baidu.com',
                    'content': '\n\n'.join(snippets),
                    'type': 'search_snippets',
                    'success': True
                }

        except:
            pass

    elif 'weibo.cn' in domain or 'm.weibo.cn' in domain:
        # Mobile Weibo - extract posts directly
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)'}
            response = requests.get(search_url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract weibo posts
            posts = soup.find_all('div', class_='card')[:5]  # First 5 posts
            content_parts = []

            for post in posts:
                text = post.get_text(strip=True)
                if text:
                    content_parts.append(text)

            if content_parts:
                return {
                    'url': search_url,
                    'domain': 'weibo.cn',
                    'content': '\n---\n'.join(content_parts),
                    'type': 'social_posts',
                    'success': True
                }
        except:
            pass

    return {
        'url': search_url,
        'error': 'Search page, not article',
        'success': False
    }

def extract_baidu_real_url(baidu_link):
    """Extract real URL from Baidu's wrapped link"""
    try:
        # Baidu uses a redirect, follow it
        response = requests.get(baidu_link, allow_redirects=False, timeout=5)
        if 'Location' in response.headers:
            return response.headers['Location']
    except:
        pass
    return None

def extract_by_site(soup, domain, url):
    """
    Site-specific content extraction strategies
    """

    # Remove script and style elements first
    for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
        element.decompose()

    # Common Chinese news sites
    if 'xinhuanet.com' in domain or 'news.cn' in domain:
        # Xinhua News
        article = soup.find('div', class_='articleText') or \
                 soup.find('div', class_='content') or \
                 soup.find('div', id='detail')
        return article

    elif 'thepaper.cn' in domain:
        # The Paper
        article = soup.find('div', class_='news_txt') or \
                 soup.find('div', class_='detail_content')
        return article

    elif 'weibo.com' in domain or 'weibo.cn' in domain:
        # Weibo - extract post content
        article = soup.find('div', class_='weibo-text') or \
                 soup.find('div', class_='detail_text')
        return article

    elif 'chinadaily.com.cn' in domain:
        # China Daily
        article = soup.find('div', id='Content') or \
                 soup.find('div', class_='article')
        return article

    elif 'peopledaily.com.cn' in domain or 'people.cn' in domain:
        # People's Daily
        article = soup.find('div', class_='rm_txt_con') or \
                 soup.find('div', class_='content')
        return article

    elif 'cctv.com' in domain or 'cntv.cn' in domain:
        # CCTV
        article = soup.find('div', class_='content_area') or \
                 soup.find('div', class_='text_area')
        return article

    elif 'caixin.com' in domain:
        # Caixin
        article = soup.find('div', id='the_content') or \
                 soup.find('div', class_='article-content')
        return article

    else:
        # Generic extraction for unknown sites
        # Try common article containers
        article = soup.find('article') or \
                 soup.find('div', class_=re.compile('article|content|entry|post|text')) or \
                 soup.find('div', id=re.compile('article|content|entry|post|text')) or \
                 soup.find('main')

        if not article:
            # Fallback: find largest text block
            article = find_largest_text_block(soup)

        return article

def find_largest_text_block(soup):
    """
    Find the largest continuous text block (likely the article)
    """
    max_length = 0
    best_element = None

    for element in soup.find_all(['div', 'section', 'article']):
        text = element.get_text(strip=True)
        # Must be substantial text, not navigation
        if len(text) > max_length and len(text) > 500:
            # Check it's not mostly links
            links_text = sum(len(a.get_text(strip=True)) for a in element.find_all('a'))
            if links_text < len(text) * 0.3:  # Less than 30% links
                max_length = len(text)
                best_element = element

    return best_element

def extract_title(soup):
    """Extract article title"""
    # Try OpenGraph title first (most reliable)
    og_title = soup.find('meta', property='og:title')
    if og_title and og_title.get('content'):
        return og_title['content']

    # Try standard title tag
    title_tag = soup.find('title')
    if title_tag:
        return title_tag.get_text(strip=True)

    # Try h1
    h1 = soup.find('h1')
    if h1:
        return h1.get_text(strip=True)

    return "No title found"

def clean_markdown(text):
    """Clean up converted markdown"""
    # Remove excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Remove excessive spaces
    text = re.sub(r' {2,}', ' ', text)

    # Remove navigation artifacts
    text = re.sub(r'(Share|Tweet|Email|Print|Subscribe|Advertisement)[\s\n]*', '', text, flags=re.IGNORECASE)

    # Remove common Chinese navigation text
    text = re.sub(r'(分享|转发|评论|点赞|订阅|返回|更多)[\s\n]*', '', text)

    # Limit to reasonable length for summarization (~ 2000 words)
    words = text.split()
    if len(words) > 2000:
        text = ' '.join(words[:2000]) + '\n\n[Article truncated for summarization]'

    return text.strip()

def test_fetcher():
    """Test the article fetcher with various URLs"""
    test_urls = [
        "https://www.thepaper.cn/newsDetail_forward_31683289",  # The Paper article
        "https://www.xinhuanet.com/politics/2024-09/article_123.htm",  # Xinhua (example)
        "https://www.baidu.com/s?wd=王健林被限制高消费",  # Baidu search
        "https://m.weibo.cn/search?containerid=100103type%3D1%26q%3D王健林",  # Weibo search
    ]

    for url in test_urls:
        print(f"\n{'='*60}")
        print(f"Testing: {url}")
        print('='*60)

        result = fetch_article_content(url)

        if result.get('success'):
            print(f"✅ Success!")
            print(f"Title: {result.get('title', 'N/A')}")
            print(f"Content length: {result.get('length', 0)} chars")
            print(f"First 500 chars of content:")
            print('-'*40)
            print(result.get('content', '')[:500])
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    test_fetcher()