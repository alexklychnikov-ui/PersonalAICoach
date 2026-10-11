from app.ports.knowledge_base import KnowledgeBaseHealth, KnowledgeSearchResult


class DisabledKnowledgeBase:
    async def health(self) -> KnowledgeBaseHealth:
        return KnowledgeBaseHealth(ok=True, detail="disabled", enabled=False)

    async def search(self, query: str, *, mode: str = "mix") -> KnowledgeSearchResult:
        _ = query, mode
        return KnowledgeSearchResult(text="", used=False, mode=mode)
