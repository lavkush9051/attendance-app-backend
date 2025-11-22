
try:
    from pydantic import BaseSettings  # Works for Pydantic v1
except ImportError:
    from pydantic_settings import BaseSettings 
import os
from typing import Optional, List

class Settings(BaseSettings):
    # Base settings
    PROJECT_NAME: str = "Face Recognition Service"
    API_V1_PREFIX: str = "/api/v1"
    FACE_RECOGNITION_TOLERANCE: float = 0.6
    MAX_FACE_DISTANCE: float = 0.6
    MAX_UPLOAD_SIZE: int = 10485760  # 10MB
    ALLOWED_IMAGE_EXTENSIONS: str = "jpg,jpeg,png,gif,bmp"
    
    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    
    # API settings
    API_HOST: str = "0.0.0.0"
    API_PORT: str = "8000"
    DEBUG: bool = False
    FRONTEND_URL: str = "http://localhost:3000"
    TIMEZONE: str = "Asia/Kolkata"
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # Database settings
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "attendance_db")
    DATABASE_URL: str = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}"
    
    # SAP environment selector: "dev" or "prod"
    SAP_ENV: str = os.getenv("SAP_ENV", "dev")

    # SAP Development Integration settings
    SAP_DEV_BASE_URL: str = "http://10.100.30.73:8000"  # Base URL without endpoint
    SAP_DEV_ATTENDANCE_PATH: str = "/ZPUNCH55"  # Attendance endpoint path
    SAP_DEV_LEAVE_PATH: str = "/ZLEAVE55"  # Leave endpoint path
    SAP_DEV_USERNAME: str = "ADMIN_JRD"
    SAP_DEV_PASSWORD: str = "Welcome@@jnpa25"
    SAP_DEV_CLIENT: str = "200"
    SAP_DEV_SEND_VIA: str = "sap"  # 'sap' sends directly to SAP from backend

    # SAP Production Integration settings
    SAP_PROD_BASE_URL: str = "https://sapbiometric.jnpa.in"  # Base URL without endpoint
    SAP_PROD_ATTENDANCE_PATH: str = "/ZPUNCH55"  # Attendance endpoint path
    SAP_PROD_LEAVE_PATH: str = "/ZLEAVE55"  # Leave endpoint path
    SAP_PROD_USERNAME: str = "SAPSUPPORT5"
    SAP_PROD_PASSWORD: str = "Kesavi@@jnpa12"
    SAP_PROD_CLIENT: str = "400"
    SAP_PROD_SEND_VIA: str = "sap"  # 'sap' sends directly to SAP from backend

    # Common
    SHIFT_SYNC_BUFFER: int = 0  # hours after shift end to sync

    # Expose active SAP settings via computed properties to keep public API stable
    @property
    def SAP_BASE_URL(self) -> str:
        return self.SAP_DEV_BASE_URL if self.SAP_ENV.lower() == "dev" else self.SAP_PROD_BASE_URL

    @property
    def SAP_ATTENDANCE_PATH(self) -> str:
        return self.SAP_DEV_ATTENDANCE_PATH if self.SAP_ENV.lower() == "dev" else self.SAP_PROD_ATTENDANCE_PATH

    @property
    def SAP_LEAVE_PATH(self) -> str:
        return self.SAP_DEV_LEAVE_PATH if self.SAP_ENV.lower() == "dev" else self.SAP_PROD_LEAVE_PATH

    @property
    def SAP_USERNAME(self) -> str:
        return self.SAP_DEV_USERNAME if self.SAP_ENV.lower() == "dev" else self.SAP_PROD_USERNAME

    @property
    def SAP_PASSWORD(self) -> str:
        return self.SAP_DEV_PASSWORD if self.SAP_ENV.lower() == "dev" else self.SAP_PROD_PASSWORD

    @property
    def SAP_CLIENT(self) -> str:
        return self.SAP_DEV_CLIENT if self.SAP_ENV.lower() == "dev" else self.SAP_PROD_CLIENT

    @property
    def SAP_SEND_VIA(self) -> str:
        return self.SAP_DEV_SEND_VIA if self.SAP_ENV.lower() == "dev" else self.SAP_PROD_SEND_VIA
    
    # JWT settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Storage settings
    UPLOAD_DIRECTORY: str = "uploads"
    FACE_DATA_DIRECTORY: str = "face_data"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()