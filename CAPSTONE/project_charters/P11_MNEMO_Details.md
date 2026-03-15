# P11 Mnemo — Memory Landscape & Architecture (Reference)

This document explains the **memory landscape before the project** and the **architecture after Mnemo**, with diagrams and a map of how each piece is used (e.g. episodic by PlannerAgent). Use it as a personal reference for why we made certain decisions and how the system fits together.

**Sources:** Original P11 explanation and unified reference (content consolidated here and in other P11 design docs); current code.

---

## 1. Memory Landscape Before the Project

Before Mnemo, Arcturus memory was a “messy filing cabinet”: local files, single-device, no graph, no spaces.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PRE-MNEMO MEMORY LANDSCAPE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Episodic Memory                RemMe (Preferences/Facts)        RAG       │
│  (core/episodic_memory.py)       (remme/store.py)                 (server_rag)│
│  ┌─────────────────────┐        ┌─────────────────────┐        ┌──────────┐│
│  │ Session skeletons   │        │ FAISS vector store   │        │ FAISS    ││
│  │ JSON in             │        │ + JSON hubs          │        │ chunks   ││
│  │ session_summaries_  │        │ (evidence, prefs,    │        │ local    ││
│  │ index/              │        │  soft_identity)      │        │ only     ││
│  └─────────────────────┘        └─────────────────────┘        └──────────┘│
│         │                                │                            │     │
│         │ No graph, local only           │ Single device, no sync     │     │
│         │ Basic search                   │ No entities/relationships  │     │
│         ▼                                ▼                            ▼     │
│  PlannerAgent / Runs use session summaries; RemMe used for context;        │
│  RAG used for documents. All isolated, no shared knowledge graph.           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.1 Episodic Memory (Before)

- **Where:** `core/episodic_memory.py`; data in `memory/session_summaries_index/` (JSON).
- **What:** Lightweight session “skeletons” (query, nodes, task goals, outcomes).
- **Limitations:** No graph, local only, no space organization, search is basic.

### 1.2 RemMe (Before)

- **Where:** `remme/store.py` (FAISS), hubs in JSON.
- **What:** User preferences and facts; vector similarity search.
- **Limitations:** FAISS is local-only; no cloud sync; no knowledge graph; no spaces.

### 1.3 RAG (Before)

- **Where:** `mcp_servers/server_rag.py`; FAISS for document chunks.
- **What:** Indexes local files; keyword (BM25) + vector search.
- **Limitations:** Separate from memory system; local only; no space scoping.

---

## 2. Architecture After Mnemo (Target)

Mnemo introduces a unified memory and knowledge layer: Qdrant for vectors, Neo4j for graph, Spaces for organization, Sync for multi-device, Auth and Lifecycle for identity and importance.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        POST-MNEMO MEMORY LANDSCAPE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Qdrant (Vector Store)              Neo4j (Knowledge Graph)                  │
│  ┌─────────────────────────────┐   ┌─────────────────────────────────────┐ │
│  │ arcturus_memories            │   │ User, Memory, Session, Entity,      │ │
│  │ arcturus_rag_chunks          │   │ Fact, Evidence, Space               │ │
│  │ arcturus_episodic            │   │ HAS_MEMORY, CONTAINS_ENTITY,         │ │
│  │ (user_id, space_id,         │   │ IN_SPACE, SHARED_WITH, ...           │ │
│  │  entity_ids, ...)            │◀──│ memory_id / entity_ids link        │ │
│  └─────────────────────────────┘   └─────────────────────────────────────┘ │
│                │                                        │                    │
│                │  Memory Retriever                       │                    │
│                │  (semantic + entity + graph expansion)  │                    │
│                ▼                                        ▼                    │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ Spaces (space_id in Qdrant; Space node in Neo4j); Sync Engine; Auth   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

- **Vectors:** Qdrant holds memories, RAG chunks, and episodic skeletons; all tenant- and (where applicable) space-scoped.
- **Graph:** Neo4j holds entities, relationships, facts, evidence, and spaces; linked to Qdrant via `memory_id` and `entity_ids`.
- **Retrieval:** Memory Retriever combines semantic (Qdrant), entity (Neo4j), and graph expansion; can be space-scoped.
- **Organization:** Spaces (Neo4j + `space_id` in Qdrant); Sync and Auth complete the picture.

---

## 3. How Each Piece Is Used (Consumers)

| Memory / component       | Consumer(s)              | How it’s used |
|--------------------------|--------------------------|----------------|
| **RemMe memories**       | PlannerAgent, Runs       | `memory_retriever.retrieve(query)` → semantic + entity + graph → fused context for planning and answers. |
| **Preferences / facts**  | PlannerAgent, RemMe UI   | Neo4j Facts → `neo4j_preferences_adapter.build_preferences_from_neo4j()` → hub-shaped response; `GET /remme/preferences`. |
| **Episodic**             | PlannerAgent, session replay | `search_episodes` / `get_recent_episodes` from Qdrant `arcturus_episodic` (or legacy JSON); session skeletons for context. |
| **RAG / Notes**          | RAG search, agents       | Qdrant `arcturus_rag_chunks` (vector + sparse); path-derived `space_id` for Notes. |
| **Knowledge graph**      | Memory Retriever, Graph Explorer | Entity resolution, graph expansion, `get_memory_ids_for_entity_names`; `GET /api/graph/explore` for visualization. |
| **Spaces**               | Runs, RemMe, Sync        | Filter memories/runs by `currentSpaceId`; retrieval scoped by space; sync policy per space. |

```
                    ┌─────────────────┐
                    │ PlannerAgent /  │
                    │ Runs            │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Memory Retriever│ │ Preferences     │ │ Episodic         │
│ (Qdrant + Neo4j)│ │ (Neo4j adapter) │ │ (Qdrant or JSON) │
└─────────────────┘ └─────────────────┘ └─────────────────┘
         │                   │                   │
         ▼                   ▼                   ▼
    arcturus_memories    Facts (Neo4j)    arcturus_episodic
    + entity/graph                          or legacy skeletons
```

---

## 4. Key Design Decisions (Why This Shape)

- **Qdrant for vectors:** Cloud-capable, multi-tenant, supports hybrid (dense + sparse) and filtering by `user_id` / `space_id`. FAISS kept as default for backward compatibility.
- **Neo4j for graph:** Single source of truth for entities, relationships, and facts; evidence and derivation live here; adapter exposes “preferences” without changing hub contract.
- **Space as first-class:** `space_id` in Qdrant and Space node in Neo4j allow scoped retrieval and sync policy; no global injection when run is in a space.
- **Unified extractor (field_id):** LLM emits only `field_id`; registry owns canonical (namespace, key); avoids model inventing storage coordinates.
- **Sync (LWW):** Simple, deterministic merge for memories and spaces; selective by `sync_policy`; auth context for `user_id`.

---

## 5. Future Enhancements and Improvements

- **Multi-hop graph expansion:** Currently one-hop; add configurable depth for deeper reasoning.
- **Dedicated graph query API:** Endpoint for “what do I know about X and how does it relate to Y?” for agents.
- **Unified Notes/Episodic/RAG in sync:** Extend sync protocol for notes and episodic explicitly; RAG sync granularity (per-doc vs per-chunk).
- **Embedded / Lite:** Optional embedded Qdrant and embedded graph (e.g. Kùzu) for local-only, no-Docker setups (see P11_Qdrant-VectorDB_NEO4j-KG_Design.md).

---

**Related:** P11_DETAILED_ARCHITECTURE.md, P11_Qdrant-VectorDB_NEO4j-KG_Design.md, P11_DELIVERY_README.md.
