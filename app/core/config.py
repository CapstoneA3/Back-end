from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://localhost:6379"
    supabase_url: str
    supabase_anon_key: str
    docs_username: str
    docs_password: str
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_file": (".env", ".env.local"), "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
