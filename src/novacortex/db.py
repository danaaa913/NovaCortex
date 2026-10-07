"""SQLite persistence: users, question log and daily statistics."""

import logging
import sqlite3

from datetime import datetime

from novacortex.config import DB_PATH

logger = logging.getLogger(__name__)

# ==================== DATABASE ====================
def init_db():
    db_name = str(DB_PATH)
    with sqlite3.connect(db_name) as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, role TEXT DEFAULT 'visitor',
            uni_id TEXT, study_level TEXT DEFAULT 'بكالوريوس', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_active TEXT DEFAULT CURRENT_TIMESTAMP, total_questions INTEGER DEFAULT 0
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS questions_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, question TEXT NOT NULL,
            response TEXT NOT NULL, source TEXT NOT NULL, confidence REAL DEFAULT 0, response_time_ms INTEGER,
            docs_retrieved INTEGER DEFAULT 0, timestamp TEXT NOT NULL, study_level TEXT DEFAULT 'بكالوريوس'
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS response_cache (
            question_hash TEXT PRIMARY KEY, question TEXT, response TEXT, confidence REAL, source TEXT,
            created_at TEXT, last_used TEXT, hit_count INTEGER DEFAULT 0
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS daily_stats (
            date TEXT PRIMARY KEY, total_queries INTEGER DEFAULT 0, cache_hits INTEGER DEFAULT 0,
            rag_responses INTEGER DEFAULT 0, web_responses INTEGER DEFAULT 0, avg_confidence REAL DEFAULT 0,
            avg_response_time_ms INTEGER DEFAULT 0
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS conversation_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, message_index INTEGER, role TEXT,
            content TEXT, timestamp TEXT, is_summary INTEGER DEFAULT 0
        )""")
        conn.commit()
    logger.info("Database initialized (novacortex_v12.db)")
def save_user(telegram_id, username=None, first_name=None, role="visitor", uni_id=None, study_level="بكالوريوس"):
    with sqlite3.connect(str(DB_PATH)) as conn:
        c = conn.cursor()
        c.execute("""INSERT OR REPLACE INTO users
            (telegram_id, username, first_name, role, uni_id, study_level, last_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (telegram_id, username, first_name, role, uni_id, study_level, datetime.now().isoformat()))
        conn.commit()
def get_user(telegram_id):
    with sqlite3.connect(str(DB_PATH)) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        return c.fetchone()
def update_user_activity(telegram_id):
    with sqlite3.connect(str(DB_PATH)) as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET last_active = ?, total_questions = total_questions + 1 WHERE telegram_id = ?",
            (datetime.now().isoformat(), telegram_id))
        conn.commit()
def log_question(user_id, username, question, response, source, confidence, response_time_ms, docs_retrieved, study_level):
    with sqlite3.connect(str(DB_PATH)) as conn:
        c = conn.cursor()
        c.execute("""INSERT INTO questions_log
            (user_id, username, question, response, source, confidence, response_time_ms, docs_retrieved, timestamp, study_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, username, question, response, source, confidence, response_time_ms, docs_retrieved, datetime.now().isoformat(), study_level))
        conn.commit()
def update_daily_stats(source, confidence, response_time_ms):
    with sqlite3.connect(str(DB_PATH)) as conn:
        c = conn.cursor()
        today = datetime.now().date().isoformat()
        c.execute("SELECT * FROM daily_stats WHERE date = ?", (today,))
        row = c.fetchone()
        if row:
            total = row[1]
            cache = row[2] + (1 if source == 'cache' else 0)
            rag = row[3] + (1 if source == 'rag' else 0)
            web = row[4] + (1 if source == 'web' else 0)
            avg_conf = (row[5] * total + confidence) / (total + 1)
            avg_time = int((row[6] * total + response_time_ms) / (total + 1))
            c.execute("UPDATE daily_stats SET total_queries=total_queries+1, cache_hits=?, rag_responses=?, web_responses=?, avg_confidence=?, avg_response_time_ms=? WHERE date=?",
                (cache, rag, web, avg_conf, avg_time, today))
        else:
            c.execute("INSERT INTO daily_stats VALUES (?, 1, ?, ?, ?, ?, ?)",
                (today, 1 if source=='cache' else 0, 1 if source=='rag' else 0, 1 if source=='web' else 0, confidence, response_time_ms))
        conn.commit()
