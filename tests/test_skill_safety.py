import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL_SRC = Path(__file__).resolve().parents[1] / "SoftwareOrganizer-Skill" / "src"
sys.path.insert(0, str(SKILL_SRC))
spec = importlib.util.spec_from_file_location("skill_api_client", SKILL_SRC / "api_client.py")
skill_api_client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(skill_api_client)


class SkillSafetyTest(unittest.TestCase):
    def test_port_scan_includes_last_port(self):
        with patch.object(
            skill_api_client, "_port_in_use", side_effect=lambda port: port < 18050
        ), patch.object(skill_api_client, "_is_file_organizer_server", return_value=False):
            self.assertEqual(skill_api_client.find_server_port(), (18050, False))

    def test_port_scan_rejects_unrelated_services(self):
        with patch.object(skill_api_client, "_port_in_use", return_value=True), patch.object(
            skill_api_client, "_is_file_organizer_server", return_value=False
        ):
            with self.assertRaises(RuntimeError):
                skill_api_client.find_server_port()

    def test_duplicate_analysis_separates_package_variants(self):
        files = [
            {
                "filename": "LibreOffice_26.2.3_MacOS_aarch64.dmg",
                "path": "/target/LibreOffice_26.2.3_MacOS_aarch64.dmg",
                "version": "26.2.3",
            },
            {
                "filename": "LibreOffice_26.2.3_MacOS_aarch64_langpack_zh-CN.dmg",
                "path": "/target/LibreOffice_26.2.3_MacOS_aarch64_langpack_zh-CN.dmg",
                "version": "26.2.3",
            },
        ]

        self.assertEqual(skill_api_client.analyze_duplicates(files)["groups"], [])

    def test_duplicate_analysis_scopes_generic_installer_to_parent(self):
        files = [
            {"filename": "setup.exe", "path": "/target/ProductA/setup.exe"},
            {"filename": "setup.exe", "path": "/target/ProductB/setup.exe"},
        ]

        self.assertEqual(skill_api_client.analyze_duplicates(files)["groups"], [])

    def test_duplicate_analysis_uses_numeric_version_order(self):
        files = [
            {"filename": "Tool-9.9.dmg", "path": "/target/Tool-9.9.dmg", "version": "9.9"},
            {"filename": "Tool-10.0.dmg", "path": "/target/Tool-10.0.dmg", "version": "10.0"},
        ]

        groups = skill_api_client.analyze_duplicates(files)["groups"]

        kept = [item["filename"] for item in groups[0]["files"] if item["is_kept"]]
        self.assertEqual(kept, ["Tool-10.0.dmg"])

    def test_duplicate_analysis_uses_modified_time_without_version(self):
        files = [
            {"filename": "合同最终版.pdf", "path": "/target/合同最终版.pdf", "modified": 10},
            {"filename": "合同最终版.PDF", "path": "/target/合同最终版.PDF", "modified": 20},
        ]

        groups = skill_api_client.analyze_duplicates(files)["groups"]

        kept = [item["path"] for item in groups[0]["files"] if item["is_kept"]]
        self.assertEqual(kept, ["/target/合同最终版.PDF"])

    def test_extracts_document_date_as_version(self):
        self.assertEqual(
            skill_api_client._extract_version("合同归档_2026-07-16.pdf"),
            "2026.07.16",
        )

    def test_transfer_rejects_source_outside_configured_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "outside.dmg")
            open(source, "w", encoding="utf-8").close()
            config = {
                "source_dir": os.path.join(tmpdir, "source"),
                "categories": {"mac": {"target_dir": os.path.join(tmpdir, "target")}},
            }
            with patch.object(skill_api_client, "load_config", return_value=config):
                result = skill_api_client.transfer_file(source, os.path.join(tmpdir, "target"))

            self.assertFalse(result["success"])

    def test_delete_rejects_file_outside_configured_targets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "outside.dmg")
            open(path, "w", encoding="utf-8").close()
            config = {"categories": {"mac": {"target_dir": os.path.join(tmpdir, "target")}}}
            with patch.object(skill_api_client, "load_config", return_value=config), patch.object(
                skill_api_client.subprocess, "run"
            ) as run:
                result = skill_api_client.delete_file(path)

            self.assertFalse(result["success"])
            run.assert_not_called()

    def test_scanners_skip_file_symlinks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source"
            target = Path(tmpdir) / "target"
            external = Path(tmpdir) / "external"
            source.mkdir()
            target.mkdir()
            external.mkdir()
            external_file = external / "private.dmg"
            external_file.write_text("private", encoding="utf-8")
            (source / "source-link.dmg").symlink_to(external_file)
            (target / "target-link.dmg").symlink_to(external_file)

            with patch.object(skill_api_client, "load_config", return_value={"categories": {}}):
                source_result = skill_api_client.scan_directory(str(source))
            target_result = skill_api_client.scan_target_directories(
                str(target),
                {"mac": {"name": "Mac", "target_dir": str(target)}},
            )

            self.assertEqual(source_result["software"], [])
            self.assertEqual(target_result["categories"]["mac"]["files"], [])


if __name__ == "__main__":
    unittest.main()
