import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from software_organizer.database import SoftwareDB


class DatabaseTest(unittest.TestCase):
    def test_schema_and_writes_are_committed_before_connection_closes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "history.db")
            database = SoftwareDB(path)

            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

            record_id = database.log_transfer("Tool.dmg", "transfer", "/source/Tool.dmg")

            with closing(sqlite3.connect(path)) as connection:
                row = connection.execute(
                    "SELECT filename, action FROM transfer_logs WHERE id = ?", (record_id,)
                ).fetchone()
            self.assertEqual(row, ("Tool.dmg", "transfer"))


if __name__ == "__main__":
    unittest.main()
