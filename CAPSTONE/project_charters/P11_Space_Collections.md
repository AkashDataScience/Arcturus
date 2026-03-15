# P11 Space & Collections Design

This document explains the **Space** design: why we use a Space node in Neo4j and `space_id` in Qdrant, how they work together, and how retrieval and sync respect spaces.

**Source:** Mnemo scope (Spaces & Collections, retrieval scoping, Shared Space).

---

## 1. What a Space Is

A **Space** is a logical container (project hub) for organizing memories and runs—similar to “projects” or “folders” in tools like Perplexity. Examples: “Startup Research”, “Home Renovation”, “Work”, “Personal”.

- **Global space:** The special value `__global__` (`SPACE_ID_GLOBAL`) denotes unscoped or “all my stuff” memories and facts. Legacy or pre-Spaces data is treated as global when `space_id` is missing or empty.
- **Concrete space:** A user-created space has a UUID `space_id`, a name, description, and a **sync_policy** (`sync`, `local_only`, or `shared`).

---

## 2. Why Both Neo4j Space Node and Qdrant space_id

We need **two places** because the two stores have different roles:

| Store | What we store | Why |
|-------|----------------|-----|
| **Neo4j** | **Space node** (space_id, name, description, sync_policy, version, device_id, updated_at) and relationships **Session–IN_SPACE→Space**, **Fact→Space** (when space-scoped) | Graph needs to answer “which space does this session belong to?” and “which spaces can this user access?” (including SHARED_WITH). Sync and lifecycle need space metadata. |
| **Qdrant** | **space_id** in the **payload** of each point (memory, RAG chunk, episodic) | Vector search must **filter** by space. Qdrant filters on payload fields; we don’t store a full graph there. So we store `space_id` on every point and filter by it. |

So:

- **Neo4j:** Source of truth for *what spaces exist*, *who owns or is shared with*, and *which session/fact belongs to which space*. Used for listing spaces, sync policy, and graph traversal scoped by space.
- **Qdrant:** Source of truth for *which space a memory/chunk/episode belongs to* for **filtered vector search**. The payload field `space_id` is the minimal link we need; no need to duplicate full Space metadata in Qdrant.

---

## 3. How It Was Chosen

**Alternatives that were considered:**

- **Option A:** Only `space_id` in Qdrant payload; no Space node in Neo4j.  
  **Downside:** No single place for space metadata (name, sync_policy, sharing); harder to list “all spaces for user” and to enforce sync policy and sharing in the graph.
- **Option B:** Space only in Neo4j; no `space_id` in Qdrant.  
  **Downside:** We’d have to resolve space for every memory via graph (Memory→Session→Space or similar), which is awkward for Qdrant’s filter-first model and adds latency.
- **Chosen:** **Space node in Neo4j** (metadata, Session–IN_SPACE→Space, Fact→Space, SHARED_WITH) **plus** **space_id in Qdrant** payload (filtering). This keeps graph semantics and sync/sharing in Neo4j and keeps vector search simple and fast in Qdrant.

**Neo4j 5 and null:** Fact nodes use `space_id: "__global__"` instead of null because Neo4j 5 rejects null in MERGE. So “global” facts are explicitly marked with the sentinel value.

---

## 4. Current Behavior (Summary)

- **Creating a space:** `POST /remme/spaces` → Neo4j `create_space()` (Space node, optional OWNS_SPACE from User). Frontend: SpacesPanel, SpacesModal.
- **Listing spaces:** `GET /remme/spaces` → Neo4j (owned + shared-with-me via `get_all_spaces_for_user`).
- **Adding a memory:** Request can include `space_id`; stored in Qdrant payload and reflected in Neo4j (Session–IN_SPACE→Space; Memory linked to Session).
- **Runs:** `POST /runs` can include `space_id`; `get_or_create_session(run_id, space_id)`; list_runs enriches with space from Neo4j `get_space_for_session`.
- **Retrieval:** When the run (or context) is in a **non-global** space, `memory_retriever.retrieve(space_id=..., space_ids=...)` filters Qdrant and Neo4j to that space only; **no global memories** are injected. When viewing Global, `get_all(space_id=__global__)` returns points with `space_id == "__global__"` OR empty (legacy).
- **Facts:** Facts have `space_id` (global = `__global__`); `get_facts_for_user` can scope by space; preferences adapter builds hub shape for requested space(s).
- **Sync:** Only spaces with `sync_policy` = `sync` or `shared` are synced; `local_only` spaces never leave the device.

---

## 5. Diagrams (Conceptual)

```
Neo4j:
  (User)-[:OWNS_SPACE|...]->(Space {space_id, name, sync_policy})
  (Session)-[:IN_SPACE]->(Space)
  (Fact)-[:IN_SPACE?]->(Space)   // or space_id property with __global__
  (Space)-[:SHARED_WITH]->(User)  // when shared

Qdrant (payload per point):
  { user_id, space_id: "__global__" | "<uuid>", ... }
  → Filter: space_id in [allowed space_ids]
```

---

## 6. Future Enhancements and Improvements

- **Full spaces manager UI:** Beyond SpacesPanel (permissions, bulk actions, space analytics).
- **Per-space model / instructions:** Override default model and system instructions per Space (Perplexity-style).
- **Space delete:** Backend support for deleting a space (cascade or soft-delete of memories/sessions).
- **Storage limits:** Per-space quotas (e.g. max memories, max files) for Pro/Enterprise.

---

**Related:** P11_Qdrant-VectorDB_NEO4j-KG_Design.md, P11_DETAILED_ARCHITECTURE.md, P11_SYNC_ENGINE_DESIGN.md.
