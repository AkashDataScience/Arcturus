from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_lifecycle_inspect_and_override(monkeypatch):
    # Seed a fake memory in the store
    fake_memory = {
        "id": "mem-1",
        "text": "Test memory",
        "created_at": "2025-01-01T00:00:00Z",
        "last_accessed_at": "2025-01-01T00:00:00Z",
        "access_count": 0,
        "importance": 0.1,
        "archived": False,
    }

    class DummyStore:
        def __init__(self):
            self._mem = dict(fake_memory)

        def get(self, mid):
            if mid == self._mem["id"]:
                return dict(self._mem)
            return None

        def update(self, mid, metadata=None, **kwargs):
            if mid != self._mem["id"]:
                return False
            metadata = metadata or {}
            self._mem.update(metadata)
            return True

    dummy = DummyStore()

    # Patch shared remme_store used by router
    import routers.remme as remme_router

    remme_router.remme_store = dummy

    # GET lifecycle
    res_get = client.get("/remme/memories/mem-1/lifecycle")
    assert res_get.status_code == 200
    data = res_get.json()
    lf = data["lifecycle"]
    assert lf["id"] == "mem-1"
    assert lf["archived"] is False
    assert lf["importance"] == 0.1

    # PATCH lifecycle
    res_patch = client.patch(
        "/remme/memories/mem-1/lifecycle",
        json={"archived": True, "importance": 0.05, "access_count": 3},
    )
    assert res_patch.status_code == 200
    patched = res_patch.json()["lifecycle"]
    assert patched["archived"] is True
    assert patched["importance"] == 0.05
    assert patched["access_count"] == 3

