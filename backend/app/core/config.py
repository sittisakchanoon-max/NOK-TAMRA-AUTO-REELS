from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PORT: int = 8000
    HOST: str = "0.0.0.0"
    DEBUG: bool = False
    DASHBOARD_PIN: str = "123456"
    
    # Database
    DATABASE_URL: str = f"sqlite+aiosqlite:///{BASE_DIR}/storage/nok_tamra.db"
    
    # Google Drive
    GDRIVE_FOLDER_ID: str = "1HsnkGFR1wPvQXYVYLeaCaqo7q3BS6uxi"
    GDRIVE_CHECK_INTERVAL_MINUTES: int = 240  # 4 hours
    GOOGLE_SERVICE_ACCOUNT_JSON: Optional[str] = None
    
    # Meta / Facebook
    META_API_VERSION: str = "v21.0"
    FACEBOOK_PAGE_ID: Optional[str] = None
    FACEBOOK_PAGE_ACCESS_TOKEN: Optional[str] = None
    FACEBOOK_APP_ID: Optional[str] = None
    FACEBOOK_APP_SECRET: Optional[str] = None
    AUTO_PUBLISH: bool = False
    
    # LINE Bot Messaging API
    LINE_CHANNEL_SECRET: Optional[str] = None
    LINE_CHANNEL_ACCESS_TOKEN: Optional[str] = None
    LINE_ADMIN_USER_ID: Optional[str] = None
    
    # AI
    GEMINI_API_KEY: Optional[str] = None
    AI_PROVIDER: str = "gemini"
    AI_MODEL: str = "gemini-2.0-flash"
    
    # Storage
    MAX_STORAGE_MB: int = 2048
    AUTO_CLEANUP_AFTER_DAYS: int = 3
    STORAGE_DIR: Path = BASE_DIR / "storage"
    DOWNLOADS_DIR: Path = BASE_DIR / "storage" / "downloads"
    THUMBNAILS_DIR: Path = BASE_DIR / "storage" / "thumbnails"
    LOGS_DIR: Path = BASE_DIR / "logs"

settings = Settings()
