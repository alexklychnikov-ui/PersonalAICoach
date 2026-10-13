from app.adapters.disabled_kb import DisabledKnowledgeBase
from app.adapters.flru_market import FlruMarketSource
from app.adapters.hh_market import HHMarketSource
from app.adapters.kwork_market import KworkMarketSource
from app.adapters.mcp_lightrag import McpLightRagAdapter
from app.adapters.openai_llm import OpenAILLM, StubLLM
from app.adapters.telegram_market import TelegramMarketSource
from app.adapters.yandex_uslugi_market import YandexUslugiMarketSource
from app.config import Settings
from app.ports.knowledge_base import KnowledgeBasePort
from app.ports.llm import LLMPort
from app.ports.market import MarketSourcePort


def build_llm(settings: Settings) -> LLMPort:
    if settings.openai_api_key:
        return OpenAILLM(settings)
    return StubLLM()


def build_knowledge_base(settings: Settings) -> KnowledgeBasePort:
    if not settings.knowledge_base_enabled:
        return DisabledKnowledgeBase()
    return McpLightRagAdapter(settings)


def build_market_sources(settings: Settings) -> list[MarketSourcePort]:
    sources: list[MarketSourcePort] = []
    if settings.hh_enabled:
        sources.append(HHMarketSource(settings))
    if settings.kwork_enabled:
        sources.append(KworkMarketSource(settings))
    if settings.flru_enabled:
        sources.append(FlruMarketSource(settings))
    if settings.yandex_uslugi_enabled:
        sources.append(YandexUslugiMarketSource(settings))
    if settings.telegram_market_enabled:
        sources.append(TelegramMarketSource(settings))
    return sources
