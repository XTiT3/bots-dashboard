from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8-sig", extra="ignore")
    DISCORD_CLIENT_ID: str
    DISCORD_CLIENT_SECRET: str
    DISCORD_REDIRECT_URI: str = "http://localhost:8000/api/auth/callback"
    SESSION_SECRET: str = "dev-change-me"
    FRONTEND_URL: str = "http://localhost:5173"
    BOT_DATA_DIR: str = ".."
    DATABASE_URL: str = "sqlite:///./dashboard.db"
    BOT_ALI_TOKEN: str = ""
    BOT_ORGANIZER_TOKEN: str = ""
    BOT_TRANSLATOR_TOKEN: str = ""

settings = Settings()
