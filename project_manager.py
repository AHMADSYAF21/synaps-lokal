"""
Project Manager — Workspace Organiser
Projects group: conversations, files, tasks, notes, and AI context.
The AI operates within a project context — giving more relevant responses.
"""

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("synapse.projects")

PROJECTS_DB  = Path("./data/projects.db")
PROJECTS_DIR = Path("./data/project_files")
PROJECTS_DB.parent.mkdir(parents=True, exist_ok=True)
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

STATUS = ["active", "paused", "completed", "archived"]


@dataclass
class Task:
    task_id:    str
    project_id: str
    title:      str
    description: str
    status:     str    # todo | in_progress | done | blocked
    priority:   int    # 1-5 (5 = highest)
    created_at: float
    updated_at: float
    done_at:    Optional[float] = None
    agent_role: str = ""


@dataclass
class Project:
    project_id:  str
    name:        str
    description: str
    status:      str
    tech_stack:  List[str]
    goals:       List[str]
    ai_context:  str          # injected into AI prompts for this project
    created_at:  float
    updated_at:  float
    task_count:  int = 0
    file_count:  int = 0
    session_ids: List[str] = field(default_factory=list)


class ProjectManager:
    def __init__(self):
        self._db = None
        self._init_db()

    def _init_db(self):
        self._db = sqlite3.connect(str(PROJECTS_DB), check_same_thread=False)
        self._db.execute("""CREATE TABLE IF NOT EXISTS projects (
            project_id TEXT PRIMARY KEY, name TEXT, description TEXT,
            status TEXT DEFAULT 'active', tech_stack TEXT DEFAULT '[]',
            goals TEXT DEFAULT '[]', ai_context TEXT DEFAULT '',
            created_at REAL, updated_at REAL,
            task_count INTEGER DEFAULT 0, file_count INTEGER DEFAULT 0,
            session_ids TEXT DEFAULT '[]')""")
        self._db.execute("""CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY, project_id TEXT, title TEXT,
            description TEXT DEFAULT '', status TEXT DEFAULT 'todo',
            priority INTEGER DEFAULT 3, created_at REAL, updated_at REAL,
            done_at REAL, agent_role TEXT DEFAULT '',
            FOREIGN KEY(project_id) REFERENCES projects(project_id))""")
        self._db.execute("""CREATE TABLE IF NOT EXISTS notes (
            note_id TEXT PRIMARY KEY, project_id TEXT, title TEXT,
            content TEXT, created_at REAL, updated_at REAL)""")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_proj_tasks ON tasks(project_id)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_proj_notes ON notes(project_id)")
        self._db.commit()
        count = self._db.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        log.info(f"Project Manager: {count} projects")

    # ── Projects CRUD ─────────────────────────────────────────────────────────
    def create_project(
        self, name: str, description: str = "",
        tech_stack: List[str] = None, goals: List[str] = None,
        ai_context: str = ""
    ) -> Project:
        pid  = uuid.uuid4().hex[:12]
        now  = time.time()
        tech = tech_stack or []
        goal = goals or []
        self._db.execute(
            "INSERT INTO projects VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid, name, description, "active",
             json.dumps(tech), json.dumps(goal), ai_context,
             now, now, 0, 0, "[]")
        )
        self._db.commit()
        # Create project directory
        (PROJECTS_DIR / pid).mkdir(exist_ok=True)
        log.info(f"Created project: {name} ({pid})")
        return self.get_project(pid)

    def get_project(self, project_id: str) -> Optional[Project]:
        row = self._db.execute(
            "SELECT * FROM projects WHERE project_id=?", (project_id,)
        ).fetchone()
        return self._row_to_project(row) if row else None

    def list_projects(self, status: str = "") -> List[Dict]:
        if status:
            rows = self._db.execute(
                "SELECT * FROM projects WHERE status=? ORDER BY updated_at DESC", (status,)
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT * FROM projects ORDER BY updated_at DESC"
            ).fetchall()
        return [asdict(self._row_to_project(r)) for r in rows]

    def update_project(self, project_id: str, **kwargs) -> bool:
        allowed = {"name", "description", "status", "tech_stack", "goals", "ai_context"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        # JSON-encode lists
        for k in ("tech_stack", "goals", "session_ids"):
            if k in updates and isinstance(updates[k], list):
                updates[k] = json.dumps(updates[k])
        updates["updated_at"] = time.time()
        sets   = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [project_id]
        self._db.execute(f"UPDATE projects SET {sets} WHERE project_id=?", values)
        self._db.commit()
        return True

    def delete_project(self, project_id: str) -> bool:
        self._db.execute("DELETE FROM tasks WHERE project_id=?", (project_id,))
        self._db.execute("DELETE FROM notes WHERE project_id=?", (project_id,))
        cur = self._db.execute("DELETE FROM projects WHERE project_id=?", (project_id,))
        self._db.commit()
        # Remove files
        import shutil
        proj_dir = PROJECTS_DIR / project_id
        if proj_dir.exists():
            shutil.rmtree(proj_dir)
        return cur.rowcount > 0

    # ── Tasks ─────────────────────────────────────────────────────────────────
    def add_task(
        self, project_id: str, title: str,
        description: str = "", priority: int = 3,
        agent_role: str = ""
    ) -> Task:
        tid = uuid.uuid4().hex[:10]
        now = time.time()
        self._db.execute(
            "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?)",
            (tid, project_id, title, description, "todo", priority, now, now, None, agent_role)
        )
        self._db.execute(
            "UPDATE projects SET task_count=task_count+1, updated_at=? WHERE project_id=?",
            (now, project_id)
        )
        self._db.commit()
        return self.get_task(tid)

    def get_task(self, task_id: str) -> Optional[Task]:
        row = self._db.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        return self._row_to_task(row) if row else None

    def list_tasks(
        self, project_id: str, status: str = ""
    ) -> List[Dict]:
        if status:
            rows = self._db.execute(
                "SELECT * FROM tasks WHERE project_id=? AND status=? ORDER BY priority DESC, created_at",
                (project_id, status)
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT * FROM tasks WHERE project_id=? ORDER BY priority DESC, created_at",
                (project_id,)
            ).fetchall()
        return [asdict(self._row_to_task(r)) for r in rows]

    def update_task(self, task_id: str, **kwargs) -> bool:
        allowed = {"title", "description", "status", "priority", "agent_role"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        now = time.time()
        updates["updated_at"] = now
        if updates.get("status") == "done":
            updates["done_at"] = now
        sets   = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [task_id]
        self._db.execute(f"UPDATE tasks SET {sets} WHERE task_id=?", values)
        self._db.commit()
        return True

    def delete_task(self, task_id: str) -> bool:
        task = self.get_task(task_id)
        if task:
            self._db.execute("UPDATE projects SET task_count=MAX(0,task_count-1) WHERE project_id=?",
                             (task.project_id,))
        cur = self._db.execute("DELETE FROM tasks WHERE task_id=?", (task_id,))
        self._db.commit()
        return cur.rowcount > 0

    # ── Notes ─────────────────────────────────────────────────────────────────
    def add_note(self, project_id: str, title: str, content: str) -> Dict:
        nid = uuid.uuid4().hex[:10]
        now = time.time()
        self._db.execute(
            "INSERT INTO notes VALUES (?,?,?,?,?,?)",
            (nid, project_id, title, content, now, now)
        )
        self._db.commit()
        return {"note_id": nid, "title": title, "content": content, "created_at": now}

    def list_notes(self, project_id: str) -> List[Dict]:
        rows = self._db.execute(
            "SELECT * FROM notes WHERE project_id=? ORDER BY updated_at DESC",
            (project_id,)
        ).fetchall()
        return [{"note_id": r[0], "project_id": r[1], "title": r[2],
                 "content": r[3], "created_at": r[4], "updated_at": r[5]}
                for r in rows]

    # ── Files ─────────────────────────────────────────────────────────────────
    def save_file(self, project_id: str, filename: str, content: bytes) -> Dict:
        proj_dir = PROJECTS_DIR / project_id
        proj_dir.mkdir(exist_ok=True)
        # Sanitize filename
        safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ")[:100]
        file_path = proj_dir / safe_name
        file_path.write_bytes(content)
        self._db.execute(
            "UPDATE projects SET file_count=file_count+1 WHERE project_id=?", (project_id,)
        )
        self._db.commit()
        return {"filename": safe_name, "size": len(content), "path": str(file_path)}

    def list_files(self, project_id: str) -> List[Dict]:
        proj_dir = PROJECTS_DIR / project_id
        if not proj_dir.exists():
            return []
        return [
            {"name": f.name, "size": f.stat().st_size,
             "modified": f.stat().st_mtime}
            for f in sorted(proj_dir.iterdir()) if f.is_file()
        ]

    def read_file(self, project_id: str, filename: str) -> Optional[bytes]:
        safe = "".join(c for c in filename if c.isalnum() or c in "._- ")[:100]
        path = PROJECTS_DIR / project_id / safe
        return path.read_bytes() if path.exists() else None

    # ── AI Context ────────────────────────────────────────────────────────────
    def get_ai_context(self, project_id: str) -> str:
        """Build a context string to inject into AI prompts for this project."""
        proj = self.get_project(project_id)
        if not proj:
            return ""
        tasks = self.list_tasks(project_id, status="todo")[:5]
        task_list = "\n".join(f"- [{t['priority']}★] {t['title']}" for t in tasks)
        return (
            f"[PROJECT CONTEXT: {proj.name}]\n"
            f"Description: {proj.description}\n"
            f"Tech stack: {', '.join(proj.tech_stack)}\n"
            f"Goals: {', '.join(proj.goals[:3])}\n"
            + (f"Pending tasks:\n{task_list}\n" if tasks else "")
            + (f"\nSpecific context: {proj.ai_context}" if proj.ai_context else "")
        )

    # ── Stats ─────────────────────────────────────────────────────────────────
    def stats(self) -> Dict:
        total   = self._db.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        active  = self._db.execute("SELECT COUNT(*) FROM projects WHERE status='active'").fetchone()[0]
        tasks   = self._db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        done    = self._db.execute("SELECT COUNT(*) FROM tasks WHERE status='done'").fetchone()[0]
        return {"total_projects": total, "active": active,
                "total_tasks": tasks, "tasks_done": done}

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _row_to_project(self, row) -> Project:
        return Project(
            project_id=row[0], name=row[1], description=row[2], status=row[3],
            tech_stack=json.loads(row[4] or "[]"),
            goals=json.loads(row[5] or "[]"),
            ai_context=row[6] or "", created_at=row[7], updated_at=row[8],
            task_count=row[9], file_count=row[10],
            session_ids=json.loads(row[11] or "[]"),
        )

    def _row_to_task(self, row) -> Task:
        return Task(
            task_id=row[0], project_id=row[1], title=row[2],
            description=row[3], status=row[4], priority=row[5],
            created_at=row[6], updated_at=row[7], done_at=row[8], agent_role=row[9],
        )
