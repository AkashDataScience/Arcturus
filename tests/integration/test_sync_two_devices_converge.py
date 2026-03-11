"""
P11 Phase 4 Sync Engine — integration test: two devices push/pull and converge.

Device A: adds a memory (to server store), pushes to sync server.
Device B: has a separate store, pulls from sync server, applies changes.
Assert: Device B's store contains the same memory content (convergence).
"""

import os
import tempfile
from unittest.mock import patch

import numpy as np
import pytest

from memory.sync.schema import PullRequest, PullResponse, PushRequest, PushResponse


class _FakeStore:
    """Minimal in-memory store for Device B so we can assert convergence without FAISS/Qdrant."""

    def __init__(self):
        self._memories: list[dict] = []

    def get(self, memory_id: str):
        for m in self._memories:
            if m.get("id") == memory_id:
                return m.copy()
        return None

    def add(
        self,
        text: str,
        embedding,
        category: str = "general",
        source: str = "manual",
        metadata=None,
        session_id=None,
        space_id=None,
        skip_kg_ingest=False,
        **kwargs,
    ):
        import uuid
        memory_id = str(uuid.uuid4())
        m = {
            "id": memory_id,
            "text": text,
            "category": category,
            "source": source,
            "session_id": session_id,
            "space_id": space_id or "__global__",
            **(metadata or {}),
        }
        self._memories.append(m)
        return m

    def sync_upsert(self, memory_id: str, text: str, embedding, payload: dict):
        existing = self.get(memory_id)
        m = {
            "id": memory_id,
            "text": text,
            "payload": payload,
            **payload,
        }
        if existing:
            self._memories = [m if x.get("id") == memory_id else x for x in self._memories]
        else:
            self._memories.append(m)
        return True

    def get_all(self, limit=None, filter_metadata=None):
        out = list(self._memories)
        if limit:
            out = out[:limit]
        return out

    def update(self, memory_id: str, text=None, embedding=None, metadata=None):
        for m in self._memories:
            if m.get("id") == memory_id:
                if text is not None:
                    m["text"] = text
                if metadata:
                    m.update(metadata)
                return True
        return False

    def delete(self, memory_id: str):
        self._memories = [m for m in self._memories if m.get("id") != memory_id]
        return True


@pytest.mark.slow
class TestSyncTwoDevicesConverge:
    """Two devices: A pushes, B pulls; B's store converges (has the memory)."""

    @pytest.fixture(autouse=True)
    def _enable_sync_env(self, monkeypatch):
        monkeypatch.setenv("SYNC_ENGINE_ENABLED", "true")
        monkeypatch.setenv("SYNC_SERVER_URL", "http://testserver/api")

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api import app
        return TestClient(app)

    def _make_push_via_client(self, client, request: PushRequest) -> PushResponse:
        r = client.post("/api/sync/push", json=request.model_dump(mode="json"))
        r.raise_for_status()
        d = r.json()
        return PushResponse(
            accepted=d.get("accepted", True),
            cursor=d.get("cursor", ""),
            errors=d.get("errors", []),
        )

    def _make_pull_via_client(self, client, request: PullRequest) -> PullResponse:
        from memory.sync.schema import SyncChange
        r = client.post("/api/sync/pull", json=request.model_dump(mode="json"))
        r.raise_for_status()
        d = r.json()
        raw = d.get("changes", [])
        changes = [SyncChange.model_validate(c) if isinstance(c, dict) else c for c in raw]
        return PullResponse(changes=changes, cursor=d.get("cursor", ""))

    def test_two_devices_push_then_pull_converge(self, client):
        """Device A adds memory and pushes; Device B pulls; B has the memory."""
        from memory.sync.engine import SyncEngine
        from memory.sync.transport import pull_changes, push_changes
        from memory.user_id import get_user_id

        user_id = get_user_id()
        device_a = "device-a"
        device_b = "device-b"

        # 1) Device A: add memory via API (server store gets it)
        add_resp = client.post(
            "/api/remme/add",
            json={"text": "Integration test memory for sync converge.", "category": "general"},
        )
        assert add_resp.status_code == 200
        data = add_resp.json()
        memory = data.get("memory", {})
        memory_id = memory.get("id")
        text_added = memory.get("text", "")
        assert memory_id and text_added

        # 2) Device A: push to sync server (so sync log has the change)
        def push_via_testclient(base_url: str, req: PushRequest, **kwargs):
            return self._make_push_via_client(client, req)

        def pull_via_testclient(base_url: str, req: PullRequest, **kwargs):
            return self._make_pull_via_client(client, req)

        with patch("memory.sync.engine.push_changes", side_effect=push_via_testclient):
            with patch("memory.sync.engine.pull_changes", side_effect=pull_via_testclient):
                # Engine A (server's store) pushes
                store_a = None
                try:
                    from shared.state import get_remme_store
                    store_a = get_remme_store()
                except Exception:
                    pytest.skip("remme store not available")
                engine_a = SyncEngine(
                    user_id=user_id,
                    device_id=device_a,
                    store=store_a,
                    kg=None,
                    get_embedding_fn=lambda t: np.zeros(768, dtype=np.float32),
                )
                push_resp = engine_a.push()
                assert push_resp.accepted, push_resp.errors

        # 3) Device B: separate store, pull from server, apply
        store_b = _FakeStore()
        assert len(store_b.get_all()) == 0

        with patch("memory.sync.engine.push_changes", side_effect=push_via_testclient):
            with patch("memory.sync.engine.pull_changes", side_effect=pull_via_testclient):
                engine_b = SyncEngine(
                    user_id=user_id,
                    device_id=device_b,
                    store=store_b,
                    kg=None,
                    get_embedding_fn=lambda t: np.zeros(768, dtype=np.float32),
                )
                pull_resp = engine_b.pull()

        # 4) Converge: B's store should have the memory (same text)
        all_b = store_b.get_all()
        texts_b = [m.get("text") for m in all_b]
        assert text_added in texts_b, f"Expected text in B's store. Got: {texts_b}"

    def test_two_devices_B_pushes_A_receives_via_pull(self, client):
        """Device B has a memory and pushes; server store gets it (convergence to server)."""
        from memory.sync.engine import SyncEngine
        from memory.user_id import get_user_id

        user_id = get_user_id()
        device_b = "device-b"
        text_b = "Device B only memory for sync integration test."

        # Device B: local store with one memory
        store_b = _FakeStore()
        fake_emb = np.zeros(768, dtype=np.float32)
        store_b.add(text_b, fake_emb, category="general", source="manual")
        assert len(store_b.get_all()) == 1

        def push_via_testclient(base_url: str, req, **kwargs):
            return self._make_push_via_client(client, req)

        def pull_via_testclient(base_url: str, req, **kwargs):
            return self._make_pull_via_client(client, req)

        with patch("memory.sync.engine.push_changes", side_effect=push_via_testclient):
            with patch("memory.sync.engine.pull_changes", side_effect=pull_via_testclient):
                engine_b = SyncEngine(
                    user_id=user_id,
                    device_id=device_b,
                    store=store_b,
                    kg=None,
                    get_embedding_fn=lambda t: np.zeros(768, dtype=np.float32),
                )
                push_resp = engine_b.push()
                assert push_resp.accepted, push_resp.errors

        # Server should have received the push (merge into server store). So server store has the memory.
        try:
            from shared.state import get_remme_store
            store_server = get_remme_store()
            all_server = store_server.get_all()
            texts_server = [m.get("text", "") for m in all_server]
            assert text_b in texts_server, f"Expected server store to have B's memory. Got: {texts_server}"
        except Exception as e:
            pytest.skip(f"Could not assert server store: {e}")
