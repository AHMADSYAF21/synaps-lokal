"""
Skill Library — Persistent Knowledge & Pattern Storage
AI learns reusable skills from successful interactions.
Skills stored in SQLite + ChromaDB for semantic retrieval.
"""
import json, logging, re, sqlite3, time, uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("synapse.skills")

DB_PATH = Path("./data/skills.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SKILL_EXTRACTOR_SYSTEM = """You are a skill extraction engine.
Given a successful AI interaction, extract a reusable skill/pattern.
Return ONLY valid JSON — no markdown, no explanation:
{
  "skill_name": "snake_case_name",
  "skill_type": "code_pattern|reasoning_pattern|domain_knowledge|workflow",
  "description": "what this skill does in one sentence",
  "tags": ["tag1","tag2"],
  "reusable_pattern": "the generalizable pattern or template",
  "example_application": "when to apply this skill",
  "confidence": 0.0
}
Only extract if confidence > 0.7 and pattern is genuinely reusable."""

KNOWLEDGE_DISTILL_SYSTEM = """You are a knowledge distillation engine.
Summarize key facts, rules, and principles from interactions.
Return ONLY valid JSON — no markdown, no explanation:
{
  "topic": "topic name",
  "facts": ["fact1","fact2"],
  "rules": ["rule1","rule2"],
  "gotchas": ["gotcha1"],
  "best_practices": ["practice1"]
}"""


@dataclass
class Skill:
    id: str
    name: str
    skill_type: str
    description: str
    tags: List[str]
    reusable_pattern: str
    example_application: str
    confidence: float
    use_count: int
    created_at: float
    last_used: float
    source_session: str = ""


class SkillLibrary:
    def __init__(self, llm, memory):
        self.llm    = llm
        self.memory = memory
        self._db    = None
        self._init_db()

    # ── Init ──────────────────────────────────────────────────────────────────
    def _init_db(self):
        self._db = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self._db.execute("""CREATE TABLE IF NOT EXISTS skills (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, skill_type TEXT,
            description TEXT, tags TEXT, reusable_pattern TEXT,
            example_application TEXT, confidence REAL DEFAULT 0.0,
            use_count INTEGER DEFAULT 0, created_at REAL,
            last_used REAL, source_session TEXT)""")
        self._db.execute("""CREATE TABLE IF NOT EXISTS knowledge (
            id TEXT PRIMARY KEY, topic TEXT, facts TEXT, rules TEXT,
            gotchas TEXT, best_practices TEXT,
            created_at REAL, interaction_count INTEGER DEFAULT 1)""")
        self._db.execute("""CREATE TABLE IF NOT EXISTS interaction_log (
            id TEXT PRIMARY KEY, session_id TEXT, task TEXT,
            response TEXT, agent_role TEXT, score REAL DEFAULT 0,
            created_at REAL)""")
        self._db.commit()
        count = self._db.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
        log.info(f"Skill Library: {count} skills loaded")

    # ── Learn from Interaction ────────────────────────────────────────────────
    async def learn_from_interaction(self, task: str, response: str,
                                     agent_role: str = "general", score: float = 0.0,
                                     session_id: str = "default") -> Optional[Skill]:
        if score < 6.0:
            return None

        # Log interaction synchronously (fast, no need for executor)
        self._db.execute(
            "INSERT INTO interaction_log VALUES (?,?,?,?,?,?,?)",
            (uuid.uuid4().hex, session_id, task[:500], response[:2000],
             agent_role, score, time.time()),
        )
        self._db.commit()

        # Extract skill via LLM
        skill_data = await self._extract_skill(task, response)
        if not skill_data or skill_data.get("confidence", 0) < 0.7:
            return None

        skill = Skill(
            id=uuid.uuid4().hex,
            name=skill_data.get("skill_name", "unnamed"),
            skill_type=skill_data.get("skill_type", "general"),
            description=skill_data.get("description", ""),
            tags=skill_data.get("tags", []),
            reusable_pattern=skill_data.get("reusable_pattern", ""),
            example_application=skill_data.get("example_application", ""),
            confidence=float(skill_data.get("confidence", 0.7)),
            use_count=0,
            created_at=time.time(),
            last_used=time.time(),
            source_session=session_id,
        )
        await self._save_skill(skill)
        log.info(f"Learned skill: {skill.name} ({skill.confidence:.2f})")
        return skill

    # ── Retrieve Relevant Skills ──────────────────────────────────────────────
    async def get_relevant_skills(self, task: str, n: int = 3) -> List[Skill]:
        skills: List[Skill] = []
        words = [w.lower() for w in task.split() if len(w) > 3]
        if words:
            placeholders = " OR ".join(
                "LOWER(name) LIKE ? OR LOWER(description) LIKE ?" for _ in words
            )
            values = [f"%{w}%" for w in words for _ in range(2)]
            rows = self._db.execute(
                f"SELECT * FROM skills WHERE ({placeholders}) "
                f"ORDER BY confidence DESC, use_count DESC LIMIT ?",
                values + [n],
            ).fetchall()
            skills = [self._row_to_skill(r) for r in rows]

        # Also semantic search in vector memory
        try:
            results = await self.memory.search(task, n=n, collection="knowledge")
            for r in results:
                if r.get("metadata", {}).get("type") == "skill":
                    sid = r["metadata"].get("skill_id", "")
                    row = self._db.execute("SELECT * FROM skills WHERE id=?", (sid,)).fetchone()
                    if row:
                        s = self._row_to_skill(row)
                        if not any(x.id == s.id for x in skills):
                            skills.append(s)
        except Exception as e:
            log.debug(f"Semantic skill search error: {e}")

        # Update use counts
        for s in skills[:n]:
            self._db.execute(
                "UPDATE skills SET use_count=use_count+1, last_used=? WHERE id=?",
                (time.time(), s.id),
            )
        self._db.commit()
        return skills[:n]

    def format_skills_for_prompt(self, skills: List[Skill]) -> str:
        if not skills:
            return ""
        lines = ["[RELEVANT SKILLS FROM LIBRARY]"]
        for s in skills:
            lines.append(f"\n--- Skill: {s.name} ---")
            lines.append(f"Pattern: {s.reusable_pattern}")
            lines.append(f"Apply when: {s.example_application}")
        return "\n".join(lines)

    # ── Distill Knowledge ─────────────────────────────────────────────────────
    async def distill_knowledge(self, topic: str, session_id: str = "default") -> Optional[Dict]:
        rows = self._db.execute(
            "SELECT task, response FROM interaction_log "
            "WHERE session_id=? ORDER BY created_at DESC LIMIT 20",
            (session_id,),
        ).fetchall()
        if len(rows) < 3:
            return None

        interactions = "\n\n".join(
            f"Task: {r[0]}\nResponse: {r[1][:500]}" for r in rows
        )
        raw = await self.llm.complete(
            f"Topic: {topic}\n\nInteractions:\n{interactions}",
            role="general", system=KNOWLEDGE_DISTILL_SYSTEM, temperature=0.3,
        )
        try:
            raw = re.sub(r"```json|```", "", raw).strip()
            knowledge = json.loads(raw)
            kid = uuid.uuid4().hex
            self._db.execute(
                "INSERT OR REPLACE INTO knowledge VALUES (?,?,?,?,?,?,?,?)",
                (kid, topic,
                 json.dumps(knowledge.get("facts", [])),
                 json.dumps(knowledge.get("rules", [])),
                 json.dumps(knowledge.get("gotchas", [])),
                 json.dumps(knowledge.get("best_practices", [])),
                 time.time(), len(rows)),
            )
            self._db.commit()
            summary = (
                f"Knowledge about {topic}: "
                + "; ".join(knowledge.get("facts", [])[:3])
            )
            await self.memory.save_knowledge(summary, topic=topic)
            log.info(f"Distilled knowledge: {topic}")
            return knowledge
        except Exception as e:
            log.error(f"Knowledge distill error: {e}")
            return None

    # ── List / Stats ──────────────────────────────────────────────────────────
    def list_skills(self, skill_type: str = None, limit: int = 50) -> List[Dict]:
        q, p = "SELECT * FROM skills", []
        if skill_type:
            q += " WHERE skill_type=?"; p.append(skill_type)
        q += " ORDER BY confidence DESC, use_count DESC LIMIT ?"
        p.append(limit)
        return [asdict(self._row_to_skill(r)) for r in self._db.execute(q, p).fetchall()]

    def get_knowledge(self, topic: str = None) -> List[Dict]:
        if topic:
            rows = self._db.execute(
                "SELECT * FROM knowledge WHERE topic LIKE ?", (f"%{topic}%",)
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT * FROM knowledge ORDER BY created_at DESC LIMIT 20"
            ).fetchall()
        return [{"id":r[0],"topic":r[1],
                 "facts":json.loads(r[2] or "[]"),
                 "rules":json.loads(r[3] or "[]"),
                 "gotchas":json.loads(r[4] or "[]"),
                 "best_practices":json.loads(r[5] or "[]"),
                 "created_at":r[6],"interaction_count":r[7]} for r in rows]

    def stats(self) -> Dict:
        skill_count = self._db.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
        knowledge_count = self._db.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
        interaction_count = self._db.execute("SELECT COUNT(*) FROM interaction_log").fetchone()[0]
        top = self._db.execute(
            "SELECT name,use_count FROM skills ORDER BY use_count DESC LIMIT 5"
        ).fetchall()
        return {
            "total_skills": skill_count,
            "knowledge_topics": knowledge_count,
            "total_interactions_logged": interaction_count,
            "top_skills": [{"name": r[0], "uses": r[1]} for r in top],
        }

    def delete_skill(self, skill_id: str) -> bool:
        cur = self._db.execute("DELETE FROM skills WHERE id=?", (skill_id,))
        self._db.commit()
        return cur.rowcount > 0

    # ── Private ───────────────────────────────────────────────────────────────
    async def _extract_skill(self, task: str, response: str) -> Optional[Dict]:
        raw = await self.llm.complete(
            f"Task:\n{task}\n\nResponse:\n{response[:2000]}",
            role="general", system=SKILL_EXTRACTOR_SYSTEM, temperature=0.3,
        )
        try:
            raw = re.sub(r"```json|```", "", raw).strip()
            return json.loads(raw)
        except Exception:
            return None

    async def _save_skill(self, skill: Skill):
        self._db.execute(
            "INSERT OR REPLACE INTO skills VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (skill.id, skill.name, skill.skill_type, skill.description,
             json.dumps(skill.tags), skill.reusable_pattern,
             skill.example_application, skill.confidence,
             skill.use_count, skill.created_at, skill.last_used,
             skill.source_session),
        )
        self._db.commit()
        # Index in vector memory for semantic search
        try:
            await self.memory.save(
                f"Skill: {skill.name}. {skill.description}. "
                f"Pattern: {skill.reusable_pattern}",
                {"type": "skill", "skill_name": skill.name, "skill_id": skill.id},
                collection="knowledge",
            )
        except Exception as e:
            log.debug(f"Skill vector index error: {e}")

    def _row_to_skill(self, row) -> Skill:
        return Skill(
            id=row[0], name=row[1], skill_type=row[2], description=row[3],
            tags=json.loads(row[4] or "[]"),
            reusable_pattern=row[5] or "",
            example_application=row[6] or "",
            confidence=float(row[7] or 0.0),
            use_count=int(row[8] or 0),
            created_at=float(row[9] or 0.0),
            last_used=float(row[10] or 0.0),
            source_session=row[11] or "",
        )
