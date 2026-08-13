import os
import sys
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

import software_organizer.ai_engines as ai_engines


class AIHttpEnginesTest(unittest.TestCase):
    def setUp(self):
        self._orig_http_json_request = ai_engines._http_json_request
        self._orig_call_ai_engine = ai_engines._call_ai_engine

    def tearDown(self):
        ai_engines._http_json_request = self._orig_http_json_request
        ai_engines._call_ai_engine = self._orig_call_ai_engine

    def test_gemini_uses_http_and_maps_retired_default(self):
        captured = {}

        def fake_request(url, headers, payload=None, timeout=60, method=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = payload
            return {
                "candidates": [
                    {"content": {"parts": [{"text": '{"ok": true}'}]}}
                ]
            }

        ai_engines._http_json_request = fake_request

        result = ai_engines._call_ai_engine(
            "gemini",
            {"gemini": {"api_key": "key", "model_name": "gemini-pro"}},
            'Return {"ok": true}.',
            json_mode=True,
        )

        self.assertEqual(result, {"ok": True})
        self.assertIn("/models/gemini-2.5-flash:generateContent", captured["url"])
        self.assertEqual(captured["headers"]["x-goog-api-key"], "key")
        self.assertEqual(
            captured["payload"]["generationConfig"]["responseMimeType"],
            "application/json",
        )

    def test_deepseek_uses_http_and_maps_retired_coder_model(self):
        captured = {}

        def fake_request(url, headers, payload=None, timeout=60, method=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = payload
            return {"choices": [{"message": {"content": '{"ok": true}'}}]}

        ai_engines._http_json_request = fake_request

        result = ai_engines._call_ai_engine(
            "deepseek",
            {"deepseek": {"api_key": "key", "model_name": "deepseek-coder"}},
            'Return {"ok": true}.',
            json_mode=True,
        )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(captured["url"], "https://api.deepseek.com/chat/completions")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer key")
        self.assertEqual(captured["payload"]["model"], "deepseek-v4-flash")
        self.assertEqual(captured["payload"]["response_format"], {"type": "json_object"})

    def test_ollama_uses_http_without_sdk(self):
        captured = {}

        def fake_request(url, headers, payload=None, timeout=60, method=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = payload
            return {"message": {"content": '{"ok": true}'}}

        ai_engines._http_json_request = fake_request

        result = ai_engines._call_ai_engine(
            "ollama",
            {"ollama": {"url": "http://127.0.0.1:11434", "model_name": "llama3"}},
            'Return {"ok": true}.',
            json_mode=True,
        )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(captured["url"], "http://127.0.0.1:11434/api/chat")
        self.assertEqual(captured["headers"], {})
        self.assertEqual(captured["payload"]["model"], "llama3")
        self.assertEqual(captured["payload"]["format"], "json")

    def test_batch_path_suggestions_do_not_send_absolute_paths(self):
        captured = {}

        def fake_call(engine, config, prompt, json_mode=True):
            captured["prompt"] = prompt
            return {
                "suggestions": [
                    {
                        "item_id": "ITEM_001",
                        "filename": "Tool.dmg",
                        "suggested_path": "DIR_001",
                        "reason": "matching folder",
                    }
                ]
            }

        ai_engines._call_ai_engine = fake_call

        result = ai_engines.batch_analyze_path_suggestions(
            "gemini",
            {},
            [{"filename": "Tool.dmg", "name": "Tool", "path": "/source/Tool.dmg"}],
            ["/tmp/private/Tools/04_Net"],
        )

        self.assertNotIn("/tmp/private/Tools/04_Net", captured["prompt"])
        self.assertNotIn("/source/Tool.dmg", captured["prompt"])
        self.assertIn("DIR_001", captured["prompt"])
        self.assertIn("ITEM_001", captured["prompt"])
        self.assertEqual(
            result["suggestions"][0]["suggested_path"],
            "/tmp/private/Tools/04_Net",
        )
        self.assertEqual(result["suggestions"][0]["source_path"], "/source/Tool.dmg")

    def test_batch_path_suggestions_keep_duplicate_filenames_distinct(self):
        def fake_call(engine, config, prompt, json_mode=True):
            return {
                "suggestions": [
                    {"item_id": "ITEM_001", "suggested_path": "DIR_001"},
                    {"item_id": "ITEM_002", "suggested_path": "DIR_002"},
                ]
            }

        ai_engines._call_ai_engine = fake_call
        result = ai_engines.batch_analyze_path_suggestions(
            "gemini",
            {},
            [
                {"filename": "setup.zip", "name": "Product A", "path": "/source/a/setup.zip"},
                {"filename": "setup.zip", "name": "Product B", "path": "/source/b/setup.zip"},
            ],
            ["/target/Product A", "/target/Product B"],
        )

        self.assertEqual(
            [(item["source_path"], item["suggested_path"]) for item in result["suggestions"]],
            [
                ("/source/a/setup.zip", "/target/Product A"),
                ("/source/b/setup.zip", "/target/Product B"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
