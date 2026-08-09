import json
import os
import sys
import tempfile
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from software_organizer.config import ensure_private_file, get_default_config, write_json_file


class ConfigDefaultsTest(unittest.TestCase):
    def test_new_install_defaults_to_local_rules_with_useful_categories(self):
        config = get_default_config()

        self.assertFalse(config["use_ai"])
        self.assertTrue({"general", "documents", "mac", "ios", "windows"} <= set(config["categories"]))
        self.assertIn(".pdf", config["categories"]["documents"]["formats"])
        self.assertIn(".dmg", config["categories"]["mac"]["formats"])

    def test_json_state_is_written_with_private_permissions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.json")
            write_json_file(path, {"api_key": "secret"})

            with open(path, encoding="utf-8") as file:
                self.assertEqual(json.load(file), {"api_key": "secret"})
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_existing_state_permissions_are_restricted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "legacy.json")
            with open(path, "w", encoding="utf-8") as file:
                json.dump({"legacy": True}, file)
            os.chmod(path, 0o644)

            ensure_private_file(path)

            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
