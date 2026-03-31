from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGODB_URL: str
    DATABASE_NAME: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Email Settings
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = "noreply@smartdrivex.com"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_FROM_NAME: str = "SmartDriveX"
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    USE_CREDENTIALS: bool = True
    VALIDATE_CERTS: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"  # ignore unknown env vars like PORT

settings = Settings()
