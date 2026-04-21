"""
Knowledge Graph — Entity-Relationship Store
Extracts entities & relations from text, stores in SQLite graph DB,
supports graph traversal, path finding, and structured querying.
"""

import json
import logging
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

log = logging.getLogger("synapse.graph")

GRAPH_DB = Path("./data/knowledge_graph.db")
GRAPH_DB.parent.mkdir(parents=True, exist_ok=True)

EXTRACT_SYSTEM = """You are a knowledge extraction engine.
Extract entities and relationships from the given text.
Return ONLY valid JSON:
{
  "entities": [
    {"id": "unique_slug", "name": "Entity Name", "type": "person|org|concept|tech|place|event|other", "description": "brief desc"}
  ],
  "relations": [
    {"from": "entity_slug", "relation": "verb phrase", "to": "entity_slug", "weight": 1.0}
  ]
}
Extract meaningful, reusable facts. Use snake_case for IDs."""

QUERY_SYSTEM = """You are a knowledge graph query interpreter.
Given a user question and graph context, answer using the graph data.
Be specific about what the graph says vs what you're inferring."""


class KnowledgeGraph:
    def __init__(self, llm):
        self.llm = llm
        self._db  = None
        self._init_db()

    # ── Init ──────────────────────────────────────────────────────────────────
    def _init_db(self):
        self._db = sqlite3.connect(str(GRAPH_DB), check_same_thread=False)
        self._db.execute("""CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY, name TEXT, type TEXT, description TEXT,
            created_at REAL, updated_at REAL, source TEXT)""")
        self._db.execute("""CREATE TABLE IF NOT EXISTS relations (
            id TEXT PRIMARY KEY, from_id TEXT, relation TEXT, to_id TEXT,
            weight REAL DEFAULT 1.0, created_at REAL, source TEXT,
            FOREIGN KEY(from_id) REFERENCES entities(id),
            FOREIGN KEY(to_id)   REFERENCES entities(id))""")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_from ON relations(from_id)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_to   ON relations(to_id)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_etype ON entities(type)")
        self._db.commit()
        stats = self.stats()
        log.info(f"Knowledge Graph: {stats['entities']} entities, {stats['relations']} relations")

    # ── Extract from Text ─────────────────────────────────────────────────────
    async def extract_and_add(self, text: str, source: str = "") -> Dict:
        """Extract entities/relations from text via LLM and add to graph."""
        raw = await self.llm.complete(
            f"Extract entities and relations from:\n\n{text[:3000]}",
            role="general", system=EXTRACT_SYSTEM, temperature=0.1
        )
        try:
            raw = re.sub(r"```json|```", "", raw).strip()
            data = json.loads(raw)
        except Exception as e:
            log.warning(f"Graph extract parse error: {e}")
            return {"success": False, "error": str(e)}

        entities_added  = self._add_entities(data.get("entities", []), source)
        relations_added = self._add_relations(data.get("relations", []), source)

        return {
            "success": True,
            "entities_added":  entities_added,
            "relations_added": relations_added,
            "total_entities":  self.stats()["entities"],
            "total_relations": self.stats()["relations"],
        }

    # ── Add Manually ──────────────────────────────────────────────────────────
    def add_entity(self, name: str, entity_type: str = "concept",
                   description: str = "", source: str = "") -> str:
        eid = re.sub(r"[^a-z0-9_]", "_", name.lower())[:50]
        existing = self._db.execute(
            "SELECT id FROM entities WHERE id=?", (eid,)
        ).fetchone()
        if existing:
            return eid
        self._db.execute(
            "INSERT INTO entities VALUES (?,?,?,?,?,?,?)",
            (eid, name, entity_type, description,
             time.time(), time.time(), source)
        )
        self._db.commit()
        return eid

    def add_relation(self, from_id: str, relation: str, to_id: str,
                     weight: float = 1.0, source: str = "") -> bool:
        # Auto-create entities if they don't exist
        for eid in (from_id, to_id):
            if not self._entity_exists(eid):
                self._db.execute(
                    "INSERT INTO entities VALUES (?,?,?,?,?,?,?)",
                    (eid, eid.replace("_", " ").title(), "concept",
                     "", time.time(), time.time(), source)
                )
        rid = uuid.uuid4().hex[:12]
        # Check for duplicate
        dup = self._db.execute(
            "SELECT id FROM relations WHERE from_id=? AND relation=? AND to_id=?",
            (from_id, relation, to_id)
        ).fetchone()
        if dup:
            return False
        self._db.execute(
            "INSERT INTO relations VALUES (?,?,?,?,?,?,?)",
            (rid, from_id, relation, to_id, weight, time.time(), source)
        )
        self._db.commit()
        return True

    # ── Query ─────────────────────────────────────────────────────────────────
    async def query(self, question: str, depth: int = 2) -> Dict:
        """Answer a question using graph context + LLM."""
        # Find relevant entities via keyword matching
        keywords = [w.lower() for w in question.split() if len(w) > 3]
        entities = self._find_entities_by_keywords(keywords, limit=8)

        if not entities:
            return {"answer": "No relevant entities found in the knowledge graph.",
                    "entities": [], "relations": []}

        # Expand neighbourhood
        entity_ids = [e["id"] for e in entities]
        subgraph   = self._get_subgraph(entity_ids, depth)

        # Format for LLM
        ctx = self._format_subgraph(subgraph)
        prompt = f"Knowledge Graph Context:\n{ctx}\n\nQuestion: {question}\n\nAnswer:"
        answer = await self.llm.complete(
            prompt, role="general", system=QUERY_SYSTEM
        )

        return {
            "answer": answer,
            "entities": subgraph["entities"][:10],
            "relations": subgraph["relations"][:20],
        }

    def search_entities(self, query: str, entity_type: str = "",
                        limit: int = 20) -> List[Dict]:
        """Search entities by name/description."""
        words = [f"%{w.lower()}%" for w in query.split() if len(w) > 2]
        if not words:
            if entity_type:
                rows = self._db.execute(
                    "SELECT * FROM entities WHERE type=? LIMIT ?",
                    (entity_type, limit)
                ).fetchall()
            else:
                rows = self._db.execute(
                    "SELECT * FROM entities ORDER BY updated_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
        else:
            conds = " OR ".join(
                "LOWER(name) LIKE ? OR LOWER(description) LIKE ?" for _ in words
            )
            if entity_type:
                conds += " AND type=?"
            vals = [v for w in words for v in (w, w)]
            if entity_type:
                vals.append(entity_type)
            vals.append(limit)
            rows = self._db.execute(
                f"SELECT * FROM entities WHERE {conds} LIMIT ?", vals
            ).fetchall()
        return [self._row_to_entity(r) for r in rows]

    def get_neighbours(self, entity_id: str, depth: int = 1) -> Dict:
        """Get entity and its neighbourhood."""
        subgraph = self._get_subgraph([entity_id], depth)
        return subgraph

    def get_path(self, from_id: str, to_id: str,
                 max_depth: int = 4) -> Optional[List[Dict]]:
        """Find shortest path between two entities (BFS)."""
        if from_id == to_id:
            return [{"id": from_id}]

        visited: Set[str] = {from_id}
        queue: List[List[str]] = [[from_id]]

        for _ in range(max_depth):
            next_queue = []
            for path in queue:
                current = path[-1]
                # Get all connected entities
                rows = self._db.execute(
                    "SELECT to_id, relation FROM relations WHERE from_id=? "
                    "UNION SELECT from_id, relation FROM relations WHERE to_id=?",
                    (current, current)
                ).fetchall()
                for neighbour_id, relation in rows:
                    if neighbour_id == to_id:
                        # Found! Return path with relation labels
                        full_path = path + [neighbour_id]
                        return [{"id": eid} for eid in full_path]
                    if neighbour_id not in visited:
                        visited.add(neighbour_id)
                        next_queue.append(path + [neighbour_id])
            queue = next_queue
            if not queue:
                break
        return None  # No path found

    # ── Visualisation Data ────────────────────────────────────────────────────
    def get_viz_data(self, limit: int = 100) -> Dict:
        """Return graph data formatted for D3 / vis.js visualisation."""
        entities = self._db.execute(
            "SELECT * FROM entities ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        entity_ids = {r[0] for r in entities}

        relations = self._db.execute(
            "SELECT * FROM relations WHERE from_id IN ({}) AND to_id IN ({}) LIMIT ?".format(
                ",".join("?" * len(entity_ids)),
                ",".join("?" * len(entity_ids)),
            ),
            list(entity_ids) * 2 + [limit * 2]
        ).fetchall()

        nodes = [{"id": r[0], "name": r[1], "type": r[2], "description": r[3]}
                 for r in entities]
        links = [{"source": r[1], "relation": r[2], "target": r[3], "weight": r[4]}
                 for r in relations]
        return {"nodes": nodes, "links": links}

    # ── Delete ────────────────────────────────────────────────────────────────
    def delete_entity(self, entity_id: str) -> bool:
        self._db.execute("DELETE FROM relations WHERE from_id=? OR to_id=?",
                         (entity_id, entity_id))
        cur = self._db.execute("DELETE FROM entities WHERE id=?", (entity_id,))
        self._db.commit()
        return cur.rowcount > 0

    def clear(self):
        self._db.execute("DELETE FROM relations")
        self._db.execute("DELETE FROM entities")
        self._db.commit()

    # ── Stats ─────────────────────────────────────────────────────────────────
    def stats(self) -> Dict:
        entities  = self._db.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        relations = self._db.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        types     = self._db.execute(
            "SELECT type, COUNT(*) FROM entities GROUP BY type"
        ).fetchall()
        return {"entities": entities, "relations": relations,
                "by_type": dict(types)}

    # ── Private ───────────────────────────────────────────────────────────────
    def _add_entities(self, entities: list, source: str) -> int:
        added = 0
        for e in entities:
            eid = e.get("id", "").strip()
            if not eid:
                continue
            existing = self._db.execute(
                "SELECT id FROM entities WHERE id=?", (eid,)
            ).fetchone()
            if not existing:
                self._db.execute(
                    "INSERT INTO entities VALUES (?,?,?,?,?,?,?)",
                    (eid, e.get("name", eid),
                     e.get("type", "concept"),
                     e.get("description", ""),
                     time.time(), time.time(), source)
                )
                added += 1
            else:
                # Update description if we have a better one
                if e.get("description"):
                    self._db.execute(
                        "UPDATE entities SET description=?, updated_at=? WHERE id=?",
                        (e["description"], time.time(), eid)
                    )
        self._db.commit()
        return added

    def _add_relations(self, relations: list, source: str) -> int:
        added = 0
        for r in relations:
            from_id  = r.get("from", "").strip()
            to_id    = r.get("to", "").strip()
            relation = r.get("relation", "").strip()
            if not all([from_id, to_id, relation]):
                continue
            if self.add_relation(from_id, relation, to_id,
                                 r.get("weight", 1.0), source):
                added += 1
        return added

    def _entity_exists(self, eid: str) -> bool:
        return bool(
            self._db.execute("SELECT 1 FROM entities WHERE id=?", (eid,)).fetchone()
        )

    def _find_entities_by_keywords(self, keywords: list, limit: int) -> List[Dict]:
        if not keywords:
            rows = self._db.execute(
                "SELECT * FROM entities ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            conds = " OR ".join("LOWER(name) LIKE ? OR LOWER(description) LIKE ?" for _ in keywords)
            vals  = [f"%{kw}%" for kw in keywords for _ in range(2)]
            rows  = self._db.execute(
                f"SELECT * FROM entities WHERE {conds} LIMIT ?",
                vals + [limit]
            ).fetchall()
        return [self._row_to_entity(r) for r in rows]

    def _get_subgraph(self, seed_ids: List[str], depth: int) -> Dict:
        all_entities: Dict[str, Dict] = {}
        all_relations: List[Dict]     = []
        frontier = set(seed_ids)

        for _ in range(depth):
            if not frontier:
                break
            new_frontier: Set[str] = set()
            for eid in frontier:
                row = self._db.execute(
                    "SELECT * FROM entities WHERE id=?", (eid,)
                ).fetchone()
                if row and eid not in all_entities:
                    all_entities[eid] = self._row_to_entity(row)

                # Outgoing relations
                rels = self._db.execute(
                    "SELECT * FROM relations WHERE from_id=? OR to_id=?",
                    (eid, eid)
                ).fetchall()
                for rel in rels:
                    r_dict = {"id": rel[0], "from": rel[1], "relation": rel[2],
                              "to": rel[3], "weight": rel[4]}
                    if r_dict not in all_relations:
                        all_relations.append(r_dict)
                    for connected in (rel[1], rel[3]):
                        if connected not in all_entities:
                            new_frontier.add(connected)
            frontier = new_frontier

        return {"entities": list(all_entities.values()),
                "relations": all_relations[:50]}

    def _format_subgraph(self, subgraph: Dict) -> str:
        parts = ["Entities:"]
        for e in subgraph["entities"][:10]:
            parts.append(f"  [{e['type']}] {e['name']}: {e.get('description','')[:100]}")
        parts.append("\nRelations:")
        for r in subgraph["relations"][:20]:
            ef = next((e["name"] for e in subgraph["entities"] if e["id"] == r["from"]), r["from"])
            et = next((e["name"] for e in subgraph["entities"] if e["id"] == r["to"]),   r["to"])
            parts.append(f"  {ef} —[{r['relation']}]→ {et}")
        return "\n".join(parts)

    def _row_to_entity(self, row) -> Dict:
        return {"id": row[0], "name": row[1], "type": row[2],
                "description": row[3], "created_at": row[4],
                "updated_at": row[5], "source": row[6]}
