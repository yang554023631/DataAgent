from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True

    # LLM
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    DEFAULT_MODEL: str = "claude-3-haiku-20240307"
    ANALYST_MODEL: str = "claude-3-sonnet-20240229"

    # Custom Report
    CUSTOM_REPORT_URL: str = "http://localhost:3000"
    CUSTOM_REPORT_TIMEOUT: int = 30

    # Limits
    MAX_CLARIFICATION_COUNT: int = 3
    MAX_DRILL_DOWN_LEVEL: int = 2

settings = Settings()
