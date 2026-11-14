import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend import database
from backend.main import hash_password, require_role, verify_password
from backend.schemas import AccountCredentials


class AccountTests(unittest.TestCase):
    def test_password_hash_is_salted_and_verified(self):
        first_hash = hash_password("a-long-password")
        second_hash = hash_password("a-long-password")

        self.assertNotEqual(first_hash, second_hash)
        self.assertTrue(verify_password("a-long-password", first_hash))
        self.assertFalse(verify_password("wrong-password", first_hash))

    def test_role_guard_rejects_insufficient_permissions(self):
        with self.assertRaises(HTTPException) as raised:
            require_role({"role": "creator"}, "admin", "reviewer")

        self.assertEqual(raised.exception.status_code, 403)

    def test_email_is_normalized_and_password_length_is_validated(self):
        credentials = AccountCredentials(email="  Person@Example.com ", password="correct-horse")

        self.assertEqual(credentials.email, "person@example.com")
        with self.assertRaises(ValueError):
            AccountCredentials(email="not-an-email", password="correct-horse")
        with self.assertRaises(ValueError):
            AccountCredentials(email="person@example.com", password="short")

    def test_database_migration_preserves_existing_reviews(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.sqlite3"
            conn = sqlite3.connect(path)
            conn.execute(
                """
                CREATE TABLE reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'needs_review',
                    decision_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    decided_at TEXT
                )
                """
            )
            conn.execute(
                "INSERT INTO reviews (title, source_name, source_type, content) VALUES (?, ?, ?, ?)",
                ("Existing review", "draft.txt", "text", "Saved content"),
            )
            conn.commit()
            conn.close()

            with patch.object(database, "DATABASE_PATH", path):
                database.initialize_database()
                with database.connection() as migrated:
                    row = migrated.execute(
                        "SELECT title, content, created_by, decided_by FROM reviews WHERE id = 1"
                    ).fetchone()
                    users_table = migrated.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'users'"
                    ).fetchone()

            self.assertEqual(row["title"], "Existing review")
            self.assertEqual(row["content"], "Saved content")
            self.assertIsNone(row["created_by"])
            self.assertIsNone(row["decided_by"])
            self.assertIsNotNone(users_table)


if __name__ == "__main__":
    unittest.main()
