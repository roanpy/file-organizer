# -*- coding: utf-8 -*-
"""
Database Module - SQLite database management.

Current usage:
- Records historical logs of file transfer/deletion operations (/api/history endpoint).
- Reserved for future software record management features.

Contains:
- Software records table (reserved)
- Transfer history table (active)
"""

import os
import sqlite3
from contextlib import closing
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import APP_DIR


class SoftwareDB:
    """Software Database management class."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize database connection."""
        self.db_path = db_path or os.path.join(APP_DIR, "software_organizer.db")
        self._ensure_tables()
        try:
            os.chmod(self.db_path, 0o600)
        except OSError:
            pass

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self) -> None:
        """Ensure specific tables exist."""
        with closing(self._get_connection()) as conn, conn:
            cursor = conn.cursor()

            # Software records table (Reserved)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS software_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    software_name TEXT,
                    version TEXT,
                    platform TEXT,
                    source_path TEXT,
                    destination_path TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Transfer history table (In use)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transfer_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    action TEXT NOT NULL,
                    source_path TEXT,
                    destination_path TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()

    def add_record(
        self,
        filename: str,
        software_name: Optional[str] = None,
        version: Optional[str] = None,
        platform: Optional[str] = None,
        source_path: Optional[str] = None,
    ) -> int:
        """Add a software record."""
        with closing(self._get_connection()) as conn, conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO software_records 
                (filename, software_name, version, platform, source_path)
                VALUES (?, ?, ?, ?, ?)
            """,
                (filename, software_name, version, platform, source_path),
            )
            conn.commit()
            return cursor.lastrowid

    def update_record(self, record_id: int, **kwargs) -> bool:
        """Update a software record."""
        if not kwargs:
            return False

        allowed_fields = [
            "software_name",
            "version",
            "platform",
            "source_path",
            "destination_path",
            "status",
        ]
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        updates["updated_at"] = datetime.now().isoformat()

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [record_id]

        with closing(self._get_connection()) as conn, conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE software_records SET {set_clause} WHERE id = ?", values
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_record(self, record_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a single record."""
        with closing(self._get_connection()) as conn, conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM software_records WHERE id = ?", (record_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_records_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Retrieve records by status."""
        with closing(self._get_connection()) as conn, conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM software_records WHERE status = ? ORDER BY created_at DESC",
                (status,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def log_transfer(
        self,
        filename: str,
        action: str,
        source_path: Optional[str] = None,
        destination_path: Optional[str] = None,
    ) -> int:
        """Log a transfer operation."""
        with closing(self._get_connection()) as conn, conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO transfer_logs 
                (filename, action, source_path, destination_path)
                VALUES (?, ?, ?, ?)
            """,
                (filename, action, source_path, destination_path),
            )
            conn.commit()
            return cursor.lastrowid

    def get_transfer_logs(
        self, limit: int = 100, action: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve transfer history logs."""
        with closing(self._get_connection()) as conn, conn:
            cursor = conn.cursor()

            if action:
                cursor.execute(
                    "SELECT * FROM transfer_logs WHERE action = ? ORDER BY timestamp DESC LIMIT ?",
                    (action, limit),
                )
            else:
                cursor.execute(
                    "SELECT * FROM transfer_logs ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                )

            return [dict(row) for row in cursor.fetchall()]


# Global database instance
_db_instance: Optional[SoftwareDB] = None


def get_db() -> SoftwareDB:
    """Get database instance (singleton)."""
    global _db_instance
    if _db_instance is None:
        _db_instance = SoftwareDB()
    return _db_instance
