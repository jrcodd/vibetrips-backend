from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_key: str
    supabase_service_key: str
    
    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Google Maps
    google_maps_api_key: Optional[str] = None
    
    # App
    app_name: str = "VibeTrip API"
    debug: bool = True
    environment: str = "development"
    
    class Config:
        env_file = ".env"

settings = Settings()
