from typing import Protocol

from app.domain.models import MarketItem


class MarketSourcePort(Protocol):
    name: str

    async def search(self, query: str, *, limit: int = 10) -> list[MarketItem]: ...

    async def get_item(self, external_id: str) -> MarketItem | None: ...
