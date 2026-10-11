import pytest
from bson import ObjectId

from app.domain.models import CareerTrack, CareerTrackType
from app.services.profile_service import ProfileService


class FakeCollection:
    def __init__(self) -> None:
        self.docs: dict[ObjectId, dict] = {}

    async def find_one(self, query: dict):
        if query.get("is_active") is True:
            for oid, doc in self.docs.items():
                if doc.get("is_active") is True:
                    return {**doc, "_id": oid}
            return None
        if "type" in query and "title" in query:
            for oid, doc in self.docs.items():
                if doc.get("type") == query["type"] and doc.get("title") == query["title"]:
                    return {**doc, "_id": oid}
            return None
        if "_id" in query:
            doc = self.docs.get(query["_id"])
            return {**doc, "_id": query["_id"]} if doc else None
        return None

    async def insert_one(self, data: dict):
        oid = ObjectId()
        self.docs[oid] = dict(data)
        return type("R", (), {"inserted_id": oid})()

    async def update_many(self, query: dict, update: dict):
        for doc in self.docs.values():
            if query.get("is_active") is True and doc.get("is_active") is True:
                doc.update(update.get("$set", {}))

    async def find_one_and_update(self, query: dict, update: dict, return_document=None):
        oid = query["_id"]
        doc = self.docs.get(oid)
        if not doc:
            return None
        doc.update(update.get("$set", {}))
        return {**doc, "_id": oid}

    def find(self):
        class Cursor:
            def __init__(self, docs):
                self._docs = docs

            def sort(self, *args, **kwargs):
                return self

            def __aiter__(self):
                self._iter = iter(self._docs)
                return self

            async def __anext__(self):
                try:
                    oid, doc = next(self._iter)
                except StopIteration as exc:
                    raise StopAsyncIteration from exc
                return {**doc, "_id": oid}

        return Cursor(list(self.docs.items()))

    async def replace_one(self, query, data, upsert=False):
        self.docs[query["_id"]] = {k: v for k, v in data.items() if k != "_id"}


class FakeDB:
    def __init__(self) -> None:
        self.user_profile = FakeCollection()
        self.career_tracks = FakeCollection()


@pytest.mark.asyncio
async def test_track_activation_exclusive():
    db = FakeDB()
    svc = ProfileService(db)  # type: ignore[arg-type]
    t1 = await svc.create_track(
        CareerTrack(type=CareerTrackType.EMPLOYMENT, title="Найм", kpis=["1 offer"])
    )
    t2 = await svc.create_track(
        CareerTrack(
            type=CareerTrackType.FIRST_FREELANCE_ORDER,
            title="Фриланс",
            kpis=["1 заказ"],
        )
    )
    assert t1.id and t2.id
    await svc.activate_track(t1.id)
    await svc.activate_track(t2.id)
    active = await svc.get_active_track()
    assert active is not None
    assert active.id == t2.id
    tracks = await svc.list_tracks()
    assert sum(1 for t in tracks if t.is_active) == 1


@pytest.mark.asyncio
async def test_upsert_track_no_duplicates():
    db = FakeDB()
    svc = ProfileService(db)  # type: ignore[arg-type]
    t1 = await svc.upsert_track(
        CareerTrack(
            type=CareerTrackType.FIRST_FREELANCE_ORDER,
            title="Первые платные заказы",
            kpis=["a"],
            weekly_hours_budget=10,
        )
    )
    t2 = await svc.upsert_track(
        CareerTrack(
            type=CareerTrackType.FIRST_FREELANCE_ORDER,
            title="Первые платные заказы",
            kpis=["b", "c"],
            weekly_hours_budget=15,
        )
    )
    assert t1.id == t2.id
    assert t2.kpis == ["b", "c"]
    assert t2.weekly_hours_budget == 15
    assert len(await svc.list_tracks()) == 1
