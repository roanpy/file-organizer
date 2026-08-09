import os
import sys
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

import software_organizer.file_ops as file_ops
from software_organizer.ai_engines import group_software_by_name


class MatchingRulesTest(unittest.TestCase):
    def setUp(self):
        self._orig_get_categories = file_ops.get_categories
        file_ops.get_categories = lambda: {
            "general": {
                "name": "Universal",
                "formats": [".zip", ".7z", ".rar"],
                "target_dir": "",
                "cross_format_match": False,
            },
            "mac": {
                "name": "Mac",
                "formats": [".dmg", ".pkg", ".zip"],
                "target_dir": "/target/mac",
                "cross_format_match": True,
            },
        }

    def tearDown(self):
        file_ops.get_categories = self._orig_get_categories

    def test_matches_compact_product_name(self):
        source_name = file_ops.parse_software_name("iMazing3forMac.dmg")
        target_name = file_ops.parse_software_name("iMazing.v3.5.2.dmg")

        matches = file_ops.find_target_matches(
            {
                "name": source_name["name"],
                "filename": "iMazing3forMac.dmg",
                "extension": ".dmg",
                "category": "mac",
            },
            [
                {
                    "name": target_name["name"],
                    "filename": "iMazing.v3.5.2.dmg",
                    "extension": ".dmg",
                    "category": "mac",
                    "version": target_name["version"],
                    "parent_dir": "07_Live",
                    "path": "/target/mac/07_Live/iMazing.v3.5.2.dmg",
                    "location": "target",
                }
            ],
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["parent_dir_abs"], "/target/mac/07_Live")
        self.assertEqual(matches[0]["location"], "target")

    def test_general_zip_can_match_cross_format_mac_target(self):
        matches = file_ops.find_target_matches(
            {
                "name": "BetterTouchTool",
                "filename": "BetterTouchTool.zip",
                "extension": ".zip",
                "category": "general",
            },
            [
                {
                    "name": "BetterTouchTool",
                    "filename": "BetterTouchTool.v5.155.dmg",
                    "extension": ".dmg",
                    "category": "mac",
                    "version": "5.155",
                    "parent_dir": "01_System/TouchPad",
                    "path": "/target/mac/01_System/TouchPad/BetterTouchTool.v5.155.dmg",
                    "location": "target",
                }
            ],
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["category"], "mac")

    def test_does_not_match_different_adobe_products(self):
        score = file_ops.software_name_similarity(
            "Adobe Photoshop", "Adobe Photoshop Lightroom"
        )
        self.assertLess(score, 0.86)

    def test_does_not_match_open_codesign_to_open_design(self):
        source_name = file_ops.parse_software_name("open-codesign-0.2.1-arm64.dmg")
        target_name = file_ops.parse_software_name("open-design-0.8.0-mac-arm64.dmg")

        self.assertEqual(
            file_ops.normalize_software_name(source_name["name"]), "open codesign"
        )
        self.assertEqual(
            file_ops.normalize_software_name(target_name["name"]), "open design"
        )
        self.assertLess(
            file_ops.software_name_similarity(source_name["name"], target_name["name"]),
            0.86,
        )

        matches = file_ops.find_target_matches(
            {
                "name": source_name["name"],
                "filename": "open-codesign-0.2.1-arm64.dmg",
                "extension": ".dmg",
                "category": "mac",
            },
            [
                {
                    "name": target_name["name"],
                    "filename": "open-design-0.8.0-mac-arm64.dmg",
                    "extension": ".dmg",
                    "category": "mac",
                    "version": target_name["version"],
                    "parent_dir": "01_System",
                    "path": "/target/mac/01_System/open-design-0.8.0-mac-arm64.dmg",
                    "location": "target",
                }
            ],
        )

        self.assertEqual(matches, [])

    def test_dotted_product_names_do_not_collapse_to_vendor(self):
        pairs = (
            ("PDF.Converter", "PDF.Expert"),
            ("SQLPro.Studio", "SQLPro.for.SQLite"),
            ("Wondershare.Recoverit", "Wondershare.Repairit"),
            ("Cisdem.VideoPaw", "Cisdem.PDFMaster"),
        )

        for left, right in pairs:
            with self.subTest(left=left, right=right):
                self.assertLess(file_ops.software_name_similarity(left, right), 0.86)

        items = [
            {
                "name": name,
                "filename": f"{name}.v1.0.dmg",
                "extension": ".dmg",
                "path": f"/target/{name}.v1.0.dmg",
            }
            for pair in pairs
            for name in pair
        ]
        self.assertEqual(len(group_software_by_name(items)), len(items))

    def test_parses_document_date_as_version(self):
        name = file_ops.parse_software_name("合同归档_2026-06-25.pdf")

        self.assertEqual(name["name"], "合同归档")
        self.assertEqual(name["version"], "2026.06.25")

    def test_parses_compact_document_date_as_version(self):
        name = file_ops.parse_software_name("合同归档20260625.pdf")

        self.assertEqual(name["name"], "合同归档")
        self.assertEqual(name["version"], "2026.06.25")

    def test_plain_document_without_date_has_no_version(self):
        name = file_ops.parse_software_name("合同归档最终版.pdf")

        self.assertEqual(name["name"], "合同归档最终版")
        self.assertIsNone(name["version"])

    def test_parses_single_major_version_before_edition_note(self):
        name = file_ops.parse_software_name("Bartender 6（正）.dmg")

        self.assertEqual(name["name"], "Bartender（正）")
        self.assertEqual(name["version"], "6")

    def test_cleanup_groups_keep_language_pack_separate(self):
        items = [
            {
                "name": "LibreOffice",
                "filename": "LibreOffice_26.2.3_MacOS_aarch64.dmg",
                "extension": ".dmg",
                "path": "/target/LibreOffice_26.2.3_MacOS_aarch64.dmg",
            },
            {
                "name": "LibreOffice",
                "filename": "LibreOffice_26.2.3_MacOS_aarch64_langpack_zh-CN.dmg",
                "extension": ".dmg",
                "path": "/target/LibreOffice_26.2.3_MacOS_aarch64_langpack_zh-CN.dmg",
            },
        ]

        groups = group_software_by_name(items)

        self.assertEqual(len(groups), 2)

    def test_cleanup_groups_keep_cpu_architectures_separate(self):
        items = [
            {
                "name": "Tool",
                "filename": "Tool-2.0-arm64.dmg",
                "extension": ".dmg",
                "path": "/target/Tool-2.0-arm64.dmg",
            },
            {
                "name": "Tool",
                "filename": "Tool-2.0-x64.dmg",
                "extension": ".dmg",
                "path": "/target/Tool-2.0-x64.dmg",
            },
        ]

        self.assertEqual(len(group_software_by_name(items)), 2)

    def test_cleanup_groups_sort_versions_numerically(self):
        items = [
            {
                "name": "Tool",
                "filename": "Tool-9.9.dmg",
                "extension": ".dmg",
                "version": "9.9",
                "path": "/target/Tool-9.9.dmg",
            },
            {
                "name": "Tool",
                "filename": "Tool-10.0.dmg",
                "extension": ".dmg",
                "version": "10.0",
                "path": "/target/Tool-10.0.dmg",
            },
        ]

        group = next(iter(group_software_by_name(items).values()))

        self.assertEqual(group[0]["filename"], "Tool-10.0.dmg")

    def test_generic_installers_are_scoped_to_parent_directory(self):
        items = [
            {
                "name": "setup",
                "filename": "setup.exe",
                "extension": ".exe",
                "parent_dir": "ProductA",
                "path": "/target/ProductA/setup.exe",
            },
            {
                "name": "setup",
                "filename": "setup.exe",
                "extension": ".exe",
                "parent_dir": "ProductB",
                "path": "/target/ProductB/setup.exe",
            },
        ]

        self.assertEqual(len(group_software_by_name(items)), 2)
        self.assertEqual(file_ops.software_name_similarity("setup", "setup"), 0)


if __name__ == "__main__":
    unittest.main()
