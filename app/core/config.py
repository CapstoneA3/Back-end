from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://localhost:6379"

    model_config = {"env_file": ".env"}


settings = Settings()
