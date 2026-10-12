"""Database regression tests for profile updates and user-data deletion."""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from novacortex import db  # noqa: E402


def test_profile_update_preserves_activity_and_delete_removes_user_data():
    original_path = db.DB_PATH
    try:
        with tempfile.TemporaryDirectory() as tmp:
            db.DB_PATH = Path(tmp) / "test.db"
            db.init_db()
            db.save_user(42, "first", "Test", uni_id="123", study_level="بكالوريوس")
            db.update_user_activity(42)
            db.save_user(42, "updated", "Test", uni_id="123", study_level="ماجستير")
            user = db.get_user(42)
            assert user[1] == "updated"
            assert user[5] == "ماجستير"
            assert user[8] == 1

            db.log_question(42, "updated", "سؤال", "جواب", "rag", 70, 10, 2, "ماجستير")
            conn = sqlite3.connect(db.DB_PATH)
            try:
                conn.execute(
                    "INSERT INTO conversation_memory "
                    "(user_id, message_index, role, content, timestamp, is_summary) "
                    "VALUES (42, 0, 'user', 'سؤال', 'now', 0)"
                )
                conn.commit()
            finally:
                conn.close()

            db.delete_user_data(42)
            conn = sqlite3.connect(db.DB_PATH)
            try:
                assert conn.execute("SELECT COUNT(*) FROM users WHERE telegram_id=42").fetchone()[0] == 0
                assert conn.execute("SELECT COUNT(*) FROM questions_log WHERE user_id=42").fetchone()[0] == 0
                assert conn.execute("SELECT COUNT(*) FROM conversation_memory WHERE user_id=42").fetchone()[0] == 0
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                conn.execute("PRAGMA journal_mode=DELETE")
            finally:
                conn.close()
    finally:
        db.DB_PATH = original_path


if __name__ == "__main__":
    test_profile_update_preserves_activity_and_delete_removes_user_data()
    print("db privacy: PASS")
