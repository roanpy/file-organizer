import inspect
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

import server


class OperationSafetyTest(unittest.TestCase):
    def test_path_boundary_rejects_prefix_and_relative_paths(self):
        self.assertTrue(server._is_path_within("/tmp/root/file.dmg", "/tmp/root"))
        self.assertFalse(server._is_path_within("/tmp/root-old/file.dmg", "/tmp/root"))
        self.assertFalse(server._is_path_within("file.dmg", "/tmp/root"))

    def test_transfer_rejects_file_outside_configured_source(self):
        config = {
            "source_dir": "/source",
            "categories": {"mac": {"target_dir": "/target"}},
        }
        request = server.TransferRequest(
            files=["/outside/App.dmg"], destination="/target", overwrite=False
        )

        with patch.object(server, "load_config", return_value=config), patch.object(
            server, "batch_move"
        ) as batch_move:
            with self.assertRaises(HTTPException):
                server.transfer_software(request)

        batch_move.assert_not_called()

    def test_delete_rejects_file_outside_configured_targets(self):
        config = {"categories": {"mac": {"target_dir": "/target"}}}
        request = server.DeleteRequest(files=["/outside/App.dmg"])

        with patch.object(server, "load_config", return_value=config), patch.object(
            server, "batch_delete"
        ) as batch_delete:
            with self.assertRaises(HTTPException):
                server.delete_software_files(request)

        batch_delete.assert_not_called()

    def test_delete_allows_file_inside_configured_target(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "App.dmg")
            config = {"categories": {"mac": {"target_dir": tmpdir}}}
            request = server.DeleteRequest(files=[file_path])
            result = {"success": [], "failed": []}

            with patch.object(server, "load_config", return_value=config), patch.object(
                server, "batch_delete", return_value=result
            ) as batch_delete:
                self.assertEqual(server.delete_software_files(request), result)

            batch_delete.assert_called_once_with([file_path])

    def test_blocking_file_routes_use_fastapi_threadpool_dispatch(self):
        endpoints = (
            server.browse_directory,
            server.get_software_list,
            server.get_all_target_software,
            server.analyze_software,
            server.analyze_duplicates,
            server.transfer_software,
            server.delete_software_files,
        )

        self.assertTrue(all(not inspect.iscoroutinefunction(endpoint) for endpoint in endpoints))


if __name__ == "__main__":
    unittest.main()
