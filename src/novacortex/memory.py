"""Short-term conversational memory per Telegram user."""

import asyncio
import logging
import sqlite3

from contextlib import closing
from datetime import datetime
from typing import List, Optional, Dict

from novacortex.config import DB_PATH
from novacortex.llm import llm_client

logger = logging.getLogger(__name__)

# ==================== SMART MEMORY SYSTEM ====================
class SmartMemorySystem:
    def __init__(self, client, max_messages=10, summary_interval=10):
        self.client = client
        self.max_messages = max_messages
        self.summary_interval = summary_interval
        self.db_path = str(DB_PATH)
    async def add_message(self, user_id: int, role: str, content: str, entity: str = None):
        with closing(sqlite3.connect(self.db_path)) as conn:
            c = conn.cursor()
            c.execute("SELECT MAX(message_index) FROM conversation_memory WHERE user_id = ?", (user_id,))
            last_index = c.fetchone()[0]
            new_index = (last_index + 1) if last_index is not None else 0
            content_with_entity = f"{content}|||entity:{entity}" if entity else content
            c.execute("INSERT INTO conversation_memory (user_id, message_index, role, content, timestamp, is_summary) VALUES (?, ?, ?, ?, ?, 0)",
                (user_id, new_index, role, content_with_entity, datetime.now().isoformat()))
            conn.commit()
        if new_index > 0 and new_index % self.summary_interval == 0:
            try:
                await self._compress_memory(user_id)
            except:
                pass
    def get_context(self, user_id: int, max_messages: Optional[int] = None) -> List[Dict]:
        max_msg = max_messages or self.max_messages
        with closing(sqlite3.connect(self.db_path)) as conn:
            c = conn.cursor()
            c.execute("SELECT role, content, is_summary FROM conversation_memory WHERE user_id = ? ORDER BY message_index DESC LIMIT ?",
                (user_id, max_msg))
            rows = c.fetchall()
            result = []
            for r, c_val, s in reversed(rows):
                entity = None
                content = c_val
                if "|||entity:" in c_val:
                    parts = c_val.split("|||entity:")
                    content = parts[0]
                    entity = parts[1] if len(parts) > 1 else None
                result.append({"role": r, "content": content, "is_summary": bool(s), "entity": entity})
            return result
    def format_context_for_llm(self, context: List[Dict]) -> str:
        formatted = []
        for msg in context:
            if msg["is_summary"]:
                formatted.append(msg["content"])
            else:
                role = "المستخدم" if msg["role"] == "user" else "المساعد"
                formatted.append(f"{role}: {msg['content']}")
        return "\n".join(formatted)
    async def _compress_memory(self, user_id: int):
        try:
            with closing(sqlite3.connect(self.db_path)) as conn:
                c = conn.cursor()
                c.execute("SELECT message_index, role, content FROM conversation_memory WHERE user_id = ? AND is_summary = 0 ORDER BY message_index ASC LIMIT ?",
                    (user_id, self.summary_interval))
                messages = c.fetchall()
                if len(messages) < 3:
                    return
                conversation_text = "\n".join([f"{'المستخدم' if r == 'user' else 'المساعد'}: {ct}" for _, r, ct in messages])
                summary = await self._generate_summary(conversation_text)
                if summary:
                    indices = [idx for idx, _, _ in messages]
                    placeholders = ','.join('?' * len(indices))
                    c.execute(f"DELETE FROM conversation_memory WHERE user_id = ? AND message_index IN ({placeholders})", (user_id, *indices))
                    c.execute("INSERT INTO conversation_memory (user_id, message_index, role, content, timestamp, is_summary) VALUES (?, ?, 'assistant', ?, ?, 1)",
                        (user_id, min(indices), summary, datetime.now().isoformat()))
                    conn.commit()
        except Exception as e:
            logger.error(f"Memory compression error: {e}")
    async def _generate_summary(self, conversation: str) -> Optional[str]:
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "لخص هذه المحادثة بإيجاز (100 كلمة كحد أقصى)."},
                    {"role": "user", "content": f"المحادثة:\n{conversation}"}
                ],
                temperature=0.3, max_tokens=200
            )
            return f"[ملخص]: {response.choices[0].message.content.strip()}"
        except:
            return None
    def clear_memory(self, user_id: int):
        with closing(sqlite3.connect(self.db_path)) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM conversation_memory WHERE user_id = ?", (user_id,))
            conn.commit()
memory_system = SmartMemorySystem(llm_client)
