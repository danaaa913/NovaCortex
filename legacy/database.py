"""
Database operations for NovaCortex Bot
Handles all SQLite database interactions
"""

import sqlite3
from datetime import datetime
from typing import List, Optional, Tuple
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class Database:
    """Database manager for chat history and user data"""
    
    def __init__(self, db_path: str = "chat_history.db"):
        self.db_path = db_path
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def init_db(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            c = conn.cursor()
            
            # Conversations table
            c.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    session_title TEXT,
                    message TEXT NOT NULL,
                    response TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    feedback TEXT DEFAULT NULL,
                    response_time_ms INTEGER DEFAULT NULL,
                    retrieval_method TEXT DEFAULT NULL,
                    INDEX idx_user_timestamp (user_id, timestamp)
                )
            """)
            
            # Users table
            c.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    role TEXT NOT NULL,
                    uni_id TEXT,
                    email TEXT,
                    is_international INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    last_active TEXT,
                    message_count INTEGER DEFAULT 0
                )
            """)
            
            # Rate limiting table
            c.execute("""
                CREATE TABLE IF NOT EXISTS rate_limits (
                    user_id INTEGER PRIMARY KEY,
                    last_reset TEXT NOT NULL,
                    message_count INTEGER DEFAULT 0
                )
            """)
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    def generate_session_title(self, message: str) -> str:
        """Generate a session title from message"""
        words = message.split()[:5]
        title = " ".join(words)
        if len(message) > 50:
            title += "..."
        return title
    
    def save_conversation(
        self,
        user_id: int,
        username: str,
        message: str,
        response: str,
        session_title: Optional[str] = None,
        response_time_ms: Optional[int] = None,
        retrieval_method: Optional[str] = None
    ):
        """Save a conversation to the database"""
        with self.get_connection() as conn:
            c = conn.cursor()
            timestamp = datetime.now().isoformat()
            
            if not session_title:
                session_title = self.generate_session_title(message)
            
            c.execute("""
                INSERT INTO conversations
                (user_id, username, session_title, message, response, timestamp, 
                 response_time_ms, retrieval_method)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, session_title, message, response, 
                  timestamp, response_time_ms, retrieval_method))
            
            # Update user activity
            c.execute("""
                UPDATE users 
                SET last_active = ?, message_count = message_count + 1
                WHERE telegram_id = ?
            """, (timestamp, user_id))
            
            conn.commit()
            logger.debug(f"Saved conversation for user {user_id}")
    
    def get_chat_history(self, user_id: int, limit: int = 8) -> List[Tuple[str, str]]:
        """Get recent chat history for a user"""
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT message, response FROM conversations
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (user_id, limit))
            rows = c.fetchall()
            return list(reversed(rows))
    
    def search_similar_question(
        self, 
        user_id: int, 
        question: str
    ) -> Optional[Tuple[str, str, str]]:
        """Search for similar previous questions"""
        keywords = question.lower().split()[:3]
        
        with self.get_connection() as conn:
            c = conn.cursor()
            for kw in keywords:
                c.execute("""
                    SELECT message, response, timestamp
                    FROM conversations
                    WHERE user_id = ?
                      AND LOWER(message) LIKE ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (user_id, f"%{kw}%"))
                row = c.fetchone()
                if row:
                    return row
        
        return None
    
    def save_user(
        self,
        telegram_id: int,
        role: str,
        uni_id: Optional[str] = None,
        email: Optional[str] = None,
        is_international: int = 0
    ):
        """Save or update user information"""
        with self.get_connection() as conn:
            c = conn.cursor()
            timestamp = datetime.now().isoformat()
            
            c.execute("""
                INSERT OR REPLACE INTO users 
                (telegram_id, role, uni_id, email, is_international, created_at, last_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (telegram_id, role, uni_id, email, is_international, timestamp, timestamp))
            
            conn.commit()
            logger.info(f"Saved user {telegram_id} with role {role}")
    
    def get_user(self, telegram_id: int) -> Optional[Tuple]:
        """Get user information"""
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            return c.fetchone()
    
    def get_session_titles(self, user_id: int, limit: int = 10) -> List[Tuple[str, str]]:
        """Get session titles for a user"""
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT session_title, timestamp FROM conversations
                WHERE user_id = ?
                GROUP BY session_title
                ORDER BY timestamp DESC
                LIMIT ?
            """, (user_id, limit))
            return c.fetchall()
    
    def save_feedback(self, user_id: int, feedback: str):
        """Save feedback for the last conversation"""
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                UPDATE conversations 
                SET feedback = ? 
                WHERE id = (
                    SELECT MAX(id) FROM conversations WHERE user_id = ?
                )
            """, (feedback, user_id))
            conn.commit()
            logger.debug(f"Saved feedback for user {user_id}")
    
    # Rate limiting methods
    def check_rate_limit(self, user_id: int, max_messages: int, window_seconds: int) -> bool:
        """Check if user has exceeded rate limit"""
        with self.get_connection() as conn:
            c = conn.cursor()
            now = datetime.now()
            
            c.execute("""
                SELECT last_reset, message_count FROM rate_limits
                WHERE user_id = ?
            """, (user_id,))
            row = c.fetchone()
            
            if not row:
                # First message from this user
                c.execute("""
                    INSERT INTO rate_limits (user_id, last_reset, message_count)
                    VALUES (?, ?, 1)
                """, (user_id, now.isoformat()))
                conn.commit()
                return True
            
            last_reset_str, count = row
            last_reset = datetime.fromisoformat(last_reset_str)
            
            # Check if window has expired
            if (now - last_reset).total_seconds() > window_seconds:
                # Reset counter
                c.execute("""
                    UPDATE rate_limits 
                    SET last_reset = ?, message_count = 1
                    WHERE user_id = ?
                """, (now.isoformat(), user_id))
                conn.commit()
                return True
            
            # Check if within limit
            if count < max_messages:
                c.execute("""
                    UPDATE rate_limits 
                    SET message_count = message_count + 1
                    WHERE user_id = ?
                """, (user_id,))
                conn.commit()
                return True
            
            return False
    
    def get_stats(self) -> dict:
        """Get overall bot statistics"""
        with self.get_connection() as conn:
            c = conn.cursor()
            
            # Total users
            c.execute("SELECT COUNT(*) FROM users")
            total_users = c.fetchone()[0]
            
            # Total conversations
            c.execute("SELECT COUNT(*) FROM conversations")
            total_conversations = c.fetchone()[0]
            
            # Users by role
            c.execute("SELECT role, COUNT(*) FROM users GROUP BY role")
            users_by_role = dict(c.fetchall())
            
            # Feedback stats
            c.execute("""
                SELECT feedback, COUNT(*) FROM conversations 
                WHERE feedback IS NOT NULL 
                GROUP BY feedback
            """)
            feedback_stats = dict(c.fetchall())
            
            return {
                "total_users": total_users,
                "total_conversations": total_conversations,
                "users_by_role": users_by_role,
                "feedback_stats": feedback_stats
            }