import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import collectors.baidu_top as baidu_top


class DummyResponse:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload

    def json(self):
        return self._payload


class BaiduCollectorTests(unittest.TestCase):
    def test_extract_item_list_handles_top_level_newslist(self):
        payload = {
            "code": 200,
            "newslist": [
                {"word": "测试", "hot": 123, "url": "https://example.com"},
                "not-a-dict",
            ],
        }

        items = baidu_top._extract_item_list(payload)  # pylint: disable=protected-access
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["word"], "测试")

    def test_fetch_baidu_top_normalises_fields(self):
        payload = {
            "code": 200,
            "result": {
                "data": {
                    "list": [
                        {
                            "keyword": "人工智能",
                            "heat": "889900",
                            "desc": "热门科技话题",
                        }
                    ]
                }
            },
        }

        with patch.dict(os.environ, {"TIANAPI_API_KEY": "test"}, clear=False):
            with patch("collectors.baidu_top.requests.get", return_value=DummyResponse(payload)):
                with patch("collectors.baidu_top.translate_text", return_value="AI"):
                    items = baidu_top.fetch_baidu_top(max_items=5)

        self.assertEqual(len(items), 1)
        first = items[0]
        self.assertEqual(first["title"], "1. 人工智能")
        self.assertEqual(first["value"], "热度 889900")
        self.assertTrue(first["url"].startswith("https://www.baidu.com/s?wd="))
        self.assertEqual(first["extra"]["description"], "热门科技话题")
        self.assertEqual(first["extra"]["translation"], "AI")
        self.assertEqual(first["extra"]["api_source"], "tianapi")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
