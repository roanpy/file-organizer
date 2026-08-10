import os
import sys
import unittest
import asyncio

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

import server


class ConfigSecurityTest(unittest.TestCase):
    def test_public_config_redacts_api_keys(self):
        public_config = server._public_config(
            {
                "gemini": {"api_key": "example-gemini-secret", "model_name": "gemini"},
                "deepseek": {"api_key": "example-deepseek-secret", "model_name": "chat"},
                "ollama": {"url": "http://127.0.0.1:11434"},
                "custom_providers": {
                    "demo": {"api_key": "custom-secret-value", "model_name": "demo"}
                },
            }
        )

        self.assertNotIn("api_key", public_config["gemini"])
        self.assertNotIn("api_key", public_config["deepseek"])
        self.assertNotIn("api_key", public_config["custom_providers"]["demo"])
        self.assertTrue(public_config["gemini"]["configured"])
        self.assertTrue(public_config["deepseek"]["configured"])
        self.assertTrue(public_config["custom_providers"]["demo"]["configured"])
        self.assertIn("api_key_masked", public_config["gemini"])
        self.assertIn("configured", public_config["gemini"])
        self.assertIn("configured", public_config["deepseek"])

    def test_public_config_keeps_configured_false_without_api_key(self):
        public_config = server._public_config(
            {
                "gemini": {"model_name": "gemini"},
                "deepseek": {"api_key": "", "model_name": "chat"},
            }
        )

        self.assertFalse(public_config["gemini"]["configured"])
        self.assertFalse(public_config["deepseek"]["configured"])
        self.assertNotIn("api_key", public_config["gemini"])
        self.assertNotIn("api_key", public_config["deepseek"])

    def test_merge_secret_config_preserves_existing_key_when_blank(self):
        merged = server._merge_secret_config(
            {"api_key": "existing-key", "model_name": "old"},
            {"api_key": "", "model_name": "new"},
        )

        self.assertEqual(merged["api_key"], "existing-key")
        self.assertEqual(merged["model_name"], "new")

    def test_ai_status_default_is_lightweight_configured_state(self):
        original_load_config = server.load_config
        original_cache = dict(server._ai_status_cache)
        try:
            server.load_config = lambda: {
                "gemini": {"api_key": "gemini-key", "model_name": "gemini-2.5-flash"},
                "deepseek": {"api_key": "deepseek-key", "model_name": "deepseek-chat"},
                "ollama": {"url": "http://127.0.0.1:11434"},
            }
            server._ai_status_cache["data"] = None
            server._ai_status_cache["time"] = 0

            status = asyncio.run(server.get_ai_status())
        finally:
            server.load_config = original_load_config
            server._ai_status_cache.clear()
            server._ai_status_cache.update(original_cache)

        self.assertTrue(status["gemini"]["configured"])
        self.assertTrue(status["gemini"]["connected"])
        self.assertFalse(status["gemini"]["verified"])
        self.assertIn("gemini-2.5-flash", status["gemini"]["models"])
        self.assertTrue(status["deepseek"]["connected"])


    def test_ai_config_endpoint_redacts_stored_credentials(self):
        original_load_ai_config = server.load_ai_config
        try:
            server.load_ai_config = lambda: {
                "api_key": "stored-secret",
                "core_rules": {
                    "token": "nested-secret",
                    "keep": "visible",
                },
                "items": [{"password": "secret"}, "plain"],
            }
            result = asyncio.run(server.get_ai_config())
        finally:
            server.load_ai_config = original_load_ai_config

        self.assertNotIn("api_key", result)
        self.assertNotIn("token", result["core_rules"])
        self.assertEqual(result["core_rules"]["keep"], "visible")
        self.assertEqual(result["items"], [{}, "plain"])


if __name__ == "__main__":
    unittest.main()
