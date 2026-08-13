import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from software_organizer.config import (
    add_category,
    ensure_private_file,
    ensure_private_runtime_state,
    get_default_config,
    write_json_file,
)


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

    def test_existing_runtime_logs_are_restricted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = [
                os.path.join(tmpdir, name)
                for name in ("app.log", "main.log", "server.log", "skill-server.log")
            ]
            for path in paths:
                with open(path, "w", encoding="utf-8") as log_file:
                    log_file.write("synthetic log")
                os.chmod(path, 0o644)

            ensure_private_runtime_state(tmpdir)

            self.assertTrue(all(os.stat(path).st_mode & 0o777 == 0o600 for path in paths))

    def test_category_ids_are_validated_in_the_storage_layer(self):
        with patch(
            "software_organizer.config.load_config",
            return_value={"categories": {}},
        ), patch("software_organizer.config.save_config") as save_config:
            result = add_category('bad" onclick="alert(1)', "Unsafe", [".dmg"])

        self.assertFalse(result["success"])
        save_config.assert_not_called()


if __name__ == "__main__":
    unittest.main()
