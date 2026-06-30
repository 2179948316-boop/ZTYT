"""Application configuration - loaded from environment variables."""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── LLM ──
    deepseek_api_key: str = os.environ.get("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 4096

    # ── Business Database (target for NL2SQL queries) ──
    biz_db_host: str = "localhost"
    biz_db_port: int = 3306
    biz_db_user: str = "root"
    biz_db_password: str = "123456"
    biz_db_name: str = "ecommerce_demo"

    # ── Application Database (stores conversations, history) ──
    app_db_host: str = "localhost"
    app_db_port: int = 3306
    app_db_user: str = "root"
    app_db_password: str = "123456"
    app_db_name: str = "smart_analyst"

    # ── Redis ──
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 1
    redis_password: str = ""

    # ── Server ──
    host: str = "0.0.0.0"
    port: int = 8001

    @property
    def biz_database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.biz_db_user}:{self.biz_db_password}"
            f"@{self.biz_db_host}:{self.biz_db_port}/{self.biz_db_name}"
        )

    @property
    def biz_async_database_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.biz_db_user}:{self.biz_db_password}"
            f"@{self.biz_db_host}:{self.biz_db_port}/{self.biz_db_name}"
        )

    @property
    def app_database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.app_db_user}:{self.app_db_password}"
            f"@{self.app_db_host}:{self.app_db_port}/{self.app_db_name}"
        )

    @property
    def app_async_database_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.app_db_user}:{self.app_db_password}"
            f"@{self.app_db_host}:{self.app_db_port}/{self.app_db_name}"
        )

    class Config:
        env_file = ".env"


settings = Settings()
