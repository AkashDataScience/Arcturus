# P11 Qdrant (Vector DB) & Neo4j (Knowledge Graph) Design

This document captures the design of the vector store (Qdrant) and knowledge graph (Neo4j) for Mnemo: what was built in Phase 1 and Phase 2, options that were discussed with pros/cons, current schema and flows, and how to make the stack “lite” for local setup. Use it as a personal reference for why we chose this design.

**Sources:** Neo4j knowledge graph design, unified reference, and embedded/lite architecture (content consolidated here).

---

## 1. Phase 1: Vector Store (FAISS → Qdrant)

### 1.1 Goal

Replace local FAISS with a cloud-capable vector store that supports multi-tenancy and scales, while keeping backward compatibility (FAISS remains the default).

### 1.2 Options Discussed

| Option | Pros | Cons |
|--------|------|------|
| **Qdrant** | Good Python client, local (Docker/embedded) and cloud, multi-tenant, sparse vectors + prefetch/RRF | None blocking for our scope |
| **Weaviate** | Graph-like schema, hybrid search | Additional evaluation; charter allowed “if time permits” |
| **Keep FAISS** | No new infra, fast locally | No cloud sync, single-device, no managed multi-tenancy |

**Choice:** Qdrant for Phase 1. FAISS kept as fallback via `VECTOR_STORE_PROVIDER=faiss` (default).

### 1.3 Implemented Design

- **Abstraction:** `memory/vector_store.py` — `get_vector_store(provider="qdrant"|"faiss")`, `VectorStoreProtocol`.
- **Qdrant backend:** `memory/backends/qdrant_store.py` — CRUD, search, multi-tenant via `user_id`; on add → `_ingest_to_knowledge_graph` when Neo4j enabled.
- **Config:** `memory/qdrant_config.py`, `config/qdrant_config.yaml` — collection config, URL/API key from env.
- **Collections:** `arcturus_memories` (RemMe), `arcturus_rag_chunks` (RAG), `arcturus_episodic` (session skeletons); all support `user_id` and, where applicable, `space_id`.
- **Migration:** `scripts/migrate_faiss_to_qdrant.py`, `migrate_rag_faiss_to_qdrant.py`; orchestrated by `migrate_all_memories.py`.

---

## 2. Phase 2: Neo4j Knowledge Graph

### 2.1 Goal

Store extracted entities and relationships from Remme memories; link to Qdrant via `memory_id` and `entity_ids`; support dual-path retrieval (semantic + entity/graph).

### 2.2 Options Discussed

| Aspect | Options | Choice / notes |
|--------|---------|----------------|
| **Graph DB** | Neo4j vs NetworkX vs other | Neo4j for persistence, Cypher, production use; NetworkX for in-memory prototyping only in charter. |
| **Entity identity** | By name vs by canonical key | `canonical_name` + `composite_key = type::canonical_name` for dedupe ("Google" / "google" merge). |
| **Relationship types** | Single generic vs typed | First-class types (WORKS_AT, LOCATED_IN, KNOWS, etc.) with `RELATED_TO` fallback for unknown types. |
| **Retrieval when semantic returns 0** | Rely on semantic only vs add entity path | Entity path runs **independently**; rescues when semantic returns 0 (e.g. "John" in query, "Jon" in memory). |
| **Entity-friendly payload in Qdrant** | Only `entity_ids` vs also labels/keys | Store both `entity_ids` (Neo4j link) and `entity_labels` (display/filter without Neo4j round-trip); tradeoff: payload size vs consistency if entity renamed. |

### 2.3 Neo4j Schema (Current)

**Nodes:** User, Memory, Session, Entity, Fact, Evidence, Space.

**Key node properties:**

- **Entity:** `id`, `type`, `name`, `canonical_name`, `composite_key`, `created_at`.
- **Fact:** `id`, `user_id`, `namespace`, `key`, `space_id`, `value_*`, `confidence`, `source_mode`, `status`, `first_seen_at`, `last_seen_at`, etc. Global facts use `space_id = "__global__"` (Neo4j 5 rejects null in MERGE).
- **Space:** `space_id`, `name`, `description`, `sync_policy`, `version`, `device_id`, `updated_at`.

**Relationships:** HAS_MEMORY, FROM_SESSION, CONTAINS_ENTITY, entity–entity (WORKS_AT, LOCATED_IN, OWNS, KNOWS, etc., plus RELATED_TO), User–Entity (LIVES_IN, WORKS_AT, KNOWS, PREFERS), HAS_FACT, SUPPORTED_BY, REFERS_TO, SUPERSEDES, IN_SPACE, SHARED_WITH, CONTRADICTS (for conflicting facts).

### 2.4 Qdrant Payload (arcturus_memories)

- `user_id`, `session_id`, `space_id` (default `__global__`), `entity_ids`, optional `entity_labels`.
- `config/qdrant_config.yaml`: `indexed_payload_fields` includes `session_id`, `entity_labels`, `space_id`, `archived`, `visibility`.

### 2.5 Ingestion Flow

1. Memory added to Qdrant (with `user_id`, `session_id`, `space_id`).
2. Create/get User and Session in Neo4j; Session–IN_SPACE→Space when `space_id` present.
3. Create Memory; link User–HAS_MEMORY–Memory, Memory–FROM_SESSION–Session.
4. Extract entities/relationships (LLM via entity_extractor or unified extractor).
5. Create Entity nodes (canonical_name, composite_key); link Memory–CONTAINS_ENTITY–Entity.
6. Create entity–entity relationships (first-class or RELATED_TO).
7. Infer user facts → User–LIVES_IN|WORKS_AT|KNOWS|PREFERS–Entity.
8. When unified extractor is used: write Fact/Evidence from extraction; derive User–Entity from Fact+REFERS_TO.
9. Update Qdrant payload with `entity_ids` (and `entity_labels`).

### 2.6 Retrieval Flow

- **Path 1 — Semantic:** Qdrant vector search (k=10); optional hybrid (dense + sparse) with RRF; top used for context; all 10 for entity_ids → graph expansion.
- **Path 2 — Entity (independent):** Extract entities from query → resolve vs Neo4j (`resolve_entity_candidates`, fuzzy, within-type then global fallback) → `get_memory_ids_for_entity_names` / `expand_from_entities` → memory_ids → fetch from Qdrant.
- **Merge:** Global `result_ids` dedupe; deterministic ordering; space-scoped when `space_id`/`space_ids` provided (no global injection in a space).
- **Multi-tenant:** All graph expansion scoped by `(User {user_id})-[:HAS_MEMORY]->(Memory)`.

### 2.7 Phase 2.5: field_id and Unified Extractor

- **Principle:** Canonical fact identity is owned by the registry; LLM emits only `field_id`, never namespace/key.
- **Registry:** `memory/fact_field_registry.py` — field_id → namespace, key, value_type, etc.; `get_valid_field_ids()` for prompt.
- **Normalizer:** `memory/fact_normalizer.py` — resolves field_id → (namespace, key); unknown → extras.
- **Unified extractor:** One shot from session: memories + preferences (facts) + entities; `ingest_from_unified_extraction()` writes to Neo4j (and memories to Qdrant). Direct memory add still uses entity extraction on memory text only.

---

## 3. Implementation Status (Summary)

- **Phase 1:** Done — Qdrant backend, migration scripts, setup guide.
- **Phase 2/3:** Done — Schema (including Fact, Evidence, Space), ingestion, dual-path retrieval, backfill, memory delete & orphan cleanup.
- **Spaces:** Done — `space_id` in Qdrant; Space node and IN_SPACE in Neo4j; retrieval and ingestion scoped by space.
- **Entity-friendly payload:** Done — `entity_ids` + `entity_labels` in Qdrant; indexed.
- **Session-level extraction:** Done — `extract_from_session`, `ingest_from_unified_extraction`; runs/remme use it when Mnemo enabled.
- **Expansion depth:** One-hop only; `depth` reserved for multi-hop.

---

## 4. Embedded / “Lite” Local Architecture

For local setup without Docker or heavy dependencies, the stack can be made “lite” by swapping server-based stores for embedded ones.

### 4.1 Qdrant: Docker → Embedded

- **Mechanism:** `qdrant-client` supports `QdrantClient(path="/path/to/storage")` (SQLite-backed).
- **Config:** Add `QDRANT_MODE=embedded`, `QDRANT_PATH=./memory/qdrant_local/`; branch in `qdrant_config.py` and `qdrant_store.py`.
- **Effort:** Low. Same Python API (scroll, retrieve, etc.).

### 4.2 Neo4j: Docker → Embedded Graph (e.g. Kùzu)

- **Option:** Use **Kùzu** (Cypher-compatible, embedded). Neo4j has no embedded Python option (always separate JVM).
- **Tradeoffs:** Kùzu requires schema and has Cypher differences (e.g. variable-length upper bound, datetime). Introduce `KnowledgeGraphProtocol`; implement `KùzuKnowledgeGraph` with schema and query adaptation.
- **Effort:** Medium–high (2–4 days depending on query volume).
- **Production:** Keep Neo4j (or Aura) for cloud; use Kùzu only for local/embedded. Hybrid: server = Qdrant Cloud + Neo4j; local = embedded Qdrant + Kùzu (see §4).

### 4.3 Alternatives (Reference)

- **Embedded vector:** Qdrant `path=`, Chroma, LanceDB, sqlite-vec.
- **Embedded graph:** Kùzu (Cypher), FalkorDBLite (Cypher, subprocess), NetworkX (prototyping only).

---

## 5. Future Enhancements and Improvements

- **Multi-hop expansion:** Add configurable depth for graph expansion; currently one-hop.
- **Entity-friendly refinements:** Optional composite keys or richer payload in Qdrant for filter/display without Neo4j; tune k, top_for_context, fuzzy_threshold.
- **Session-level extraction:** Already implemented; possible refinements to schema or prompt.
- **Preferences unification:** Already in Neo4j via Fact/Evidence and adapter; optional further migration off JSON hubs.
- **Graph query API:** Dedicated endpoint for “what do I know about X and how does it relate to Y?” for agent reasoning.
- **Lite rollout:** Implement embedded Qdrant path first; then KnowledgeGraphProtocol + Kùzu backend for optional local-only graph.
- **Sharding / federated search:** Per-user shards with cross-user federated search for shared spaces (post–Phase 5).

---

**Related:** P11_Space_Collections.md (Space design), P11_RAG_Notes_Episodic.md (RAG/Notes/Episodic in this stack), P11_DETAILED_ARCHITECTURE.md (high-level).
