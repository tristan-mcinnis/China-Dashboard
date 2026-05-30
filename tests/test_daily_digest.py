import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import collectors.daily_digest as digest


class TitleNormalizationTests(unittest.TestCase):
    def test_clean_title_strips_rank_prefix(self):
        self.assertEqual(digest._clean_title("1. 加快高水平科技自立自强"), "加快高水平科技自立自强")
        self.assertEqual(digest._clean_title("10、某新闻"), "某新闻")

    def test_similar_matches_near_identical_titles(self):
        self.assertTrue(digest._similar("加快高水平科技自立自强", "加快高水平科技自立自强"))
        self.assertFalse(digest._similar("完全不同的话题", "另一个无关主题内容"))


class SalienceTests(unittest.TestCase):
    def test_cross_platform_story_outranks_single_platform(self):
        data = {
            "baidu_top": {
                "items": [
                    {"title": "1. 共同话题", "url": "u1", "extra": {"rank": 1}},
                    {"title": "2. 仅百度话题", "url": "u2", "extra": {"rank": 2}},
                ]
            },
            "tencent_wechat_hot": {
                "items": [{"title": "1. 共同话题", "url": "u3", "extra": {"rank": 1}}]
            },
        }
        candidates = digest._collect_candidates(data)
        top = candidates[0]
        # The story trending on both platforms should rank first.
        self.assertEqual(top["primary_title"], "共同话题")
        self.assertEqual(top["platform_count"], 2)
        self.assertGreater(top["weight"], candidates[1]["weight"])


class BuildDigestTests(unittest.TestCase):
    def test_heuristic_build_produces_valid_schema(self):
        # Force the deterministic fallback path so the test never hits the network.
        sample = {
            "items": [{"title": "1. 测试新闻", "url": "u", "extra": {"rank": 1}}]
        }
        original_load = digest._load
        original_synth = digest._deepseek_synthesis
        digest._load = lambda name: sample if name in ("baidu_top", "weibo_hot") else {"items": []}
        digest._deepseek_synthesis = lambda *a, **k: None
        try:
            result = digest.build_digest()
        finally:
            digest._load = original_load
            digest._deepseek_synthesis = original_synth

        for key in ("digest_type", "date", "headline", "narrative", "top_stories", "generated_by"):
            self.assertIn(key, result)
        self.assertEqual(result["generated_by"], "heuristic")
        self.assertGreaterEqual(len(result["top_stories"]), 1)
        # Markdown rendering must not raise.
        md = digest._render_markdown(result)
        self.assertIn("China Daily Digest", md)


if __name__ == "__main__":
    unittest.main()
