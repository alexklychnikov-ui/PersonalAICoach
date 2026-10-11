import pytest

from app.adapters.disabled_kb import DisabledKnowledgeBase
from app.adapters.mcp_lightrag import McpLightRagAdapter
from app.config import Settings


@pytest.mark.asyncio
async def test_kb_disabled():
    kb = DisabledKnowledgeBase()
    health = await kb.health()
    assert health.ok is True
    assert health.enabled is False
    result = await kb.search("карьера")
    assert result.used is False


@pytest.mark.asyncio
async def test_kb_degraded_on_unreachable():
    settings = Settings(
        _env_file=None,
        knowledge_base_enabled=True,
        mcp_lightrag_env_lightrag_base_url="http://127.0.0.1:59999",
        mcp_timeout_sec=1,
        mcp_circuit_breaker_failures=1,
    )
    kb = McpLightRagAdapter(settings)
    health = await kb.health()
    assert health.enabled is True
    assert health.ok is False
    result = await kb.search("test")
    assert result.used is False
