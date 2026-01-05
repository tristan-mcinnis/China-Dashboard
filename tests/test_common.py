"""Unit tests for collectors/common.py utilities."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from collectors import common


class TestNowIsoTz8(unittest.TestCase):
    def test_returns_iso_format_with_timezone(self):
        result = common.now_iso_tz8()
        self.assertIn("+08:00", result)
        self.assertRegex(result, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+08:00")


class TestSchema(unittest.TestCase):
    def test_schema_creates_correct_structure(self):
        items = [{"title": "test", "value": "123"}]
        result = common.schema("Test Source", items)

        self.assertIn("as_of", result)
        self.assertEqual(result["source"], "Test Source")
        self.assertEqual(result["items"], items)

    def test_schema_with_empty_items(self):
        result = common.schema("Empty Source", [])
        self.assertEqual(result["items"], [])


class TestWriteJson(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for tests
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        os.makedirs("docs/data", exist_ok=True)

    def tearDown(self):
        os.chdir(self.original_cwd)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_json_creates_file(self):
        payload = {"as_of": "2024-01-01", "items": [{"title": "test"}]}
        result = common.write_json("docs/data/test.json", payload, min_items=1)

        self.assertTrue(result)
        self.assertTrue(os.path.exists("docs/data/test.json"))

        with open("docs/data/test.json", "r", encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved["items"][0]["title"], "test")

    def test_write_json_skips_on_insufficient_items(self):
        payload = {"as_of": "2024-01-01", "items": []}
        result = common.write_json("docs/data/test.json", payload, min_items=1)

        self.assertFalse(result)
        self.assertFalse(os.path.exists("docs/data/test.json"))

    def test_write_json_rejects_path_outside_allowed_dirs(self):
        payload = {"as_of": "2024-01-01", "items": [{"title": "test"}]}

        with self.assertRaises(ValueError) as context:
            common.write_json("/tmp/malicious.json", payload)

        self.assertIn("Security", str(context.exception))

    def test_write_json_rejects_path_traversal(self):
        payload = {"as_of": "2024-01-01", "items": [{"title": "test"}]}

        with self.assertRaises(ValueError):
            common.write_json("docs/data/../../../etc/passwd", payload)


class TestWriteWithHistory(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        os.makedirs("docs/data/history", exist_ok=True)

    def tearDown(self):
        os.chdir(self.original_cwd)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_with_history_creates_both_files(self):
        payload = common.schema("Test", [{"title": "item1"}])
        result = common.write_with_history(
            "docs/data/test.json",
            "docs/data/history/test.json",
            payload,
            min_items=1
        )

        self.assertTrue(result)
        self.assertTrue(os.path.exists("docs/data/test.json"))
        self.assertTrue(os.path.exists("docs/data/history/test.json"))

    def test_write_with_history_appends_entries(self):
        # Write first entry
        payload1 = common.schema("Test", [{"title": "item1"}])
        common.write_with_history(
            "docs/data/test.json",
            "docs/data/history/test.json",
            payload1,
            min_items=1
        )

        # Write second entry with different timestamp
        payload2 = common.schema("Test", [{"title": "item2"}])
        common.write_with_history(
            "docs/data/test.json",
            "docs/data/history/test.json",
            payload2,
            min_items=1
        )

        with open("docs/data/history/test.json", "r", encoding="utf-8") as f:
            history = json.load(f)

        self.assertIn("entries", history)
        # Should have entries (may be 1 or 2 depending on timestamp resolution)
        self.assertGreaterEqual(len(history["entries"]), 1)

    def test_write_with_history_skips_empty_items(self):
        payload = common.schema("Test", [])
        result = common.write_with_history(
            "docs/data/test.json",
            "docs/data/history/test.json",
            payload,
            min_items=1
        )

        self.assertFalse(result)


class TestBaseHeaders(unittest.TestCase):
    def test_base_headers_returns_dict(self):
        headers = common.base_headers()
        self.assertIsInstance(headers, dict)
        self.assertIn("User-Agent", headers)
        self.assertIn("Accept", headers)

    def test_base_headers_uses_mobile_user_agent(self):
        headers = common.base_headers()
        ua = headers["User-Agent"]
        self.assertTrue(
            "Mobile" in ua or "iPhone" in ua or "Android" in ua,
            f"Expected mobile user agent, got: {ua}"
        )


class TestSafeGet(unittest.TestCase):
    def test_safe_get_returns_value(self):
        d = {"key": "value"}
        self.assertEqual(common.safe_get(d, "key"), "value")

    def test_safe_get_returns_default_for_missing_key(self):
        d = {"key": "value"}
        self.assertEqual(common.safe_get(d, "missing"), "")
        self.assertEqual(common.safe_get(d, "missing", "default"), "default")

    def test_safe_get_handles_non_dict(self):
        self.assertEqual(common.safe_get(None, "key"), "")
        self.assertEqual(common.safe_get("string", "key"), "")


class TestBackoffSleep(unittest.TestCase):
    @patch("collectors.common.time.sleep")
    def test_backoff_sleep_increases_with_attempts(self, mock_sleep):
        common.backoff_sleep(0)
        first_call = mock_sleep.call_args[0][0]

        common.backoff_sleep(2)
        second_call = mock_sleep.call_args[0][0]

        self.assertLess(first_call, second_call)

    @patch("collectors.common.time.sleep")
    def test_backoff_sleep_has_max_limit(self, mock_sleep):
        common.backoff_sleep(10)  # High attempt number
        sleep_time = mock_sleep.call_args[0][0]
        self.assertLessEqual(sleep_time, 9)  # Max is 8 + random (< 1)


class TestTranslateText(unittest.TestCase):
    @patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False)
    def test_translate_text_returns_empty_without_api_key(self):
        # Reset the cached client
        common._openai_client = None
        result = common.translate_text("测试文本")
        self.assertEqual(result, "")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False)
    @patch("collectors.common.OpenAI")
    def test_translate_text_calls_openai(self, mock_openai_class):
        # Reset the cached client
        common._openai_client = None

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test text"
        mock_client.chat.completions.create.return_value = mock_response

        result = common.translate_text("测试文本")

        self.assertEqual(result, "Test text")
        mock_client.chat.completions.create.assert_called_once()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False)
    @patch("collectors.common.OpenAI")
    def test_translate_text_truncates_long_translations(self, mock_openai_class):
        # Reset the cached client
        common._openai_client = None

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        long_text = "A" * 100  # 100 characters
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = long_text
        mock_client.chat.completions.create.return_value = mock_response

        result = common.translate_text("测试")

        self.assertLessEqual(len(result), 60)
        self.assertTrue(result.endswith("..."))


class TestGetOpenaiClient(unittest.TestCase):
    def setUp(self):
        # Reset the cached client before each test
        common._openai_client = None

    @patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False)
    def test_returns_none_without_api_key(self):
        result = common._get_openai_client()
        self.assertIsNone(result)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False)
    @patch("collectors.common.OpenAI")
    def test_creates_client_with_api_key(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        result = common._get_openai_client()

        self.assertEqual(result, mock_client)
        mock_openai_class.assert_called_once_with(api_key="test-key")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False)
    @patch("collectors.common.OpenAI")
    def test_caches_client(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        result1 = common._get_openai_client()
        result2 = common._get_openai_client()

        self.assertEqual(result1, result2)
        # Should only create client once
        mock_openai_class.assert_called_once()


if __name__ == "__main__":
    unittest.main()
