from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PARENT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE_PATH = PARENT_DIR / ".env"


class Settings(BaseSettings):
    llm_provider: str = Field(default="groq")

    # Groq
    groq_api_key: str | None = Field(default=None)
    groq_api_keys: str | None = Field(default=None)  # comma-separated
    groq_model: str = Field(default="llama-3.3-70b-versatile")

    # Gemini (used as fallback when LLM_PROVIDER=groq, or as primary when LLM_PROVIDER=gemini)
    gemini_api_key: str = Field(default="def_key")
    gemini_api_keys: str = Field(default="")
    gemini_model: str = Field(default="gemini-2.5-flash")

    # Ollama
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama3.1")

    output_format: str = Field(default="pdf")
    top_n_projects: int = Field(default=3)
    top_n_experience: int = Field(default=3)
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    env: str = Field(default="development")
    database_url: str = Field(...)
    secret_key: str = Field(...)
    model_config = SettingsConfigDict(env_file=ENV_FILE_PATH, case_sensitive=False)

    def get_all_groq_keys(self) -> list[str]:
        if self.groq_api_keys:
            keys = [k.strip() for k in self.groq_api_keys.split(",") if k.strip()]
            if keys:
                return keys
        if self.groq_api_key:
            return [self.groq_api_key]
        return []

    def get_all_gemini_keys(self) -> list[str]:
        if self.gemini_api_keys:
            keys = [k.strip() for k in self.gemini_api_keys.split(",") if k.strip()]
            if keys:
                return keys
        if self.gemini_api_key and self.gemini_api_key != "def_key":
            return [self.gemini_api_key]
        return []


settings = Settings()
