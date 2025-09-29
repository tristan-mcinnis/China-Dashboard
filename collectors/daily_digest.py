#!/usr/bin/env python3
"""
Daily Digest Generator - Creates sense-making summaries at key times
Runs at: 7:00, 12:00, 19:00, 23:00 Beijing Time
"""

import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from collections import defaultdict

# Add parent directory to import common utilities
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.common import schema, write_json, translate_text

# Beijing timezone
BEIJING_TZ = timezone(timedelta(hours=8))

# Output paths
DIGEST_OUT = "docs/data/daily_digest.json"
DIGEST_ARCHIVE_DIR = "docs/data/digest_archive"

# Digest schedule (Beijing time)
DIGEST_TIMES = {
    "morning": 7,     # 7:00 - Morning briefing
    "noon": 12,       # 12:00 - Midday update
    "evening": 19,    # 19:00 - Evening digest
    "final": 23       # 23:00 - Day's complete summary
}

# Platform weights for importance scoring
PLATFORM_WEIGHTS = {
    'xinhua_news': 4.0,      # Official news highest weight
    'baidu_top': 3.0,        # Search trends
    'weibo_hot': 2.5,        # Social media virality
    'tencent_wechat_hot': 2.0,  # WeChat ecosystem
    'thepaper_news': 1.5,    # Quality journalism
    'ladymax_news': 1.0      # Niche/lifestyle
}

def get_current_digest_type():
    """Determine which digest type should run based on current Beijing time"""
    now_beijing = datetime.now(BEIJING_TZ)
    current_hour = now_beijing.hour
    current_minute = now_beijing.minute

    # Check if we're within 30 minutes of a digest time
    for digest_name, target_hour in DIGEST_TIMES.items():
        if current_hour == target_hour and current_minute < 30:
            return digest_name

    return None

def should_generate_digest():
    """Check if digest should be generated now"""
    digest_type = get_current_digest_type()
    if digest_type:
        print(f"Generating {digest_type} digest")
        return True
    return False

def load_all_current_data():
    """Load all platform data from latest snapshots"""
    sources = {
        'baidu_top': 'docs/data/baidu_top.json',
        'weibo_hot': 'docs/data/weibo_hot.json',
        'xinhua_news': 'docs/data/xinhua_news.json',
        'tencent_wechat_hot': 'docs/data/tencent_wechat_hot.json',
        'thepaper_news': 'docs/data/thepaper_news.json',
        'ladymax_news': 'docs/data/ladymax_news.json'
    }

    all_items = []
    for platform, path in sources.items():
        if not os.path.exists(path):
            print(f"Warning: {path} not found, skipping")
            continue

        try:
            with open(path) as f:
                data = json.load(f)
                # Take top 20 items from each source for digest
                for idx, item in enumerate(data.get('items', [])[:20]):
                    all_items.append({
                        'platform': platform,
                        'rank': idx + 1,
                        'title': item.get('title', ''),
                        'url': item.get('url'),
                        'translation': item.get('extra', {}).get('translation', ''),
                        'raw_item': item
                    })
        except Exception as e:
            print(f"Error loading {path}: {e}")

    return all_items

def extract_keywords(title):
    """Extract key terms from Chinese title for matching"""
    if not title or not isinstance(title, str):
        return ""

    # Remove ranking numbers like "1. " or "1、"
    clean = re.sub(r'^\d+[\.\、]\s*', '', title)
    # Remove brackets and quotes
    clean = re.sub(r'[【】《》「」（）\(\)\[\]""]', ' ', clean)
    # Remove common suffix like "热" (hot)
    clean = re.sub(r'[＃#]\S+', '', clean)  # Remove hashtags
    clean = re.sub(r'\s*热$', '', clean)
    return clean.strip()

def find_similar_stories(all_items):
    """Group similar stories across platforms"""
    clusters = []
    processed = set()

    # Limit items to prevent O(n²) performance issues
    MAX_ITEMS = 500
    if len(all_items) > MAX_ITEMS:
        print(f"Warning: Limiting clustering to {MAX_ITEMS} items for performance")
        all_items = all_items[:MAX_ITEMS]

    for i, item in enumerate(all_items):
        if i in processed or not item:
            continue

        # Defensive null checks
        item_title = item.get('title', '')
        item_platform = item.get('platform', 'unknown')

        cluster = {
            'items': [item],
            'platforms': {item_platform},
            'keywords': extract_keywords(item_title),
            'titles': [item_title] if item_title else []
        }

        # Find similar stories
        for j, other in enumerate(all_items):
            if j <= i or j in processed or not other:
                continue

            # Defensive null checks
            other_title = other.get('title', '')
            other_platform = other.get('platform', 'unknown')

            # Extract keywords for comparison
            other_keywords = extract_keywords(other_title)

            # Skip if either has no keywords
            if not cluster['keywords'] or not other_keywords:
                continue

            # Calculate similarity
            try:
                similarity = SequenceMatcher(None,
                    cluster['keywords'],
                    other_keywords
                ).ratio()
            except Exception:
                similarity = 0

            # Check for key term overlap
            key_terms_1 = set(cluster['keywords'].split()) if cluster['keywords'] else set()
            key_terms_2 = set(other_keywords.split()) if other_keywords else set()

            # Need at least 2 common terms or high similarity
            common_terms = len(key_terms_1 & key_terms_2)

            if similarity > 0.5 or common_terms >= 2:
                cluster['items'].append(other)
                cluster['platforms'].add(other_platform)
                if other_title:
                    cluster['titles'].append(other_title)
                processed.add(j)

        clusters.append(cluster)
        processed.add(i)

    return clusters

def calculate_cluster_weight(cluster):
    """Calculate importance weight for a story cluster"""
    weight = 0
    for item in cluster['items']:
        base_weight = PLATFORM_WEIGHTS.get(item['platform'], 1.0)
        # Exponential decay for lower rankings
        rank_penalty = 0.9 ** (item['rank'] - 1)
        weight += base_weight * rank_penalty

    # Bonus for multi-platform coverage
    platform_count = len(cluster['platforms'])
    if platform_count > 1:
        platform_bonus = platform_count ** 1.5
        weight *= platform_bonus

    return weight

def categorize_story(cluster):
    """Determine story category based on keywords"""
    if not cluster or not cluster.get('titles'):
        return 'general'

    # Safely join titles
    titles = cluster.get('titles', [])
    title_text = ' '.join(str(t) for t in titles if t).lower()

    categories = [
        ('business', ['经济', '金融', '公司', '集团', '股', '市场', '消费', '债务', '银行']),
        ('military', ['军', '舰', '国防', '武器', '海军', '航母', '导弹', '战']),
        ('technology', ['科技', '技术', '创新', '研发', '人工智能', 'ai', '芯片', '数字']),
        ('politics', ['政治', '主席', '习近平', '政府', '党', '领导', '政策', '外交']),
        ('weather', ['台风', '天气', '暴雨', '气象', '洪水', '地震', '灾害']),
        ('social', ['教育', '医疗', '就业', '房', '民生', '社会', '疫情']),
        ('international', ['美国', '欧洲', '日本', '朝鲜', '俄罗斯', '国际', '全球'])
    ]

    for cat_name, keywords in categories:
        if any(kw in title_text for kw in keywords):
            return cat_name

    return 'general'

def generate_story_summary(cluster):
    """Generate bilingual AI summary for cross-platform stories"""
    # If no API key, return None
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"en": None, "zh": None}

    platforms = ', '.join(sorted(cluster['platforms']))
    headlines = cluster['titles'][:3]

    # Gather all available descriptions
    descriptions = []
    for item in cluster['items']:
        if item.get('raw_item', {}).get('extra', {}).get('description'):
            descriptions.append(item['raw_item']['extra']['description'])

    context = f"\nDescriptions:\n{chr(10).join(f'- {d}' for d in descriptions[:2])}" if descriptions else ""

    # For now, use simpler summaries since we don't have full OpenAI integration
    # This would need a proper OpenAI call with higher token limits for full summaries
    try:
        # Get the main headline
        main_headline = headlines[0] if headlines else ""

        # Try to translate just the main headline for a basic English version
        from collectors.common import translate_text
        english_headline = translate_text(main_headline) if main_headline else ""

        # Create basic summaries based on available data
        platform_count = len(cluster['platforms'])
        category = categorize_story(cluster)

        # Build a simple English summary
        en_summary = f"This story about '{english_headline}' is trending across {platform_count} major Chinese platforms. "
        en_summary += f"The high cross-platform coverage suggests significant public interest in this {category} news story."

        # Build a simple Chinese summary
        zh_summary = f"此新闻在{platform_count}个主要平台上热门。"
        zh_summary += f"跨平台的高覆盖率表明公众对这条{category}新闻高度关注。"

        return {
            "en": en_summary,
            "zh": zh_summary
        }

    except Exception as e:
        print(f"Error generating summary: {e}")
        # Return the fallback that we're seeing in the screenshot
        return {"en": None, "zh": None}

def generate_digest():
    """Generate the daily digest"""
    digest_type = get_current_digest_type()
    if not digest_type:
        print("Not a scheduled digest time, skipping")
        return

    print(f"\nGenerating {digest_type} digest at {datetime.now(BEIJING_TZ).strftime('%Y-%m-%d %H:%M')} Beijing time")

    # Load and cluster data
    all_items = load_all_current_data()
    if not all_items:
        print("No data available for digest")
        return

    clusters = find_similar_stories(all_items)

    # Add weights and sort
    for cluster in clusters:
        cluster['weight'] = calculate_cluster_weight(cluster)
    clusters.sort(key=lambda x: x['weight'], reverse=True)

    # Separate multi-platform and single-platform
    multi_platform = [c for c in clusters if len(c['platforms']) > 1]
    single_platform = [c for c in clusters if len(c['platforms']) == 1]

    now_beijing = datetime.now(BEIJING_TZ)

    # Create digest
    digest = {
        "digest_type": digest_type,
        "as_of": now_beijing.isoformat(),
        "date": now_beijing.strftime("%Y-%m-%d"),
        "time_label": f"{digest_type.title()} Digest",
        "beijing_time": now_beijing.strftime("%H:%M"),
        "top_stories": [],
        "metrics": {
            "total_stories_analyzed": len(all_items),
            "cross_platform_stories": len(multi_platform),
            "unique_stories": len(single_platform),
            "platforms_covered": len(set(item['platform'] for item in all_items))
        }
    }

    # Add top 5 cross-platform stories
    for idx, cluster in enumerate(multi_platform[:5], 1):
        # Get English title from translation if available
        english_title = "Story requires translation"
        for item in cluster['items']:
            if item.get('translation'):
                # Clean up the translation
                trans = item['translation']
                # Remove ellipsis and extra dots
                trans = trans.replace('...', '').strip()
                if trans:
                    english_title = trans
                    break

        # Generate bilingual summary if API key available
        summaries = generate_story_summary(cluster)
        if not summaries["en"] and not summaries["zh"]:
            # Provide basic descriptions if no API key
            category_zh = {
                'business': '商业',
                'military': '军事',
                'politics': '政治',
                'technology': '科技',
                'weather': '天气',
                'social': '社会',
                'international': '国际',
                'general': '综合'
            }
            cat = categorize_story(cluster)
            summaries = {
                "en": f"This story is trending on {len(cluster['platforms'])} platforms with high engagement. It appears to be related to {cat} news.",
                "zh": f"此新闻在{len(cluster['platforms'])}个平台上热门，属于{category_zh.get(cat, '综合')}类新闻。"
            }

        story = {
            "rank": idx,
            "weight": round(cluster['weight'], 2),
            "platforms": sorted(list(cluster['platforms'])),
            "platform_count": len(cluster['platforms']),
            "primary_title": cluster['titles'][0],
            "english_title": english_title[:100],  # Truncate long titles
            "summary": summaries["en"],
            "summary_zh": summaries["zh"],
            "category": categorize_story(cluster),
            "appearances": [
                {
                    "platform": item['platform'],
                    "rank": item['rank'],
                }
                for item in sorted(cluster['items'], key=lambda x: x['rank'])[:5]
            ]
        }

        digest["top_stories"].append(story)

    # Platform exclusive highlights (top story from each single-platform)
    platform_exclusives = {}
    for platform in PLATFORM_WEIGHTS.keys():
        exclusive = [c for c in single_platform if platform in c['platforms']]
        if exclusive and exclusive[0]['weight'] > 2.0:  # Only significant stories
            platform_exclusives[platform] = {
                "title": exclusive[0]['titles'][0][:60],
                "weight": round(exclusive[0]['weight'], 2)
            }

    if platform_exclusives:
        digest["platform_exclusives"] = platform_exclusives

    # Save main digest
    write_json(DIGEST_OUT, digest)
    print(f"✅ Digest saved to {DIGEST_OUT}")

    # Archive digest
    archive_digest(digest, digest_type, now_beijing)

    return digest

def archive_digest(digest, digest_type, timestamp):
    """Archive digest for historical tracking"""
    date_str = timestamp.strftime("%Y-%m-%d")
    archive_dir = os.path.join(DIGEST_ARCHIVE_DIR, date_str)
    os.makedirs(archive_dir, exist_ok=True)

    archive_path = os.path.join(archive_dir, f"{digest_type}.json")
    write_json(archive_path, digest)
    print(f"📁 Archived to {archive_path}")

def main():
    """Main entry point"""
    # Check if we should generate digest
    if not should_generate_digest():
        current_time = datetime.now(BEIJING_TZ).strftime("%H:%M")
        print(f"Current Beijing time: {current_time}")
        print(f"Digest times: {', '.join(f'{k}={v:02d}:00' for k, v in DIGEST_TIMES.items())}")
        print("Not a scheduled digest time, skipping")
        return

    # Generate the digest
    digest = generate_digest()

    if digest:
        print("\n" + "="*60)
        print(f"📊 {digest['time_label']} Generated Successfully")
        print(f"Top story: {digest['top_stories'][0]['english_title'] if digest['top_stories'] else 'None'}")
        print(f"Cross-platform stories: {digest['metrics']['cross_platform_stories']}")
        print("="*60)

if __name__ == "__main__":
    main()