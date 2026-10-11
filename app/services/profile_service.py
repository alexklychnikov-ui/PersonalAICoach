from datetime import UTC, datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.defaults.profile_seed import DEFAULT_PROFILE, DEFAULT_TRACK
from app.domain.models import CareerTrack, CareerTrackType, UserProfile


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ProfileService:
    def __init__(self, db: AsyncIOMotorDatabase, profile_id: str = "singleton") -> None:
        self._db = db
        self._profile_id = profile_id

    async def get_profile(self) -> UserProfile:
        doc = await self._db.user_profile.find_one({"_id": self._profile_id})
        if not doc:
            profile = UserProfile(id=self._profile_id)
            await self.save_profile(profile)
            return profile
        doc["id"] = doc.pop("_id")
        return UserProfile.model_validate(doc)

    def profile_is_empty(self, profile: UserProfile) -> bool:
        return not (
            profile.current_position.strip()
            or profile.desired_role.strip()
            or profile.skills
            or profile.resume_summary.strip()
        )

    async def save_profile(self, profile: UserProfile) -> UserProfile:
        profile.id = self._profile_id
        profile.updated_at = _utcnow()
        data = profile.model_dump()
        data["_id"] = data.pop("id")
        await self._db.user_profile.replace_one({"_id": self._profile_id}, data, upsert=True)
        return profile

    async def list_tracks(self) -> list[CareerTrack]:
        cursor = self._db.career_tracks.find().sort("created_at", -1)
        tracks: list[CareerTrack] = []
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id"))
            tracks.append(CareerTrack.model_validate(doc))
        return tracks

    async def create_track(self, track: CareerTrack) -> CareerTrack:
        track.created_at = _utcnow()
        data = track.model_dump(exclude={"id"})
        result = await self._db.career_tracks.insert_one(data)
        track.id = str(result.inserted_id)
        return track

    async def find_track_by_type_title(
        self, track_type: CareerTrackType | str, title: str
    ) -> CareerTrack | None:
        type_value = track_type.value if isinstance(track_type, CareerTrackType) else track_type
        doc = await self._db.career_tracks.find_one({"type": type_value, "title": title})
        if not doc:
            return None
        doc["id"] = str(doc.pop("_id"))
        return CareerTrack.model_validate(doc)

    async def upsert_track(self, track: CareerTrack, *, activate: bool = True) -> CareerTrack:
        """Create or update track by (type, title) — no duplicates."""
        existing = await self.find_track_by_type_title(track.type, track.title)
        if existing and existing.id:
            result = await self._db.career_tracks.find_one_and_update(
                {"_id": ObjectId(existing.id)},
                {
                    "$set": {
                        "weekly_hours_budget": track.weekly_hours_budget,
                        "kpis": track.kpis,
                        "status": track.status or "active",
                    }
                },
                return_document=ReturnDocument.AFTER,
            )
            assert result is not None
            result["id"] = str(result.pop("_id"))
            saved = CareerTrack.model_validate(result)
        else:
            saved = await self.create_track(track)
        if activate and saved.id:
            return await self.activate_track(saved.id)
        return saved

    async def seed_defaults(self, *, force_profile: bool = False) -> dict:
        """Fill profile + default freelance track from LightRAG-based seed."""
        profile = await self.get_profile()
        if force_profile or self.profile_is_empty(profile):
            seeded = UserProfile.model_validate(DEFAULT_PROFILE)
            profile = await self.save_profile(seeded)
        track = await self.upsert_track(
            CareerTrack(
                type=CareerTrackType(DEFAULT_TRACK["type"]),
                title=str(DEFAULT_TRACK["title"]),
                weekly_hours_budget=float(DEFAULT_TRACK["weekly_hours_budget"]),
                kpis=list(DEFAULT_TRACK["kpis"]),
            ),
            activate=True,
        )
        return {"profile": profile, "track": track}

    async def activate_track(self, track_id: str) -> CareerTrack:
        await self._db.career_tracks.update_many(
            {"is_active": True},
            {"$set": {"is_active": False}},
        )
        now = _utcnow()
        result = await self._db.career_tracks.find_one_and_update(
            {"_id": ObjectId(track_id)},
            {"$set": {"is_active": True, "activated_at": now, "status": "active"}},
            return_document=ReturnDocument.AFTER,
        )
        if not result:
            raise ValueError(f"Track not found: {track_id}")
        result["id"] = str(result.pop("_id"))
        return CareerTrack.model_validate(result)

    async def get_active_track(self) -> CareerTrack | None:
        doc = await self._db.career_tracks.find_one({"is_active": True})
        if not doc:
            return None
        doc["id"] = str(doc.pop("_id"))
        return CareerTrack.model_validate(doc)

    async def ensure_default_track(self) -> CareerTrack:
        active = await self.get_active_track()
        if active:
            return active
        result = await self.seed_defaults(force_profile=False)
        track = result["track"]
        assert isinstance(track, CareerTrack)
        return track
