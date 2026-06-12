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

    # Smaller Groq model used by the background chain (shares Groq keys/quota).
    groq_small_model: str = Field(default="llama-3.1-8b-instant")

    # OpenAI-compatible providers (all optional; a provider joins the fallback
    # chain only when its keys are configured — see app/llm/client_factory.py).
    cerebras_api_keys: str | None = Field(default=None)
    cerebras_model: str = Field(default="gpt-oss-120b")
    nvidia_api_keys: str | None = Field(default=None)
    nvidia_model: str = Field(default="nvidia/llama-3.3-nemotron-super-49b-v1")
    mistral_api_keys: str | None = Field(default=None)
    mistral_model: str = Field(default="mistral-large-latest")
    openrouter_api_keys: str | None = Field(default=None)
    openrouter_model: str = Field(default="meta-llama/llama-3.3-70b-instruct:free")
    # LLM7 works without a key, so its presence in the chain is opt-in.
    llm7_enabled: bool = Field(default=False)
    llm7_api_keys: str | None = Field(default=None)
    llm7_model: str = Field(default="deepseek-r1-0528")
    zai_api_keys: str | None = Field(default=None)
    zai_model: str = Field(default="glm-4.5-flash")

    # Optional comma-separated ordering overrides for the fallback chains.
    llm_interactive_chain: str | None = Field(default=None)
    llm_background_chain: str | None = Field(default=None)

    # OCR fallback for scanned/image-only PDFs (PyMuPDF + system Tesseract).
    # Degrades gracefully to a parse warning when Tesseract is not installed.
    ocr_enabled: bool = Field(default=True)
    ocr_dpi: int = Field(default=300)
    tessdata_prefix: str | None = Field(default=None)  # overrides TESSDATA_PREFIX env

    # When False, DOCX inputs may only render back to DOCX ("keep original"); when
    # True they may also use the HTML/.tex templates (DOCX -> PDF). "Keep original"
    # stays the default for DOCX either way.
    allow_docx_to_pdf: bool = Field(default=True)
    # Per-user limits on LLM-backed endpoints (SlowAPI multi-limit string).
    # The per-minute window is the real abuse guard; the hourly/daily caps keep
    # one user under ~1/3 of the conservative global free-tier capacity.
    llm_user_rate_limits: str = Field(default="10/minute;60/hour;250/day")
    top_n_projects: int = Field(default=3)
    top_n_experience: int = Field(default=3)
    # Transactional email (Brevo REST API). When brevo_api_key is unset, emails
    # are not sent; outside production the verification code is logged instead.
    brevo_api_key: str | None = Field(default=None)
    mail_from: str = Field(default="no-reply@example.com")
    mail_from_name: str = Field(default="CV Barber")

    # Google OAuth (login enabled only when both id and secret are set).
    google_oauth_client_id: str | None = Field(default=None)
    google_oauth_client_secret: str | None = Field(default=None)
    # Public origin of the app; builds the OAuth redirect URL and SPA redirects.
    app_base_url: str = Field(default="http://localhost:8000")

    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    env: str = Field(default="development")
    allowed_hosts: str = Field(default="*")  # comma-separated; "*" disables host check
    database_url: str = Field(...)
    secret_key: str = Field(...)
    # extra="ignore": the .env is shared with other services (e.g. the job-finder's
    # CRAWLER_URL); unknown keys must not crash this app's settings load.
    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH, case_sensitive=False, extra="ignore"
    )

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

    def get_provider_keys(self, provider: str) -> list[str]:
        """Parse the comma-separated `<provider>_api_keys` setting into a list."""
        if provider == "groq":
            return self.get_all_groq_keys()
        if provider == "gemini":
            return self.get_all_gemini_keys()
        raw = getattr(self, f"{provider}_api_keys", None) or ""
        return [k.strip() for k in raw.split(",") if k.strip()]


settings = Settings()
