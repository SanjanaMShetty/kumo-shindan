"""Application settings loaded from the environment and an optional .env file."""

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env before provider libraries read API keys from the environment.
load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "openai"
    llm_model: str = "SET_LATER"
    llm_base_url: str | None = None
    llm_temperature: float | None = 0.0

    allowed_namespaces: str = "demo"
    max_steps: int = 8
    log_tail_lines: int = 100
    max_tool_output_chars: int = 6000

    db_path: str = "data/kumoshindan.db"
    slack_webhook_url: str | None = None
    webhook_token: str | None = None
    alert_cooldown_seconds: int = 600
    max_concurrent_investigations: int = 2

    @property
    def namespaces(self) -> list[str]:
        return [name.strip() for name in self.allowed_namespaces.split(",") if name.strip()]


settings = Settings()
