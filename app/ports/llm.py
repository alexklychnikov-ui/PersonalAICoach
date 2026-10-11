from typing import Any, Protocol


class LLMPort(Protocol):
    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema_hint: str | None = None,
    ) -> dict[str, Any]: ...

    async def complete_text(self, *, system: str, user: str) -> str: ...
