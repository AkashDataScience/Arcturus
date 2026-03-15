# P11 RAG, Notes & Episodic Memory in the Mnemo Design

This document explains how **RAG**, **Notes**, and **Episodic memory** fit into the Mnemo design: Qdrant collections, Neo4j (where applicable), and Spaces.

**Sources:** Mnemo Phase 5A–5B (RAG/episodic scope); episodic and notes design (content consolidated here).

---

## 1. Overview

| Component | Primary store | Space scoping | Sync | Notes |
|-----------|----------------|---------------|------|-------|
| **RAG chunks** | Qdrant `arcturus_rag_chunks` | `space_id` in payload | Via RAG sync (chunks) | Migration sets user_id + space_id; path-derived for Notes |
| **Notes** | Same as RAG (chunks in Qdrant) | Path-derived `space_id` | Same as RAG | e.g. `data/Notes/__global__/`, `data/Notes/{space_id}/` |
| **Episodic** | Qdrant `arcturus_episodic` or legacy JSON | `space_id` in payload | EpisodicDelta in sync when provider=qdrant | Session skeletons; Session–IN_SPACE→Space in Neo4j |

---

## 2. RAG

### 2.1 Role in Mnemo

- RAG stores **document chunks** (and conversation history) for semantic and keyword search. It uses the **same vector store abstraction** as memories: `RAG_VECTOR_STORE_PROVIDER=qdrant` or `faiss`.
- When Qdrant is used, the collection is **arcturus_rag_chunks** with `user_id` and `space_id` in the payload.

### 2.2 How It Fits

- **Qdrant:** Collection `arcturus_rag_chunks`; dimension, distance, tenant by `user_id`; `indexed_payload_fields` include `doc`, `doc_type`, `session_id`, `space_id`. Sparse vector `chunk-bm25` for hybrid search (Phase C).
- **Neo4j:** No dedicated RAG nodes. Sessions (and thus run context) are linked to Space via Session–IN_SPACE→Space; RAG search is filtered by `user_id` and optionally `space_id` in Qdrant.
- **Spaces:** Each chunk can carry `space_id`. For Notes, `space_id` is derived from file path (e.g. `Notes/__global__/` vs `Notes/{space_id}/`).
- **Migration (Phase 5A):** `migrate_rag_faiss_to_qdrant.py` supports `--space-id` / `MIGRATION_SPACE_ID` (default `__global__`); migrated chunks get `user_id` and `space_id`.

### 2.3 Search Path

- Hybrid search (dense + sparse) with prefetch + RRF in Qdrant; filters by `user_id` and optionally `space_id`. Entity gate and existing RAG API behavior unchanged.

---

## 3. Notes

### 3.1 Role in Mnemo

- Notes are **files under `data/Notes/`** (or similar). They are indexed as RAG documents; there is no separate “Notes store” — they use the same RAG path and Qdrant collection.

### 3.2 How They Fit

- **Storage:** Same Qdrant collection `arcturus_rag_chunks`. When the RAG indexer processes a note, it derives **space_id from path**:
  - Convention: `data/Notes/__global__/` = global; `data/Notes/{space_id}/` = notes in that space.
  - Root `Notes/` (or unscoped path) → `space_id=__global__`.
- **No separate env:** Notes follow `RAG_VECTOR_STORE_PROVIDER`; no extra config.
- **Sync:** Chunks are synced like other RAG chunks (user_id, space_id in payload) when sync engine is extended for RAG (or already covered if RAG sync is implemented).

---

## 4. Episodic Memory

### 4.1 Role in Mnemo

- Episodic memory stores **session skeletons** (lightweight summaries of runs: query, nodes, task goals, outcomes). Used for replay, reasoning, and “recent sessions” context.

### 4.2 How It Fits

- **Qdrant (preferred):** Collection **arcturus_episodic** with `user_id`, `space_id`, `session_id`, `original_query`, etc. Searchable text (e.g. `original_query` + condensed node descriptions) is embedded; search via `search_episodes`, list via `get_recent_episodes` with filters.
- **Neo4j:** Session already exists and is linked to Space via **Session–IN_SPACE→Space**. So “which space does this episode belong to?” is already in the graph; episodic payload `space_id` is consistent with that.
- **Legacy:** `EPISODIC_STORE_PROVIDER=legacy` reads/writes `memory/episodic_skeletons/skeleton_*.json` (or similar). Sync engine can apply episodic changes to local JSON when legacy is used.
- **Space source:** When saving an episode, `space_id` is passed from the run/session (e.g. from `get_or_create_session(run_id, space_id)`); if missing, default `__global__`.

### 4.3 Sync

- **EpisodicDelta:** When provider is Qdrant, sync engine builds episodic deltas (episodic_id, session_id, user_id, space_id, skeleton_json, version, device_id, updated_at, deleted) and includes them in push/pull with same LWW semantics as memories.
- **Notes:** No separate episodic entity for “notes”; notes are RAG chunks with path-derived `space_id`.

---

## 5. Diagram (Logical)

```
                    ┌─────────────────────────────────────┐
                    │           Qdrant                     │
                    │  arcturus_memories (space_id)       │
                    │  arcturus_rag_chunks (space_id)     │  ← RAG + Notes
                    │  arcturus_episodic (space_id)       │  ← Episodic
                    └─────────────────────────────────────┘
                                         │
                    ┌─────────────────────────────────────┐
                    │           Neo4j                     │
                    │  Session–IN_SPACE→Space             │  ← Episodic session
                    │  (no RAG-specific nodes)            │
                    └─────────────────────────────────────┘
```

---

## 6. Migration Order (Reference)

1. Run existing migrations (memories, RAG, hubs) as needed.
2. Episodic: run `migrate_episodic_to_qdrant.py` (or equivalent in `migrate_all_memories.py`) — read legacy skeletons, write to `arcturus_episodic` with `user_id`, `space_id=__global__` for legacy.
3. Notes: Reindex RAG with `user_id` and `space_id`; path convention for Notes folders sets `space_id`.

---

## 7. Future Enhancements and Improvements

- **Unified memory architecture:** Explicitly migrate Notes and Episodic to same Mnemo patterns everywhere (space-scoped, Sync Engine–backed, offline-first); optional entity types in sync protocol for note/episodic.
- **RAG sync granularity:** Decide and document per-document vs per-chunk sync for RAG; same LWW/policy logic can apply.
- **Episodic in sync:** Ensure all environments use EpisodicDelta consistently when provider is qdrant; document any legacy-only behavior.

---

**Related:** P11_Qdrant-VectorDB_NEO4j-KG_Design.md, P11_Space_Collections.md, P11_PHASEC_BM25_HYBRID_SEARCH_DESIGN.md (RAG hybrid search).
