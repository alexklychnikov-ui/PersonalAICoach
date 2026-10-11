from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "PersonalAICoach"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    public_base_url: str = "http://127.0.0.1:8000"
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    log_redact: bool = True
    tz: str = "Asia/Irkutsk"

    streamlit_host: str = "0.0.0.0"
    streamlit_port: int = 8501
    api_base_url: str = "http://127.0.0.1:8000"

    mongo_host: str = "127.0.0.1"
    mongo_port: int = 27017
    mongo_user: str = "coach"
    mongo_password: str = ""
    mongo_db: str = "personal_ai_coach"
    mongo_uri: str | None = None

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    openai_timeout_sec: int = 60
    llm_daily_budget_usd: float = 5.0
    llm_max_retries: int = 3

    telegram_bot_token: str = ""
    telegram_owner_id: int | None = None
    telegram_webhook_path: str = "/webhook/tg"
    telegram_webhook_secret: str = ""
    telegram_use_webhook: bool = False

    hh_enabled: bool = True
    hh_client_id: str = ""
    hh_client_secret: str = ""
    hh_access_token: str = ""
    hh_user_agent: str = "PersonalAICoach/0.1"
    hh_cache_ttl_sec: int = 3600

    kwork_enabled: bool = True
    kwork_login: str = ""
    kwork_password: str = ""
    kwork_category_ids: str = "39"
    kwork_poll_interval_sec: int = 900

    knowledge_base_enabled: bool = False
    mcp_lightrag_command: str = ""
    mcp_lightrag_args: str = ""
    mcp_lightrag_env_lightrag_base_url: str = "http://127.0.0.1:9621"
    mcp_lightrag_api_key: str = ""
    mcp_timeout_sec: int = 15
    mcp_circuit_breaker_failures: int = 3

    worker_enabled: bool = True
    checkin_cron: str = "0 10 * * 1"

    basic_auth_user: str = ""
    basic_auth_password: str = ""
    internal_api_key: str = ""

    deploy_ssh_host: str = "AIcareerСoach"
    deploy_ssh_user: str = "root"
    deploy_remote_dir: str = "/opt/personal-ai-coach"
    deploy_domain: str = "aicareercoach.alexklyvibe.ru"
    deploy_server_ip: str = "193.168.196.12"

    profile_doc_id: str = "singleton"

    def build_mongo_uri(self) -> str:
        if self.mongo_uri:
            return self.mongo_uri
        if self.mongo_password:
            user = quote_plus(self.mongo_user)
            password = quote_plus(self.mongo_password)
            return (
                f"mongodb://{user}:{password}@{self.mongo_host}:{self.mongo_port}"
                f"/{self.mongo_db}?authSource=admin"
            )
        return f"mongodb://{self.mongo_host}:{self.mongo_port}/{self.mongo_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
