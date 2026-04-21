"""
Prompt Library — Reusable Prompt Template Manager
Store, version, tag, and inject prompt templates.
Templates support {{variable}} substitution.
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

log = logging.getLogger("synapse.prompts")

PROMPTS_DB = Path("./data/prompt_library.db")
PROMPTS_DB.parent.mkdir(parents=True, exist_ok=True)

GENERATOR_SYSTEM = """You are a prompt engineering expert.
Create an optimised, reusable prompt template for the given use case.
The template should:
- Be clear and specific
- Use {{variable_name}} for dynamic parts
- Include context about the AI role
- Have clear output format requirements
- Be production-ready

Return ONLY the prompt template text, no explanation."""

IMPROVE_SYSTEM = """You are a prompt optimisation expert.
Improve the given prompt template to be:
- More specific and actionable
- Better structured
- Include better output format instructions
- More robust to edge cases

Return ONLY the improved template."""

# Built-in system templates
BUILTIN_TEMPLATES = [
    {
        "name": "Code Review",
        "category": "coding",
        "tags": ["review", "code", "quality"],
        "template": "Review this {{language}} code:\n```\n{{code}}\n```\nCheck for: bugs, security issues, performance problems, style issues. Format: numbered list with severity (High/Medium/Low).",
        "variables": ["language", "code"],
        "description": "Thorough code review with severity ratings",
    },
    {
        "name": "Bug Analysis",
        "category": "coding",
        "tags": ["debug", "bug", "error"],
        "template": "Debug this {{language}} error:\nError: {{error_message}}\nCode:\n```\n{{code}}\n```\nProvide: root cause, fix, and prevention strategy.",
        "variables": ["language", "error_message", "code"],
        "description": "Root cause analysis and fix for bugs",
    },
    {
        "name": "Documentation Writer",
        "category": "writing",
        "tags": ["docs", "markdown", "api"],
        "template": "Write comprehensive documentation for:\n{{subject}}\n\nInclude: overview, parameters/inputs, examples, edge cases, returns/outputs. Format: Markdown with clear headers.",
        "variables": ["subject"],
        "description": "Generate technical documentation",
    },
    {
        "name": "Explain Like I'm 5",
        "category": "education",
        "tags": ["explain", "simple", "beginner"],
        "template": "Explain {{concept}} to a complete beginner with no technical background. Use: simple words, real-world analogies, 3 concrete examples. Max 200 words.",
        "variables": ["concept"],
        "description": "Simplify complex topics for beginners",
    },
    {
        "name": "Structured Data Extractor",
        "category": "data",
        "tags": ["extract", "json", "parse"],
        "template": "Extract structured data from this text:\n\n{{text}}\n\nReturn ONLY valid JSON with these fields: {{fields}}. No markdown, no explanation.",
        "variables": ["text", "fields"],
        "description": "Extract structured JSON from unstructured text",
    },
    {
        "name": "System Design",
        "category": "architecture",
        "tags": ["design", "architecture", "system"],
        "template": "Design a system for: {{requirement}}\nScale: {{scale}} users\nConstraints: {{constraints}}\n\nProvide: architecture diagram (ASCII), components, data flow, tech choices with reasoning, trade-offs.",
        "variables": ["requirement", "scale", "constraints"],
        "description": "System architecture design template",
    },
    {
        "name": "Test Case Generator",
        "category": "testing",
        "tags": ["test", "unit", "tdd"],
        "template": "Generate comprehensive {{test_framework}} test cases for:\n```{{language}}\n{{function_code}}\n```\nCover: happy path, edge cases, error cases, boundary values. Include docstrings.",
        "variables": ["test_framework", "language", "function_code"],
        "description": "Generate thorough test suites",
    },
    {
        "name": "Meeting Notes Formatter",
        "category": "productivity",
        "tags": ["meeting", "notes", "summary"],
        "template": "Format these meeting notes into a structured summary:\n\n{{raw_notes}}\n\nOutput sections: Attendees, Key Decisions, Action Items (with owner + deadline), Next Steps, Open Questions.",
        "variables": ["raw_notes"],
        "description": "Structure raw meeting notes",
    },
]


@dataclass
class PromptTemplate:
    template_id: str
    name:        str
    category:    str
    tags:        List[str]
    template:    str
    variables:   List[str]
    description: str
    created_at:  float
    updated_at:  float
    use_count:   int = 0
    rating:      float = 0.0
    is_builtin:  bool = False
    version:     int = 1


class PromptLibrary:
    def __init__(self, llm):
        self.llm = llm
        self._db  = None
        self._init_db()

    def _init_db(self):
        self._db = sqlite3.connect(str(PROMPTS_DB), check_same_thread=False)
        self._db.execute("""CREATE TABLE IF NOT EXISTS templates (
            template_id TEXT PRIMARY KEY, name TEXT, category TEXT,
            tags TEXT DEFAULT '[]', template TEXT, variables TEXT DEFAULT '[]',
            description TEXT, created_at REAL, updated_at REAL,
            use_count INTEGER DEFAULT 0, rating REAL DEFAULT 0.0,
            is_builtin INTEGER DEFAULT 0, version INTEGER DEFAULT 1)""")
        self._db.execute("""CREATE TABLE IF NOT EXISTS template_history (
            history_id TEXT PRIMARY KEY, template_id TEXT,
            template TEXT, version INTEGER, created_at REAL)""")
        self._db.commit()

        # Seed builtins if empty
        count = self._db.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
        if count == 0:
            self._seed_builtins()
        log.info(f"Prompt Library: {self._db.execute('SELECT COUNT(*) FROM templates').fetchone()[0]} templates")

    def _seed_builtins(self):
        now = time.time()
        for t in BUILTIN_TEMPLATES:
            tid = uuid.uuid4().hex[:10]
            self._db.execute(
                "INSERT INTO templates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (tid, t["name"], t["category"], json.dumps(t["tags"]),
                 t["template"], json.dumps(t["variables"]), t["description"],
                 now, now, 0, 0.0, 1, 1)
            )
        self._db.commit()
        log.info(f"Seeded {len(BUILTIN_TEMPLATES)} builtin templates")

    # ── CRUD ──────────────────────────────────────────────────────────────────
    def create(
        self, name: str, template: str, category: str = "general",
        tags: List[str] = None, description: str = "",
        variables: List[str] = None
    ) -> PromptTemplate:
        tid  = uuid.uuid4().hex[:10]
        now  = time.time()
        vars_ = variables or self._extract_variables(template)
        self._db.execute(
            "INSERT INTO templates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tid, name, category, json.dumps(tags or []), template,
             json.dumps(vars_), description, now, now, 0, 0.0, 0, 1)
        )
        self._db.commit()
        return self.get(tid)

    def get(self, template_id: str) -> Optional[PromptTemplate]:
        row = self._db.execute(
            "SELECT * FROM templates WHERE template_id=?", (template_id,)
        ).fetchone()
        return self._row_to_template(row) if row else None

    def list(
        self, category: str = "", search: str = "",
        limit: int = 50
    ) -> List[Dict]:
        if search:
            rows = self._db.execute(
                "SELECT * FROM templates WHERE LOWER(name) LIKE ? OR LOWER(description) LIKE ? OR LOWER(tags) LIKE ? ORDER BY use_count DESC LIMIT ?",
                (f"%{search.lower()}%",) * 3 + (limit,)
            ).fetchall()
        elif category:
            rows = self._db.execute(
                "SELECT * FROM templates WHERE category=? ORDER BY use_count DESC LIMIT ?",
                (category, limit)
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT * FROM templates ORDER BY use_count DESC LIMIT ?", (limit,)
            ).fetchall()
        return [asdict(self._row_to_template(r)) for r in rows]

    def update(
        self, template_id: str, template: str,
        **kwargs
    ) -> bool:
        existing = self.get(template_id)
        if not existing:
            return False

        # Save to history
        self._db.execute(
            "INSERT INTO template_history VALUES (?,?,?,?,?)",
            (uuid.uuid4().hex[:10], template_id,
             existing.template, existing.version, time.time())
        )

        now       = time.time()
        new_ver   = existing.version + 1
        vars_     = self._extract_variables(template)
        allowed   = {"name", "category", "tags", "description"}
        updates   = {k: v for k, v in kwargs.items() if k in allowed}
        if isinstance(updates.get("tags"), list):
            updates["tags"] = json.dumps(updates["tags"])

        sets   = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values())

        query = f"UPDATE templates SET template=?, variables=?, updated_at=?, version=?{', ' + sets if sets else ''} WHERE template_id=?"
        self._db.execute(query, [template, json.dumps(vars_), now, new_ver] + values + [template_id])
        self._db.commit()
        return True

    def delete(self, template_id: str) -> bool:
        t = self.get(template_id)
        if t and t.is_builtin:
            return False  # Cannot delete builtins
        cur = self._db.execute("DELETE FROM templates WHERE template_id=?", (template_id,))
        self._db.commit()
        return cur.rowcount > 0

    # ── Apply Template ────────────────────────────────────────────────────────
    def apply(self, template_id: str, variables: Dict[str, str]) -> Optional[str]:
        """Substitute variables and return ready-to-use prompt."""
        t = self.get(template_id)
        if not t:
            return None
        result = t.template
        for var, val in variables.items():
            result = result.replace(f"{{{{{var}}}}}", str(val))

        # Track usage
        self._db.execute(
            "UPDATE templates SET use_count=use_count+1 WHERE template_id=?",
            (template_id,)
        )
        self._db.commit()
        return result

    def rate(self, template_id: str, rating: float) -> bool:
        rating = max(0.0, min(10.0, float(rating)))
        self._db.execute(
            "UPDATE templates SET rating=? WHERE template_id=?", (rating, template_id)
        )
        self._db.commit()
        return True

    # ── AI-Powered Template Generation ───────────────────────────────────────
    async def generate(
        self, use_case: str, category: str = "general", example: str = ""
    ) -> PromptTemplate:
        """Let AI write an optimised prompt template."""
        prompt = (
            f"Use case: {use_case}\n"
            f"Category: {category}\n"
            + (f"Example input: {example}\n" if example else "")
            + "\nWrite an optimised reusable prompt template:"
        )
        template_text = await self.llm.complete(
            prompt, role="general", system=GENERATOR_SYSTEM, temperature=0.4
        )
        template_text = template_text.strip()
        vars_  = self._extract_variables(template_text)
        name   = use_case[:50]

        return self.create(
            name=name, template=template_text,
            category=category, description=f"AI-generated template for: {use_case}",
            variables=vars_,
        )

    async def improve(self, template_id: str) -> Optional[str]:
        """AI improves an existing template."""
        t = self.get(template_id)
        if not t:
            return None
        improved = await self.llm.complete(
            f"Improve this prompt template:\n\n{t.template}",
            role="general", system=IMPROVE_SYSTEM, temperature=0.3
        )
        improved = improved.strip()
        self.update(template_id, improved)
        return improved

    # ── Categories & Stats ────────────────────────────────────────────────────
    def categories(self) -> List[str]:
        rows = self._db.execute(
            "SELECT DISTINCT category FROM templates ORDER BY category"
        ).fetchall()
        return [r[0] for r in rows]

    def stats(self) -> Dict:
        total = self._db.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
        cats  = self._db.execute("SELECT COUNT(DISTINCT category) FROM templates").fetchone()[0]
        top   = self._db.execute(
            "SELECT name, use_count FROM templates ORDER BY use_count DESC LIMIT 5"
        ).fetchall()
        return {
            "total": total, "categories": cats,
            "top_used": [{"name": r[0], "uses": r[1]} for r in top],
        }

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _extract_variables(self, template: str) -> List[str]:
        return list(dict.fromkeys(re.findall(r"\{\{(\w+)\}\}", template)))

    def _row_to_template(self, row) -> PromptTemplate:
        return PromptTemplate(
            template_id=row[0], name=row[1], category=row[2],
            tags=json.loads(row[3] or "[]"), template=row[4],
            variables=json.loads(row[5] or "[]"), description=row[6],
            created_at=row[7], updated_at=row[8],
            use_count=row[9], rating=float(row[10] or 0),
            is_builtin=bool(row[11]), version=row[12] or 1,
        )
