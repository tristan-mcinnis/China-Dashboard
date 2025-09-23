import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import collectors.tencent_wechat_hot as tencent_wechat_hot


class DummyResponse:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload

    def json(self):
        return self._payload


class WechatCollectorTests(unittest.TestCase):
    def test_fetch_wechat_hot_basic_structure(self):
        payload = {
            "code": 200,
            "result": {
                "list": [
                    {
                        "word": "测试话题",
                        "index": 321,
                    }
                ]
            },
        }

        with patch.dict(os.environ, {"TIANAPI_API_KEY": "test-key"}, clear=False):
            with patch("collectors.tencent_wechat_hot.requests.get", return_value=DummyResponse(payload)):
                with patch("collectors.tencent_wechat_hot.translate_text", return_value="Test topic"):
                    items = tencent_wechat_hot.fetch_wechat_hot(max_items=5)

        self.assertEqual(len(items), 1)
        first = items[0]
        self.assertEqual(first["title"], "1. 测试话题")
        self.assertEqual(first["value"], "指数 321")
        self.assertTrue(first["url"].endswith("%E6%B5%8B%E8%AF%95%E8%AF%9D%E9%A2%98"))
        self.assertEqual(first["extra"]["translation"], "Test topic")

    def test_fetch_wechat_hot_nested_response(self):
        payload = {
            "code": 200,
            "result": {
                "data": {
                    "newslist": [
                        {
                            "title": "嵌套话题",
                            "heat": "8899",
                            "url": "https://example.com/post",
                        }
                    ]
                }
            },
        }

        with patch.dict(os.environ, {"TIANAPI_API_KEY": "test-key"}, clear=False):
            with patch("collectors.tencent_wechat_hot.requests.get", return_value=DummyResponse(payload)):
                with patch("collectors.tencent_wechat_hot.translate_text", return_value="Nested topic"):
                    items = tencent_wechat_hot.fetch_wechat_hot(max_items=5)

        self.assertEqual(len(items), 1)
        first = items[0]
        self.assertEqual(first["title"], "1. 嵌套话题")
        self.assertEqual(first["value"], "指数 8899")
        self.assertEqual(first["url"], "https://example.com/post")
        self.assertEqual(first["extra"]["raw_score"], "8899")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
