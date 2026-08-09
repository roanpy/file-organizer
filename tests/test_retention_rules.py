import os
import sys
import tempfile
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

import software_organizer.persistence as persistence


class RetentionRulesTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self._orig_retention_file = persistence.RETENTION_RULES_FILE
        self._orig_keep_file = persistence.KEEP_RULES_FILE
        persistence.RETENTION_RULES_FILE = os.path.join(
            self.tmpdir.name, "retention_rules.json"
        )
        persistence.KEEP_RULES_FILE = os.path.join(self.tmpdir.name, "keep_rules.json")
        persistence._retention_rules_cache = None
        persistence._keep_rules_cache = None

    def tearDown(self):
        persistence.RETENTION_RULES_FILE = self._orig_retention_file
        persistence.KEEP_RULES_FILE = self._orig_keep_file
        persistence._retention_rules_cache = None
        persistence._keep_rules_cache = None
        self.tmpdir.cleanup()

    def test_software_policy_keeps_latest_two_versions(self):
        result = persistence.save_software_retention_policy(
            "Example App", keep_latest=2
        )
        self.assertTrue(result["success"])

        items = [
            {"filename": "Example App 3.dmg", "name": "Example App", "version": "3"},
            {"filename": "Example App 2.dmg", "name": "Example App", "version": "2"},
            {"filename": "Example App 1.dmg", "name": "Example App", "version": "1"},
        ]
        summary = persistence.annotate_duplicate_retention(items, "Example App")

        self.assertEqual(summary["protected_count"], 2)
        self.assertTrue(items[0]["retention_protected"])
        self.assertTrue(items[1]["retention_protected"])
        self.assertFalse(items[2]["retention_protected"])
        self.assertEqual(summary["delete_candidate_count"], 1)

    def test_default_policy_keeps_newest_when_no_specific_policy(self):
        items = [
            {"filename": "Other App 2.dmg", "name": "Other App", "version": "2"},
            {"filename": "Other App 1.dmg", "name": "Other App", "version": "1"},
        ]
        summary = persistence.annotate_duplicate_retention(items, "Other App")

        self.assertEqual(summary["protected_count"], 0)
        self.assertTrue(items[0]["recommended_keep"])
        self.assertFalse(items[1]["recommended_keep"])

    def test_global_policy_keeps_latest_two_versions(self):
        persistence.save_retention_rules(
            {
                "global_keep_latest": 2,
                "software_policies": {},
                "protected_directories": [],
                "protected_keywords": [],
            }
        )
        items = [
            {"filename": "Global App 3.dmg", "name": "Global App", "version": "3"},
            {"filename": "Global App 2.dmg", "name": "Global App", "version": "2"},
            {"filename": "Global App 1.dmg", "name": "Global App", "version": "1"},
        ]
        summary = persistence.annotate_duplicate_retention(items, "Global App")

        self.assertTrue(items[0]["recommended_keep"])
        self.assertTrue(items[1]["recommended_keep"])
        self.assertFalse(items[2]["recommended_keep"])
        self.assertEqual(summary["recommended_count"], 2)

    def test_keyword_protection_adds_to_default_latest_keep(self):
        persistence.save_retention_rules(
            {
                "global_keep_latest": 1,
                "software_policies": {},
                "protected_directories": [],
                "protected_keywords": ["lts"],
            }
        )
        items = [
            {"filename": "Tool 3.dmg", "name": "Tool", "version": "3"},
            {"filename": "Tool 2 LTS.dmg", "name": "Tool", "version": "2"},
            {"filename": "Tool 1.dmg", "name": "Tool", "version": "1"},
        ]
        summary = persistence.annotate_duplicate_retention(items, "Tool")

        self.assertTrue(items[0]["recommended_keep"])
        self.assertTrue(items[1]["retention_protected"])
        self.assertTrue(items[1]["recommended_keep"])
        self.assertFalse(items[2]["recommended_keep"])
        self.assertEqual(summary["recommended_count"], 2)

    def test_directory_protection_marks_matching_files_protected(self):
        protected_dir = os.path.join(self.tmpdir.name, "Archive")
        persistence.save_retention_rules(
            {
                "global_keep_latest": 1,
                "software_policies": {},
                "protected_directories": [protected_dir],
                "protected_keywords": [],
            }
        )
        items = [
            {
                "filename": "Driver 3.dmg",
                "name": "Driver",
                "version": "3",
                "path": os.path.join(self.tmpdir.name, "Apps", "Driver 3.dmg"),
            },
            {
                "filename": "Driver 2.dmg",
                "name": "Driver",
                "version": "2",
                "path": os.path.join(protected_dir, "Driver 2.dmg"),
            },
            {
                "filename": "Driver 1.dmg",
                "name": "Driver",
                "version": "1",
                "path": os.path.join(self.tmpdir.name, "Apps", "Driver 1.dmg"),
            },
        ]
        summary = persistence.annotate_duplicate_retention(items, "Driver")

        self.assertTrue(items[0]["recommended_keep"])
        self.assertTrue(items[1]["retention_protected"])
        self.assertEqual(items[1]["retention_source"], "directory_policy")
        self.assertFalse(items[2]["recommended_keep"])
        self.assertEqual(summary["protected_count"], 1)


if __name__ == "__main__":
    unittest.main()
