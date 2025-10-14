# from typing import Optional
# from pydantic_settings import BaseSettings, SettingsConfigDict

# class Settings(BaseSettings):
#     # Application
#     APP_NAME: str = "SmartBag"
#     DEBUG: bool = False
#     PORT: int = 8000
    
#     # Security
#     SECRET_KEY: str
#     ALGORITHM: str = "HS256"
#     ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

#     # Cloudinary settings
#     cloudinary_cloud_name: Optional[str] = None
#     cloudinary_api_key: Optional[str] = None
#     cloudinary_api_secret: Optional[str] = None
    
#     # Database
#     MONGO_URI: str
#     DB_NAME: str = "smartbag"
    
#     # CORS
#     ALLOWED_ORIGINS: str = "http://localhost:3000"
    
#     model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

# settings = Settings()

# db/config.py - Updated to include Ola Krutrim API key
from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    # Database settings
    mongo_url: str = "mongodb://localhost:27017"
    db_name: str = "smartbag"
    
    # JWT settings
    secret_key: str = "your-secret-key-here"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    
    # API settings
    api_version: str = "v1"
    
    # Ola Krutrim Maps API
    ola_krutrim_api_key: Optional[str] = None
    
    class Config:
        # Allow extra fields and read from environment variables
        extra = "allow"  # This allows extra fields
        env_file = ".env"
        env_file_encoding = 'utf-8'
        case_sensitive = False
        
        # Environment variable names (optional - pydantic auto-detects)
        fields = {
            'mongo_url': {'env': 'MONGO_URL'},
            'db_name': {'env': 'DB_NAME'},
            'secret_key': {'env': 'SECRET_KEY'},
            'algorithm': {'env': 'ALGORITHM'},
            'access_token_expire_minutes': {'env': 'ACCESS_TOKEN_EXPIRE_MINUTES'},
            'ola_krutrim_api_key': {'env': 'OLA_KRUTRIM_API_KEY'},
        }

# Create settings instance
settings = Settings()

# Also make the Ola Krutrim API key available directly
OLA_KRUTRIM_API_KEY = settings.ola_krutrim_api_key or os.getenv('OLA_KRUTRIM_API_KEY')