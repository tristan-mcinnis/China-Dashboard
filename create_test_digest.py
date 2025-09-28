#!/usr/bin/env python3
"""
Create a test digest with proper mock summaries for local preview
"""

import json
from datetime import datetime

# Create a realistic digest with good summaries
test_digest = {
    "digest_type": "evening",
    "as_of": datetime.now().isoformat() + "+08:00",
    "date": datetime.now().strftime("%Y-%m-%d"),
    "time_label": "Evening Digest",
    "beijing_time": datetime.now().strftime("%H:%M"),
    "top_stories": [
        {
            "rank": 1,
            "weight": 36.37,
            "platforms": ["baidu_top", "tencent_wechat_hot", "weibo_hot"],
            "platform_count": 3,
            "primary_title": "王健林被限制高消费 涉及1.86亿执行案",
            "english_title": "Wang Jianlin Faces Consumption Restrictions in 186M Yuan Case",
            "summary": "Dalian Wanda Group and its founder Wang Jianlin have been placed under consumption restrictions following a court enforcement action involving 186 million yuan. The restrictions prohibit luxury spending including first-class travel, high-end hotels, private school tuition, and property purchases.\n\nThis development reflects ongoing challenges in China's property sector and signals continued deleveraging efforts. The move affects one of China's most prominent business figures and highlights the broader financial pressures facing major real estate developers amid tighter regulatory oversight.",
            "summary_zh": "大连万达集团及其创始人王健林因一起涉及1.86亿元人民币的法院强制执行案件被限制高消费。限制措施包括禁止乘坐飞机头等舱、入住高档酒店、子女就读私立学校及购买房产等奢侈性消费。\n\n这一事件反映了中国房地产行业持续面临的挑战，以及去杠杆化进程的持续推进。作为中国最知名的企业家之一，王健林受到的限制措施凸显了在监管收紧背景下，主要房地产开发商面临的更广泛的财务压力。",
            "category": "business",
            "appearances": [
                {"platform": "weibo_hot", "rank": 1},
                {"platform": "baidu_top", "rank": 2},
                {"platform": "tencent_wechat_hot", "rank": 2}
            ]
        },
        {
            "rank": 2,
            "weight": 14.14,
            "platforms": ["baidu_top", "tencent_wechat_hot"],
            "platform_count": 2,
            "primary_title": "石榴籽：习近平为何一再强调民族团结",
            "english_title": "Pomegranate Seeds: Xi's Metaphor for Ethnic Unity",
            "summary": "President Xi Jinping has repeatedly used the pomegranate seed metaphor to emphasize ethnic unity during Xinjiang's 70th anniversary celebrations. The imagery symbolizes how China's 56 ethnic groups should bind together tightly, just as pomegranate seeds cluster together.\n\nThis messaging underscores Beijing's focus on national cohesion and ethnic harmony policies, particularly in diverse border regions. The metaphor has become a central narrative in China's governance approach to minority areas and reflects broader efforts to strengthen national identity.",
            "summary_zh": "在新疆维吾尔自治区成立70周年之际，习近平主席再次使用石榴籽的比喻来强调民族团结。这一形象的比喻象征着中国56个民族应该像石榴籽一样紧紧抱在一起。\n\n这一表述凸显了北京对国家凝聚力和民族和谐政策的重视，特别是在多元化的边疆地区。石榴籽的比喻已成为中国少数民族地区治理方略的核心叙事，反映了加强国家认同的更广泛努力。",
            "category": "politics",
            "appearances": [
                {"platform": "baidu_top", "rank": 1},
                {"platform": "tencent_wechat_hot", "rank": 1}
            ]
        },
        {
            "rank": 3,
            "weight": 11.46,
            "platforms": ["baidu_top", "tencent_wechat_hot"],
            "platform_count": 2,
            "primary_title": "全球首例！中国航母福建舰电磁弹射创纪录",
            "english_title": "China's Fujian Carrier Sets Record with Electromagnetic Catapult",
            "summary": "China's newest aircraft carrier Fujian has achieved a historic milestone with successful electromagnetic catapult tests, becoming only the second nation after the United States to deploy this advanced technology. The breakthrough represents a leap from ski-jump to catapult launch capabilities in just over a decade.\n\nThis technological advancement positions China among elite naval powers and signals enhanced blue-water navy capabilities. Military analysts note this could reshape regional naval dynamics and demonstrates China's rapid progress in critical defense technologies, potentially altering the balance of power in the Indo-Pacific region.",
            "summary_zh": "中国最新航母福建舰成功完成电磁弹射测试，创造历史性里程碑，成为继美国之后全球第二个掌握这一先进技术的国家。这一突破标志着中国在短短十几年内实现了从滑跃起飞到弹射起飞的技术跨越。\n\n这一技术进步将中国置于精英海军强国之列，标志着蓝水海军能力的提升。军事分析人士指出，这可能重塑地区海军格局，展示了中国在关键国防技术方面的快速进步，可能改变印太地区的力量平衡。",
            "category": "military",
            "appearances": [
                {"platform": "baidu_top", "rank": 3},
                {"platform": "tencent_wechat_hot", "rank": 3}
            ]
        },
        {
            "rank": 4,
            "weight": 10.31,
            "platforms": ["baidu_top", "tencent_wechat_hot"],
            "platform_count": 2,
            "primary_title": "台风博罗依逼近 南方多省暴雨预警",
            "english_title": "Typhoon Bolaven Approaches with Severe Weather Warnings",
            "summary": "Typhoon Bolaven is approaching southern China with warnings of torrential rain and severe weather conditions across multiple provinces. Hainan, Guangdong, and Guangxi provinces are preparing for potential flooding with rainfall expected to exceed 250mm in some areas.\n\nAuthorities have issued emergency alerts and evacuation orders for coastal areas. The storm's path could affect millions and disrupt economic activity during the National Day holiday period. Emergency response teams are on standby as the typhoon is expected to make landfall within 48 hours.",
            "summary_zh": "台风博罗依正在逼近中国南部，多个省份发布暴雨和恶劣天气预警。海南、广东和广西等省份正在为可能的洪涝灾害做准备，部分地区降雨量预计将超过250毫米。\n\n当局已发布紧急警报并对沿海地区下达疏散令。台风路径可能影响数百万人，并在国庆假期期间扰乱经济活动。随着台风预计在48小时内登陆，应急响应团队已进入待命状态。",
            "category": "weather",
            "appearances": [
                {"platform": "baidu_top", "rank": 10},
                {"platform": "tencent_wechat_hot", "rank": 10}
            ]
        },
        {
            "rank": 5,
            "weight": 9.28,
            "platforms": ["baidu_top", "tencent_wechat_hot"],
            "platform_count": 2,
            "primary_title": "朝鲜宣布建党80周年大赦令",
            "english_title": "North Korea Announces Amnesty for 80th Party Anniversary",
            "summary": "North Korea has announced a general amnesty for convicted individuals to mark the 80th anniversary of the Workers' Party founding. The decree, issued by the Supreme People's Assembly, will result in the release or sentence reduction for thousands of prisoners.\n\nThis rare gesture comes amid ongoing economic challenges and international sanctions. Analysts suggest the move may be aimed at boosting domestic morale and demonstrating magnanimity ahead of the significant anniversary celebrations planned for October.",
            "summary_zh": "朝鲜宣布为纪念劳动党建党80周年实施大赦，对被判有罪人员给予特赦。最高人民会议发布的法令将导致数千名囚犯获释或减刑。\n\n这一罕见举措发生在持续的经济挑战和国际制裁背景下。分析人士认为，此举可能旨在提升国内士气，并在10月份计划举行的重要周年庆典前展示宽大姿态。",
            "category": "international",
            "appearances": [
                {"platform": "baidu_top", "rank": 5},
                {"platform": "tencent_wechat_hot", "rank": 5}
            ]
        }
    ],
    "metrics": {
        "total_stories_analyzed": 90,
        "cross_platform_stories": 10,
        "unique_stories": 55,
        "platforms_covered": 6
    },
    "platform_exclusives": {
        "xinhua_news": {
            "title": "中国科学家实现量子计算新突破",
            "weight": 4.05
        },
        "weibo_hot": {
            "title": "明星慈善晚宴筹款超千万",
            "weight": 2.25
        }
    }
}

# Save the test digest
with open('docs/data/daily_digest.json', 'w', encoding='utf-8') as f:
    json.dump(test_digest, f, ensure_ascii=False, indent=2)

print("✅ Test digest created successfully!")
print("📁 Saved to: docs/data/daily_digest.json")
print("\nTop stories included:")
for story in test_digest['top_stories']:
    print(f"  {story['rank']}. {story['english_title'][:50]}...")
    print(f"     Platforms: {', '.join(story['platforms'])}")
    print(f"     Category: {story['category']}")
print("\nNow starting local server...")