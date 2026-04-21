"""
Conversation Manager — Full Session History & Analytics
Stores complete conversations, enables search, export (MD/JSON/TXT),
generates summaries, tracks topics and patterns.
"""

import json
import logging
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("synapse.conv")

CONV_DB = Path("./data/conversations.db")
CONV_DB.parent.mkdir(parents=True, exist_ok=True)

SUMMARY_SYSTEM = """Summarise this conversation in 2-3 sentences.
Identify: main topics discussed, key conclusions, any action items.
Be concise."""

TOPIC_SYSTEM = """Extract the main topics from this conversation.
Return ONLY a JSON array of 3-5 topic strings: ["topic1", "topic2", ...]"""


@dataclass
class Message:
    msg_id:     str
    session_id: str
    role:       str         # user | assistant
    content:    str
    agent_role: str = ""    # which AI agent (coder, architect, etc.)
    strategy:   str = ""    # meta-agent strategy used
    timestamp:  float = 0.0
    tokens_est: int = 0


@dataclass
class Session:
    session_id:  str
    title:       str
    created_at:  float
    updated_at:  float
    message_count: int
    topics:      List[str] = field(default_factory=list)
    summary:     str = ""
    total_tokens: int = 0


class ConversationManager:
    def __init__(self, llm):
        self.llm = llm
        self._db  = None
        self._init_db()

    # ── Init ──────────────────────────────────────────────────────────────────
    def _init_db(self):
        self._db = sqlite3.connect(str(CONV_DB), check_same_thread=False)
        self._db.execute("""CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY, title TEXT, created_at REAL,
            updated_at REAL, message_count INTEGER DEFAULT 0,
            topics TEXT DEFAULT '[]', summary TEXT DEFAULT '',
            total_tokens INTEGER DEFAULT 0)""")
        self._db.execute("""CREATE TABLE IF NOT EXISTS messages (
            msg_id TEXT PRIMARY KEY, session_id TEXT, role TEXT,
            content TEXT, agent_role TEXT DEFAULT '', strategy TEXT DEFAULT '',
            timestamp REAL, tokens_est INTEGER DEFAULT 0,
            FOREIGN KEY(session_id) REFERENCES sessions(session_id))""")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_ts ON messages(timestamp)")
        self._db.commit()
        count = self._db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        log.info(f"Conversation Manager: {count} sessions")

    # ── Save Message ──────────────────────────────────────────────────────────
    def save_message(
        self, session_id: str, role: str, content: str,
        agent_role: str = "", strategy: str = ""
    ) -> str:
        msg_id   = uuid.uuid4().hex[:12]
        tokens   = len(content.split())
        now      = time.time()

        # Auto-create session if needed
        self._ensure_session(session_id, content if role == "user" else "")

        self._db.execute(
            "INSERT INTO messages VALUES (?,?,?,?,?,?,?,?)",
            (msg_id, session_id, role, content,
             agent_role, strategy, now, tokens)
        )
        self._db.execute(
            """UPDATE sessions SET updated_at=?, message_count=message_count+1,
               total_tokens=total_tokens+? WHERE session_id=?""",
            (now, tokens, session_id)
        )
        self._db.commit()
        return msg_id

    # ── Get Session ───────────────────────────────────────────────────────────
    def get_session(self, session_id: str) -> Optional[Dict]:
        row = self._db.execute(
            "SELECT * FROM sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_session(row)

    def get_messages(
        self, session_id: str, limit: int = 100, offset: int = 0
    ) -> List[Dict]:
        rows = self._db.execute(
            "SELECT * FROM messages WHERE session_id=? ORDER BY timestamp ASC LIMIT ? OFFSET ?",
            (session_id, limit, offset)
        ).fetchall()
        return [self._row_to_message(r) for r in rows]

    def list_sessions(
        self, limit: int = 50, offset: int = 0,
        search: str = ""
    ) -> List[Dict]:
        if search:
            rows = self._db.execute(
                """SELECT s.* FROM sessions s
                   JOIN messages m ON s.session_id=m.session_id
                   WHERE LOWER(m.content) LIKE ?
                   GROUP BY s.session_id
                   ORDER BY s.updated_at DESC LIMIT ? OFFSET ?""",
                (f"%{search.lower()}%", limit, offset)
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
        return [self._row_to_session(r) for r in rows]

    # ── Search across all messages ────────────────────────────────────────────
    def search_messages(self, query: str, limit: int = 20) -> List[Dict]:
        words = [f"%{w.lower()}%" for w in query.split() if len(w) > 2]
        if not words:
            return []
        conds = " OR ".join("LOWER(content) LIKE ?" for _ in words)
        rows  = self._db.execute(
            f"SELECT * FROM messages WHERE {conds} ORDER BY timestamp DESC LIMIT ?",
            words + [limit]
        ).fetchall()
        return [self._row_to_message(r) for r in rows]

    # ── Generate Summary ──────────────────────────────────────────────────────
    async def summarise_session(self, session_id: str) -> Dict:
        messages = self.get_messages(session_id, limit=30)
        if not messages:
            return {"success": False, "error": "Session not found or empty"}

        conv_text = "\n".join(
            f"{m['role'].upper()}: {m['content'][:300]}" for m in messages[:20]
        )

        summary = await self.llm.complete(
            f"Conversation:\n{conv_text}\n\nSummarise:",
            role="general", system=SUMMARY_SYSTEM, temperature=0.3
        )

        topics_raw = await self.llm.complete(
            f"Conversation:\n{conv_text[:1500]}\n\nExtract topics:",
            role="general", system=TOPIC_SYSTEM, temperature=0.2
        )
        try:
            topics_raw = re.sub(r"```json|```", "", topics_raw).strip()
            topics = json.loads(topics_raw)
        except Exception:
            topics = []

        # Generate a title if session title is generic
        title = summary[:60] + "…" if len(summary) > 60 else summary

        self._db.execute(
            "UPDATE sessions SET summary=?, topics=?, title=? WHERE session_id=?",
            (summary, json.dumps(topics), title, session_id)
        )
        self._db.commit()
        return {"success": True, "summary": summary, "topics": topics, "title": title}

    # ── Export ────────────────────────────────────────────────────────────────
    def export_session(self, session_id: str, fmt: str = "markdown") -> Optional[str]:
        session  = self.get_session(session_id)
        messages = self.get_messages(session_id)
        if not session or not messages:
            return None

        if fmt == "markdown":
            return self._export_markdown(session, messages)
        elif fmt == "json":
            return json.dumps(
                {"session": session, "messages": messages}, indent=2
            )
        elif fmt == "text":
            return self._export_text(session, messages)
        return None

    def _export_markdown(self, session: Dict, messages: List[Dict]) -> str:
        lines = [
            f"# {session['title']}",
            f"*Session: {session['session_id']}*",
            f"*Created: {self._fmt_time(session['created_at'])}*",
            f"*Messages: {session['message_count']}*",
        ]
        if session.get("summary"):
            lines += ["", "## Summary", session["summary"]]
        if session.get("topics"):
            lines += ["", "**Topics:** " + ", ".join(session["topics"])]
        lines.append("\n---\n")

        for msg in messages:
            role = "**You**" if msg["role"] == "user" else f"**◈ Synapse ({msg.get('agent_role','AI')})**"
            time_str = self._fmt_time(msg["timestamp"])
            lines.append(f"{role} *{time_str}*\n")
            lines.append(msg["content"])
            lines.append("\n---\n")
        return "\n".join(lines)

    def _export_text(self, session: Dict, messages: List[Dict]) -> str:
        lines = [f"=== {session['title']} ===\n"]
        for msg in messages:
            role = "YOU" if msg["role"] == "user" else "AI"
            lines.append(f"[{role}] {self._fmt_time(msg['timestamp'])}")
            lines.append(msg["content"])
            lines.append("")
        return "\n".join(lines)

    # ── Analytics ─────────────────────────────────────────────────────────────
    def analytics(self) -> Dict:
        total_sessions = self._db.execute(
            "SELECT COUNT(*) FROM sessions"
        ).fetchone()[0]
        total_messages = self._db.execute(
            "SELECT COUNT(*) FROM messages"
        ).fetchone()[0]
        total_tokens = self._db.execute(
            "SELECT SUM(total_tokens) FROM sessions"
        ).fetchone()[0] or 0
        most_active = self._db.execute(
            """SELECT session_id, message_count FROM sessions
               ORDER BY message_count DESC LIMIT 3"""
        ).fetchall()
        agent_usage = self._db.execute(
            """SELECT agent_role, COUNT(*) as cnt FROM messages
               WHERE agent_role != '' GROUP BY agent_role
               ORDER BY cnt DESC"""
        ).fetchall()
        recent_topics = []
        rows = self._db.execute(
            "SELECT topics FROM sessions WHERE topics != '[]' ORDER BY updated_at DESC LIMIT 10"
        ).fetchall()
        for r in rows:
            try:
                recent_topics.extend(json.loads(r[0]))
            except Exception:
                pass

        return {
            "total_sessions":  total_sessions,
            "total_messages":  total_messages,
            "total_tokens_est": total_tokens,
            "most_active":     [{"session_id": r[0], "messages": r[1]} for r in most_active],
            "agent_usage":     [{"agent": r[0], "count": r[1]} for r in agent_usage],
            "recent_topics":   list(dict.fromkeys(recent_topics))[:10],
        }

    # ── Delete ────────────────────────────────────────────────────────────────
    def delete_session(self, session_id: str) -> bool:
        self._db.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
        cur = self._db.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
        self._db.commit()
        return cur.rowcount > 0

    def clear_all(self):
        self._db.execute("DELETE FROM messages")
        self._db.execute("DELETE FROM sessions")
        self._db.commit()

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _ensure_session(self, session_id: str, first_message: str = ""):
        exists = self._db.execute(
            "SELECT 1 FROM sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if not exists:
            title = (first_message[:60] + "…") if len(first_message) > 60 else first_message
            title = title or f"Session {session_id[-8:]}"
            now   = time.time()
            self._db.execute(
                "INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?)",
                (session_id, title, now, now, 0, "[]", "", 0)
            )
            self._db.commit()

    def _row_to_session(self, row) -> Dict:
        topics = []
        try:
            topics = json.loads(row[5] or "[]")
        except Exception:
            pass
        return {"session_id": row[0], "title": row[1],
                "created_at": row[2], "updated_at": row[3],
                "message_count": row[4], "topics": topics,
                "summary": row[6], "total_tokens": row[7]}

    def _row_to_message(self, row) -> Dict:
        return {"msg_id": row[0], "session_id": row[1], "role": row[2],
                "content": row[3], "agent_role": row[4], "strategy": row[5],
                "timestamp": row[6], "tokens_est": row[7]}

    def _fmt_time(self, ts: float) -> str:
        import datetime
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
