# P11 Mnemo: Neo4j Knowledge Graph Design

> **Status:** Implemented. See memory/knowledge_graph.py, memory/entity_extractor.py, scripts/migrate_memories_to_neo4j.py.
> **Context:** Phase 3 of Mnemo — Neo4j layer for Remme memories (entities, relationships, User/Session nodes).

---

## 1. Overview

Neo4j stores extracted entities and relationships from Remme memories. It ties to Qdrant via `memory_id` (Qdrant point id) and `entity_ids` (Neo4j entity ids in Qdrant payload).

---

## 2. Neo4j Schema

### Nodes

| Node Label | Properties | Purpose |
|------------|------------|---------|
| **User** | `id`, `user_id` | Central node; multi-tenant; anchor for derived facts |
| **Memory** | `id` (Qdrant point id), `category`, `source`, `created_at` | Bridge to Qdrant |
| **Session** | `id`, `session_id`, `original_query`, `created_at` | Provenance; temporal grouping |
| **Entity** | `id`, `type`, `name`, `created_at` | Person, Company, Concept, City, Date, etc. |

### Relationships

| Relationship | From → To | Properties | Purpose |
|--------------|-----------|------------|---------|
| **HAS_MEMORY** | User → Memory | — | Ownership; multi-tenant |
| **FROM_SESSION** | Memory → Session | — | Provenance; "which session produced this memory" |
| **CONTAINS_ENTITY** | Memory → Entity | — | Memory mentions this entity |
| **RELATED_TO** | Entity → Entity | `type`, `value`, `confidence`, `source_memory_ids` | e.g. Person -[:WORKS_AT]-> Company |
| **LIVES_IN** | User → Entity | `source_memory_ids` | Derived: user lives in City |
| **WORKS_AT** | User → Entity | `source_memory_ids` | Derived: user works at Company |
| **KNOWS** | User → Entity | `source_memory_ids` | Derived: user knows Person |
| **PREFERS** | User → Entity | `source_memory_ids` | Derived: user prefers Concept (e.g. dietary) |
| **CONTRADICTS** | (Phase 5) | — | Mark conflicting facts |

### Example Graph

```
(User {user_id: "abc"})
  -[:HAS_MEMORY]-> (Memory {id: "qdrant-123"})
  -[:FROM_SESSION]-> (Session {session_id: "run_456"})
  -[:CONTAINS_ENTITY]-> (Entity {type: "Person", name: "John"})
  -[:CONTAINS_ENTITY]-> (Entity {type: "Company", name: "Google"})

(Entity {name: "John"}) -[:RELATED_TO {type: "works_at", source_memory_ids: ["qdrant-123"]}]-> (Entity {name: "Google"})

(User) -[:LIVES_IN {source_memory_ids: ["qdrant-123"]}]-> (Entity {type: "City", name: "Morrisville"})
```

---

## 3. Qdrant Changes

### Payload additions for `arcturus_memories`

| Field | Type | Purpose |
|-------|------|---------|
| `user_id` | string | Already exists (multi-tenant) |
| `session_id` | string | Run/session id; link to Session node |
| `entity_ids` | list[string] | Neo4j entity ids; enables Qdrant ↔ Neo4j link |

### Config

- Add `session_id` and `entity_ids` to `indexed_payload_fields` in `config/qdrant_config.yaml` if filtered search is needed.

---

## 4. Ingestion Flow

1. New memory added to Qdrant (with `user_id`, `session_id` in payload).
2. Create or get **User** and **Session** nodes in Neo4j.
3. Create **Memory** node; link `(User)-[:HAS_MEMORY]->(Memory)` and `(Memory)-[:FROM_SESSION]->(Session)`.
4. Extract entities and relationships from memory text (LLM or NER).
5. Create **Entity** nodes; link `(Memory)-[:CONTAINS_ENTITY]->(Entity)`.
6. Create `(Entity)-[:RELATED_TO]->(Entity)` with `source_memory_ids`.
7. Infer user-centric facts → create `(User)-[:LIVES_IN|WORKS_AT|KNOWS|PREFERS]->(Entity)` with `source_memory_ids`.
8. Update Qdrant memory payload with `entity_ids`.

---

## 5. Retrieval Flow

```
Query: "What do I know about John and his work?"
         │
         ├─► Qdrant: semantic search → top-k memories (memory_ids)
         │
         └─► Neo4j: 
             - Find Entity(name="John")
             - Traverse RELATED_TO, LIVES_IN, WORKS_AT, etc.
             - Get Memory nodes via CONTAINS_ENTITY or HAS_MEMORY
             - Optionally: (User)-[:LIVES_IN]->(City) for user context
         │
         ▼
    Fused context for agent
```

---

## 6. Implementation Order

1. Add Neo4j client + schema (User, Memory, Session, Entity, relationships).
2. Entity extraction pipeline (LLM or NER).
3. Ingestion: on memory add → extract → write Neo4j → update Qdrant `entity_ids`.
4. Ensure Qdrant payload includes `user_id`, `session_id`, `entity_ids`.
5. Retrieval: Qdrant search + Neo4j expansion.
6. Migration script: backfill existing Qdrant memories → Neo4j.

---

## 7. Files to Create/Modify

| File | Action |
|------|--------|
| `memory/knowledge_graph.py` | New: Neo4j client, schema, CRUD |
| `memory/entity_extractor.py` | New: LLM/NER extraction |
| `config/qdrant_config.yaml` | Add `session_id`, `entity_ids` to indexed fields |
| `memory/backends/qdrant_store.py` | Ensure add() accepts `session_id`, `entity_ids` |
| `remme/extractor.py` or ingestion path | Call knowledge graph on memory add |
| `scripts/migrate_memories_to_neo4j.py` | New: backfill script |

---

## 8. How to Continue in a New Chat

Start a new chat and say:

> "Continue the Neo4j knowledge graph implementation from @CAPSTONE/project_charters/P11_NEO4J_KNOWLEDGE_GRAPH_DESIGN.md"

Or attach the file and ask to implement the design.

---

## 9. Next Steps (Recorded for Future Implementation)

*No code in this section — use this as the spec for a new context.*

### 9.1 Retrieval Gap: When Semantic Search Returns Nothing

**Problem:** At agent run time we do a single vector search (top-k, e.g. 3) on Qdrant. If the user query does not semantically match any memory (e.g. "Planning to meet John again at his office? Can you check the weather next week?"), Qdrant returns no results. We then never call Neo4j, so we never surface the memory that contains entities like "Jon", "Google", "NC" even though "John" / "office" are clearly related. The knowledge graph is only used *after* we have at least one memory from Qdrant.

**Two directions to address this:**

1. **Entity-friendly payload in Qdrant**
   - **Idea:** Store something more readable than raw `entity_ids` in Qdrant (e.g. composite keys like `Person::Jon`, `Company::Google`, or a small list of `{type, name}` objects) so we can do entity-based matching or display without always querying Neo4j.
   - **Industry practice:** Keeping only foreign IDs in the vector store is common (single source of truth in the graph). Denormalizing entity names/types into the payload is also common when you need filter-by-entity or hybrid search (e.g. keyword/entity filters in Qdrant) or to avoid a Neo4j round-trip for every read. Tradeoff: payload size and consistency (if an entity is renamed in Neo4j, you’d need to update Qdrant). A practical approach is to store both: `entity_ids` (for Neo4j link) and something like `entity_labels` or `entity_composite_keys` (for display and optional filter/expansion) so reads and entity-first retrieval can work without always hitting Neo4j.

2. **Smarter search at agent run**
   - **Idea:** Don’t rely only on “Qdrant top-k then expand.” Options:
     - **Larger k then trim:** e.g. fetch top 10 from Qdrant, use top 3 for direct memory context and use the rest (or all 10) for entity_ids → Neo4j expansion, then fuse. So we still have one vector call but more candidates for graph expansion.
     - **Dual path:** In parallel (or as fallback), do an **entity-first** path: from the query, extract or guess entity names (e.g. “John”, “office”) → query Neo4j for entities matching those names (or similar) → get `memory_ids` from the graph → fetch those memories from Qdrant by id and inject into context. That way even with zero semantic match we can still pull in memories that mention “John” / “Jon” / “Google office”.
   - Combining both (slightly larger k + entity-first fallback) gives better recall when the query is entity-centric but not semantically close to the memory text.

### 9.2 Session-Level Extraction: One Pass for Memories, Preferences, and Entities

**Current limitation:** Session summaries are used to extract memories (and preferences) via the existing extractor. Those memories are then stored in Qdrant and, on add, we run entity extraction on the **memory text only**. So we can lose entities and relationships that existed in the full session but were compressed or dropped when the memory snippet was written.

**Better design:**

- **Single session-level extraction:** Update the extractor (and its output schema) so that when processing a **session summary** (or full session), it produces in one shot:
  - **Memories** (as today: add/update/delete commands or text snippets),
  - **Preferences** (as today: key-value or structured for hubs),
  - **Entities and relationships** (same structure as the current entity extractor: entities, entity_relationships, user_facts).
- **One JSON structure** from the extractor that includes all three. The ingestion pipeline then:
  - Writes memories to Qdrant (and Neo4j: Memory, Session, User, entities, relationships, user_facts) using that single extraction result, so entities are derived from the **full session context**, not from the shortened memory text.
- **Manual memory add stays separate:** When the user adds a memory directly from the UI, we only have that single text. So we keep the current flow: add to Qdrant → run entity extraction on that text → write to Neo4j and update Qdrant. No change to that path; only the **session-based** path becomes “one extraction, memories + preferences + entities.”

**Extractor change:** The remme extractor (or a unified extraction prompt/skill) would need an updated JSON schema that includes both the existing memory commands and preferences and the new entities/entity_relationships/user_facts. Downstream: same Neo4j ingestion, same Qdrant payload updates; preferences can still be written to staging/hubs as today.

### 9.3 Unifying Preferences with Qdrant + Neo4j (Longer-Term)

**Observation:** Extracted entities and user_facts (LIVES_IN, WORKS_AT, KNOWS, PREFERS) are very similar to what is stored in JSON files (e.g. `evidence_log.json`, `preferences_hub.json`, etc.). Having two places for “user preferences and facts” can lead to duplication and drift.

**Possible direction:**

- **Move preferences / evidence into Qdrant + Neo4j** so that:
  - Preference-like facts are stored as memories (Qdrant) and/or as user–entity relationships and entities (Neo4j).
  - One source of truth for “what we know about the user” for retrieval and reasoning.
- **UI and existing consumers:** Keep the current UX “more or less” the same by:
  - Adding an **adapter or service layer** that reads from Qdrant/Neo4j (and optionally from existing JSON for backward compatibility) and exposes the same or similar structure that the UI and hubs expect (e.g. same categories, same field names). Over time, the UI can be pointed only at the new store.
- **Extraction pipeline:** As in 9.2, the session-level extractor would output memories, preferences, and entities; the ingestion path would write preferences into the new store (and optionally still to JSON for a transition period). This may require mapping current hub schema (e.g. dietary_style, verbosity) to entities/concepts and user_facts (e.g. PREFERS → Concept "vegetarian") so that both the graph and the UI stay consistent.

Use this section (9) as the reference when starting a new context to implement retrieval improvements, session-level extraction, and/or preferences unification.
