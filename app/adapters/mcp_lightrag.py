import logging
import time

import httpx

from app.config import Settings
from app.ports.knowledge_base import KnowledgeBaseHealth, KnowledgeSearchResult

logger = logging.getLogger(__name__)


class McpLightRagAdapter:
    """
    LightRAG context via HTTP bridge to LightRAG Server REST.

    Product contract is MCP-only from app perspective; this adapter talks to the
    LightRAG server that backs the MCP tools (search/status). Direct SDK is not used.
    When MCP stdio process wiring is added later, swap transport here without
    changing KnowledgeBasePort callers.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base = settings.mcp_lightrag_env_lightrag_base_url.rstrip("/")
        self._api_key = settings.mcp_lightrag_api_key
        self._timeout = settings.mcp_timeout_sec
        self._fail_threshold = settings.mcp_circuit_breaker_failures
        self._failures = 0
        self._open_until = 0.0

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        return headers

    def _circuit_open(self) -> bool:
        return time.time() < self._open_until

    def _record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._fail_threshold:
            self._open_until = time.time() + 60
            logger.warning("LightRAG circuit open for 60s after %s failures", self._failures)

    def _record_success(self) -> None:
        self._failures = 0
        self._open_until = 0.0

    async def health(self) -> KnowledgeBaseHealth:
        if self._circuit_open():
            return KnowledgeBaseHealth(ok=False, detail="circuit_open", enabled=True)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(f"{self._base}/health", headers=self._headers())
            if resp.status_code < 400:
                self._record_success()
                return KnowledgeBaseHealth(ok=True, detail="ok", enabled=True)
            self._record_failure()
            return KnowledgeBaseHealth(
                ok=False, detail=f"status={resp.status_code}", enabled=True
            )
        except Exception as exc:  # noqa: BLE001
            self._record_failure()
            logger.warning("LightRAG health failed: %s", exc)
            return KnowledgeBaseHealth(ok=False, detail=str(exc), enabled=True)

    async def search(self, query: str, *, mode: str = "mix") -> KnowledgeSearchResult:
        if self._circuit_open():
            return KnowledgeSearchResult(text="", used=False, mode=mode)
        payload = {"query": query, "mode": mode, "only_need_context": True}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base}/query",
                    headers=self._headers(),
                    json=payload,
                )
            if resp.status_code >= 400:
                self._record_failure()
                return KnowledgeSearchResult(text="", used=False, mode=mode)
            data = resp.json()
            text = data.get("response") or data.get("data") or ""
            if isinstance(text, dict):
                text = str(text.get("response") or text)
            text = str(text)
            self._record_success()
            return KnowledgeSearchResult(text=text, used=bool(text.strip()), mode=mode)
        except Exception as exc:  # noqa: BLE001
            self._record_failure()
            logger.warning("LightRAG search failed: %s", exc)
            return KnowledgeSearchResult(text="", used=False, mode=mode)
