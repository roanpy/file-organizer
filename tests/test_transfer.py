import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from software_organizer.transfer import batch_move, move_software


class TransferTest(unittest.TestCase):
    def test_move_reports_target_exists_code_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            target_dir = os.path.join(tmpdir, "target")
            os.makedirs(source_dir)
            os.makedirs(target_dir)

            source_path = os.path.join(source_dir, "App.dmg")
            target_path = os.path.join(target_dir, "App.dmg")
            with open(source_path, "w", encoding="utf-8") as f:
                f.write("new")
            with open(target_path, "w", encoding="utf-8") as f:
                f.write("old")

            result = move_software(source_path, target_dir, overwrite=False)

            self.assertFalse(result["success"])
            self.assertEqual(result["code"], "target_exists")
            self.assertTrue(os.path.exists(source_path))
            with open(target_path, encoding="utf-8") as f:
                self.assertEqual(f.read(), "old")

    def test_batch_move_preserves_target_exists_code(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            target_dir = os.path.join(tmpdir, "target")
            os.makedirs(source_dir)
            os.makedirs(target_dir)

            source_path = os.path.join(source_dir, "Tool.dmg")
            target_path = os.path.join(target_dir, "Tool.dmg")
            open(source_path, "w", encoding="utf-8").close()
            open(target_path, "w", encoding="utf-8").close()

            result = batch_move([source_path], target_dir, overwrite=False)

            self.assertEqual(result["success"], [])
            self.assertEqual(result["failed"][0]["code"], "target_exists")

    def test_overwrite_replaces_target_after_copy_completes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            target_dir = os.path.join(tmpdir, "target")
            os.makedirs(source_dir)
            os.makedirs(target_dir)
            source_path = os.path.join(source_dir, "App.dmg")
            target_path = os.path.join(target_dir, "App.dmg")
            with open(source_path, "w", encoding="utf-8") as f:
                f.write("new")
            with open(target_path, "w", encoding="utf-8") as f:
                f.write("old")

            result = move_software(source_path, target_dir, overwrite=True)

            self.assertTrue(result["success"])
            self.assertFalse(os.path.exists(source_path))
            with open(target_path, encoding="utf-8") as f:
                self.assertEqual(f.read(), "new")

    def test_overwrite_copy_failure_preserves_both_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            target_dir = os.path.join(tmpdir, "target")
            os.makedirs(source_dir)
            os.makedirs(target_dir)
            source_path = os.path.join(source_dir, "App.dmg")
            target_path = os.path.join(target_dir, "App.dmg")
            with open(source_path, "w", encoding="utf-8") as f:
                f.write("new")
            with open(target_path, "w", encoding="utf-8") as f:
                f.write("old")

            with patch("software_organizer.transfer.shutil.copy2", side_effect=OSError("copy failed")):
                result = move_software(source_path, target_dir, overwrite=True)

            self.assertFalse(result["success"])
            self.assertTrue(os.path.exists(source_path))
            with open(target_path, encoding="utf-8") as f:
                self.assertEqual(f.read(), "old")


if __name__ == "__main__":
    unittest.main()
