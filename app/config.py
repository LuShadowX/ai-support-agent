"""All settings come from environment variables (or a .env file)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # LLM - any OpenAI-compatible provider (OpenRouter, Gemini, OpenAI, Groq...)
    llm_api_key: str = ""
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "google/gemini-2.5-flash"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 800
    llm_timeout_seconds: float = 60

    # Branding
    business_name: str = "Nimbus Home"
    bot_name: str = "Nimbus Assistant"
    greeting: str = "Hi! I can answer questions about our products, shipping and returns, or check on your order. How can I help?"

    # Knowledge base (RAG)
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    docs_dir: Path = BASE_DIR / "data" / "docs"
    storage_dir: Path = BASE_DIR / "storage"
    chunk_size: int = 800
    chunk_overlap: int = 120
    top_k: int = 4

    # Conversation
    history_turns: int = 10
    max_message_chars: int = 2000
    max_agent_steps: int = 5

    # Security
    allowed_origins: list[str] = ["*"]
    rate_limit_per_minute: int = 20
    admin_token: str = ""

    # Channels
    telegram_bot_token: str = ""


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    return settings
