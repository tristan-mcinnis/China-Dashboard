#!/usr/bin/env python3
"""
Enhanced Daily Digest - Fetches actual article content for real summarization
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup
import html2text

# Add parent for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.common import translate_text
from collectors.daily_digest import (
    load_all_current_data,
    find_similar_stories,
    calculate_cluster_weight,
    categorize_story,
    BEIJING_TZ,
    DIGEST_TIMES,
    get_current_digest_type
)

def fetch_article_safely(url, timeout=10):
    """
    Simplified article fetcher - gets whatever content is available
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

        response = requests.get(url, headers=headers, timeout=timeout)
        response.encoding = response.apparent_encoding or 'utf-8'

        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer']):
            element.decompose()

        # Try to find article content
        article_text = ""

        # Strategy 1: Look for main content areas
        content_areas = soup.find_all(['article', 'main',
                                      'div'],
                                      class_=lambda x: x and ('content' in x.lower() or
                                                             'article' in x.lower() or
                                                             'text' in x.lower()))

        if content_areas:
            for area in content_areas[:2]:  # First 2 matching areas
                text = area.get_text(separator='\n', strip=True)
                if len(text) > len(article_text):
                    article_text = text

        # Strategy 2: Get all paragraphs if no content area found
        if len(article_text) < 200:
            paragraphs = soup.find_all('p')
            if paragraphs:
                article_text = '\n\n'.join(p.get_text(strip=True) for p in paragraphs
                                         if len(p.get_text(strip=True)) > 30)

        # Strategy 3: Just get all text if still nothing
        if len(article_text) < 200:
            article_text = soup.get_text(separator='\n', strip=True)

        # Clean up
        article_text = '\n'.join(line.strip() for line in article_text.split('\n')
                                if line.strip() and len(line.strip()) > 20)

        return {
            'success': True,
            'content': article_text[:3000],  # Limit for API
            'length': len(article_text)
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'content': ''
        }

def generate_enhanced_summary(cluster):
    """
    Generate summary using actual article content
    """
    if not os.getenv("OPENAI_API_KEY"):
        return None

    print(f"  Generating enhanced summary for: {cluster['titles'][0][:50]}...")

    # Collect all available content
    all_content = []
    article_fetched = False

    # Try to fetch actual article content from URLs
    for item in cluster['items'][:2]:  # Try first 2 URLs
        url = item.get('url', '')

        # Skip search result pages
        if url and not ('baidu.com/s' in url or 'weibo.cn/search' in url):
            print(f"    Fetching article from: {url[:60]}...")
            result = fetch_article_safely(url, timeout=5)

            if result['success'] and result.get('content'):
                all_content.append(f"Article content:\n{result['content']}")
                article_fetched = True
                print(f"    ✓ Fetched {result['length']} chars")
                break  # One good article is enough

    # Add descriptions and summaries as fallback
    if not article_fetched:
        print("    Using descriptions/summaries as fallback")
        for item in cluster['items']:
            if item.get('raw_item'):
                extra = item['raw_item'].get('extra', {})
                if extra.get('description'):
                    all_content.append(f"Description: {extra['description']}")
                if extra.get('summary'):
                    all_content.append(f"Summary: {extra['summary']}")

    # Build comprehensive prompt
    content_text = '\n\n'.join(all_content) if all_content else "No detailed content available"

    prompt = f"""Analyze this trending Chinese news story:

Headlines from {len(cluster['platforms'])} platforms:
{chr(10).join(f'- {t}' for t in cluster['titles'][:3])}

{content_text[:2500]}  # Limit for API

Based on the actual article content above, write a 2-paragraph English summary (150 words):
1. What specifically happened with key details and facts
2. Context, significance and implications

Be specific and factual, citing details from the article content."""

    try:
        summary = translate_text(prompt)
        return summary if summary else None
    except Exception as e:
        print(f"    Error generating summary: {e}")
        return None

def test_enhanced_digest():
    """Test the enhanced digest with article fetching"""

    print("="*80)
    print("ENHANCED DIGEST TEST - With Real Article Content")
    print("="*80)

    # Load and cluster data
    all_items = load_all_current_data()
    clusters = find_similar_stories(all_items)

    # Add weights and sort
    for cluster in clusters:
        cluster['weight'] = calculate_cluster_weight(cluster)
    clusters.sort(key=lambda x: x['weight'], reverse=True)

    # Get top multi-platform story
    multi_platform = [c for c in clusters if len(c['platforms']) > 1]

    if not multi_platform:
        print("No multi-platform stories found")
        return

    # Test with top story
    top_story = multi_platform[0]

    print(f"\n📰 TOP STORY:")
    print(f"Weight: {top_story['weight']:.2f}")
    print(f"Platforms: {', '.join(top_story['platforms'])}")
    print(f"Primary headline: {top_story['titles'][0]}")

    # Check if we have URLs
    urls = [item.get('url', '') for item in top_story['items'] if item.get('url')]
    print(f"\nAvailable URLs: {len(urls)}")
    for url in urls[:3]:
        print(f"  - {url[:80]}...")

    # Try basic content extraction
    print("\n🔍 Attempting content extraction...")

    for item in top_story['items'][:2]:
        url = item.get('url', '')
        if url and not ('baidu.com/s' in url or 'weibo.cn/search' in url):
            print(f"\nFetching: {url[:60]}...")

            result = fetch_article_safely(url)

            if result['success']:
                print(f"✅ Success! Got {result['length']} characters")
                print("\nContent preview:")
                print("-"*40)
                print(result['content'][:500])
                print("-"*40)

                # Show what we'd send to GPT
                print("\n📝 Enhanced prompt for GPT:")
                print("="*60)

                prompt = f"""Analyze this trending Chinese news story:

Headlines from {len(top_story['platforms'])} platforms:
{chr(10).join(f'- {t}' for t in top_story['titles'][:3])}

Article content:
{result['content'][:1000]}...

Based on the actual article content above, write a 2-paragraph English summary..."""

                print(prompt[:600])
                print("\n✨ Now GPT has REAL article content to work with!")
                break
            else:
                print(f"❌ Failed: {result.get('error', 'Unknown')}")

    # Test summary generation if API key available
    if os.getenv("OPENAI_API_KEY"):
        print("\n🤖 Generating AI summary with real content...")
        summary = generate_enhanced_summary(top_story)
        if summary:
            print("\nGenerated summary:")
            print("-"*40)
            print(summary)
        else:
            print("Failed to generate summary")
    else:
        print("\n⚠️  OPENAI_API_KEY not set - would generate summary here")

if __name__ == "__main__":
    test_enhanced_digest()