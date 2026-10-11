from app.adapters.disabled_kb import DisabledKnowledgeBase
from app.adapters.factory import build_knowledge_base, build_llm
from app.adapters.openai_llm import StubLLM
from app.config import Settings


def test_config_load_defaults():
    settings = Settings(
        _env_file=None,
        mongo_password="",
        openai_api_key="",
        knowledge_base_enabled=False,
    )
    assert settings.app_name == "PersonalAICoach"
    assert settings.api_prefix == "/api/v1"
    uri = settings.build_mongo_uri()
    assert "27017" in uri


def test_mongo_uri_with_password():
    settings = Settings(
        _env_file=None,
        mongo_user="coach",
        mongo_password="s3cret",
        mongo_host="mongo",
        mongo_db="personal_ai_coach",
    )
    uri = settings.build_mongo_uri()
    assert "coach:s3cret@mongo:27017" in uri
    assert "authSource=admin" in uri


def test_kb_disabled_factory():
    settings = Settings(_env_file=None, knowledge_base_enabled=False)
    kb = build_knowledge_base(settings)
    assert isinstance(kb, DisabledKnowledgeBase)


def test_llm_stub_without_key():
    settings = Settings(_env_file=None, openai_api_key="")
    llm = build_llm(settings)
    assert isinstance(llm, StubLLM)
