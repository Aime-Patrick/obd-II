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

    # Admin dashboard login (seeded when admin_users collection is empty)
    ADMIN_EMAIL: str = "admin@smartdrivex.com"
    ADMIN_PASSWORD: str = ""
    ADMIN_FULL_NAME: str = "SmartDriveX Admin"
    ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Admin API keys (optional — scripts / legacy)
    ADMIN_API_KEY: str = ""
    ADMIN_BOOTSTRAP_KEY: str = ""
    MIN_LABELED_SAMPLES: int = 50
    MIN_LABELS_PER_CLASS: int = 5
    METRIC_TOLERANCE: float = 0.005  # allow tiny regression vs previous model
    SCHEDULE_RETRAIN_ENABLED: bool = False
    SCHEDULE_RETRAIN_INTERVAL_DAYS: int = 7

    class Config:
        env_file = ".env"
        extra = "ignore"  # ignore unknown env vars like PORT

settings = Settings()
