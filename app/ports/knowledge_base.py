from typing import Protocol

from pydantic import BaseModel, Field


class KnowledgeBaseHealth(BaseModel):
    ok: bool
    detail: str = ""
    enabled: bool = False


class KnowledgeSearchResult(BaseModel):
    text: str = ""
    used: bool = False
    mode: str = "mix"
    references: list[str] = Field(default_factory=list)


class KnowledgeBasePort(Protocol):
    async def health(self) -> KnowledgeBaseHealth: ...

    async def search(self, query: str, *, mode: str = "mix") -> KnowledgeSearchResult: ...
