import os
import sys
import unittest
import stat
import tempfile
from unittest.mock import patch

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

import main


class StartupTest(unittest.TestCase):
    def test_binary_specs_include_license_notices(self):
        root = os.path.join(os.path.dirname(__file__), "..")
        self.assertTrue(
            os.path.isfile(
                os.path.join(root, "static", "vendor", "fontawesome", "LICENSE.txt")
            )
        )
        for spec_name in ("SoftwareOrganizer.spec", "SoftwareOrganizer.windows.spec"):
            with open(os.path.join(root, spec_name), encoding="utf-8") as spec_file:
                spec = spec_file.read()
            self.assertIn("('LICENSE', '.')", spec)
            self.assertIn("('THIRD_PARTY_NOTICES.md', '.')", spec)

    def test_packaged_log_is_private_and_rotates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            handler = main._create_private_rotating_log_handler(temp_dir)
            try:
                self.assertEqual(handler.maxBytes, 2 * 1024 * 1024)
                self.assertEqual(handler.backupCount, 2)
                directory_mode = stat.S_IMODE(os.stat(temp_dir).st_mode)
                mode = stat.S_IMODE(os.stat(os.path.join(temp_dir, "app.log")).st_mode)
                self.assertEqual(directory_mode, 0o700)
                self.assertEqual(mode, 0o600)
            finally:
                handler.close()

    def test_macos_preferred_language_wins_over_c_utf8(self):
        defaults_output = '"zh-Hans-US"'
        completed = type("Completed", (), {"stdout": defaults_output})()
        with patch.object(main.platform, "system", return_value="Darwin"), patch.object(
            main.subprocess, "run", return_value=completed
        ), patch.dict(
            os.environ, {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}, clear=False
        ):
            self.assertEqual(main.detect_system_locale(), "zh-Hans-US")

    def test_qt_locale_is_used_when_native_locale_is_unavailable(self):
        with patch.object(main.platform, "system", return_value="Windows"), patch.object(
            main, "_macos_preferred_locale", return_value=None
        ), patch.object(main, "_qt_system_locale", return_value="zh_CN"), patch.dict(
            os.environ, {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}, clear=False
        ):
            self.assertEqual(main.detect_system_locale(), "zh_CN")

    def test_port_scan_includes_last_configured_port(self):
        with patch.object(main, "is_port_in_use", side_effect=lambda port: port < 18050), patch.object(
            main, "check_if_it_is_me", return_value=False
        ):
            self.assertEqual(main.get_server_port(), (18050, False))

    def test_port_scan_fails_instead_of_reusing_unrelated_service(self):
        with patch.object(main, "is_port_in_use", return_value=True), patch.object(
            main, "check_if_it_is_me", return_value=False
        ):
            with self.assertRaises(RuntimeError):
                main.get_server_port()


if __name__ == "__main__":
    unittest.main()
