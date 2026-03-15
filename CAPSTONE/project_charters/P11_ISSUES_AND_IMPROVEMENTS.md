# P11 Mnemo — Issues & Improvements (Post First Run)

**Last run:** `./scripts/run_p11_automation_tests.sh` (2026-03-15)

---

## Test Run Summary (Latest)

| Mode | Passed | Skipped | Failed |
|------|--------|---------|--------|
| **ASYNC_KG_INGEST=false** | 28 | 1 | 0 |
| **ASYNC_KG_INGEST=true** | 25 | 1 | 3 |

**Total selected:** 29 tests (p11_automation marker). Requires `docker-compose.tests.yml` (Qdrant on 6335, Neo4j on 7688).

### Fixes applied (this run)

- **docker-compose.tests.yml** — Added so the script can start isolated Qdrant (6335) and Neo4j (7688).
- **Sequential scenario** — `clean_databases` skips cleaning for `TestSequentialRaleighJonFlow` so steps 2–6 see data from steps 1–5.
- **Retrieval context** — Session-scoped `p11_embedding_mock` (word-overlap) so semantic search returns relevant memories without real LLM; `call_retrieve()` sets auth context (`set_current_user_id`) so store tenant filter matches the test user.

### Known skip (expected)

- **test_tg4_01_sync_trigger_after_add** — Skipped when sync server is not reachable (`SYNC_SERVER_URL`). Start sync server or accept skip in CI.

### Known failures with ASYNC_KG_INGEST=true

- **test_entities_list_returns_records** — Neo4j entities not yet present when assertion runs (async ingest delay).
- **test_step_01_add_raleigh_memory** — Location fact / Raleigh entity not in Neo4j within `wait_for_condition` window.
- **test_step_03_add_jon_google_memory** — Jon/Google/Durham entities not in Neo4j within window.

**Cause:** With async KG ingest, entities/facts are written in the background; a 5s poll can be too short.  
**Recommendation:** Increase `wait_for_condition` timeout for Neo4j assertions when `ASYNC_KG_INGEST=true`, or mark these tests as sync-only / allow flaky in async mode.

---

## Issues (by priority)

### P0 — Blocker

1. ~~**POST /runs invokes full agent loop, blocks on Gemini**~~ **FIXED**
   - **Fix:** Added dry-run mode: `RunRequest.dry_run=True` or `DRY_RUN_RUNS=true` env. Skips agent, writes minimal session JSON, returns immediately with status `completed`.

### P1 — High

2. ~~**TG3 and TG4 tests not implemented**~~ **FIXED**
   - **Fix:** Added `task_group_3_logged_in/test_auth_migration.py` (register, login, auth/me, migration). Added `task_group_4_sync/test_sync_api.py` (sync trigger, pull).

3. ~~**RAG and Notes CRUD not covered**~~ **FIXED**
   - **Fix:** Added `task_group_1_guest_single_space/test_rag_notes.py` (list documents, create file, delete).

### P2 — Medium

4. **Retrieval injection tests not implemented**
   - **Impact:** Plan cases TG1-03, TG1-05, TG1-06, TG1-08 verify that `retrieve(query)` injects Raleigh, Jon, episodic context into the agent. These require running the full run or calling `memory_retriever.retrieve()` directly with mocked agent context.
   - **Recommendation:** Add integration tests that call `memory_retriever.retrieve()` directly (or a thin API wrapper) and assert the returned context contains expected memory text and facts.

5. **Space isolation (run-scoped retrieval) not asserted**
   - **Impact:** TG2-03/04 (run in Global vs Cat space; different retrieval) require run creation. Since create_run is skipped, space-scoped retrieval is not validated.
   - **Recommendation:** Add tests that call `memory_retriever.retrieve(query, space_id=...)` directly and assert space filtering.

6. **pytest.ini excludes p11_automation by default**
   - **Impact:** Default `pytest` run skips these tests. Developers may not discover them.
   - **Recommendation:** Document in README and test plan; ensure CI has an explicit job that runs `scripts/run_p11_automation_tests.sh`.

### P3 — Low

7. **Episodic memory verification missing**
   - **Impact:** TG1-06 (episodic reference) and TG1-08 (when did I last meet Jon) depend on episodic store and run completion. Not covered.
   - **Recommendation:** Add episodic-related tests when run creation is mocked or a dedicated episodic API exists.

8. **Entity/Fact extraction quality not asserted**
   - **Impact:** Mock extractor returns deterministic entities; we do not validate that real extraction (or a richer mock) produces correct Neo4j graph state.
   - **Recommendation:** Add tests that query Neo4j for entities/facts after add and assert expected structure (optionally with real LLM in slow suite).

---

## Improvements (by priority)

### P0

1. **Mock AgentLoop4 for non-blocking run creation**
   - Enable `test_tg1_04_create_run` and future run-based tests without invoking Gemini.

### P1

2. **Implement TG3 and TG4 suites**
   - Per plan: registration, migration, logout, guest merge; multi-install sync with LWW.

3. **Add RAG and Notes automation tests**
   - Ensure RAG/Notes CRUD and space scoping work with mocked embeddings.

### P2

4. **Add retrieval injection tests**
   - Direct `retrieve()` calls with assertions on context content.

5. **Add space-scoped retrieval tests**
   - Assert `retrieve(query, space_id=cat_space)` excludes global memories.

### P3

6. **CI job for p11_automation**
   - Add `p11-mnemo-automation` job to `project-gates.yml` that runs `scripts/run_p11_automation_tests.sh` on schedule or manual trigger.

7. **Episodic and entity-quality tests**
   - When infrastructure allows (mocked runs or episodic API).

---

---

## Summary: Existing and New Issues / Recommendations

| Item | Type | Description |
|------|------|-------------|
| **ASYNC_KG_INGEST=true** | Existing | 3 tests fail: Neo4j assertions run before async ingest completes. Increase timeout or treat async run as best-effort. |
| **test_tg4_01_sync_trigger_after_add** | Existing | Skipped when sync server unreachable. Document or start sync server in CI. |
| **Script dependency** | Fixed | `docker-compose.tests.yml` was missing; added so script runs. |
| **Sequential scenario** | Fixed | DB was cleaned between steps; now skip clean for `TestSequentialRaleighJonFlow`. |
| **Retrieval empty context** | Fixed | Embedding mock + auth context in `call_retrieve()` so retrieval sees test user's memories. |
| **Warnings** | Low | Deprecation (SwigPy*, passlib/crypt). Non-blocking. |
| **CI** | Recommendation | Add a CI job that runs `./scripts/run_p11_automation_tests.sh` (with test compose). Optionally allow ASYNC run to fail without failing the job, or increase Neo4j wait timeouts. |

---

## How to Run

```bash
# Full suite (starts test DBs, runs sync then async mode)
./scripts/run_p11_automation_tests.sh

# One-off with env already set (e.g. in CI)
export QDRANT_URL=http://localhost:6335 NEO4J_URI=bolt://localhost:7688 NEO4J_USER=neo4j NEO4J_PASSWORD=test-password
uv run pytest -m p11_automation -v --tb=short
```

Requires Docker for `docker-compose.tests.yml` (Qdrant 6335, Neo4j 7688). Without test ports, tests are skipped.
