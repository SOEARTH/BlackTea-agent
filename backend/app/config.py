"""应用配置，从 .env 读取。pydantic-settings 自动加载 cwd 下的 .env。"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 大淘客
    dataoke_app_key: str = ""
    dataoke_app_secret: str = ""

    # LLM
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    model_name: str = "gpt-4o-mini"

    # Embedding (本地 Ollama, qwen3-embedding 4096维)
    embedding_api_key: str = "ollama"
    embedding_api_base: str = "http://localhost:11434/v1"
    embedding_model: str = "qwen3-embedding"
    reranker_model: str = ""  # M3 再接，ollama 本地无 reranker

    # PostgreSQL
    # 注意：宿主机本地有原生 postgres 抢占 5432，Docker PG 映射到 5433
    database_url: str = "postgresql://blacktea:blacktea@localhost:5433/blacktea"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Milvus
    milvus_host: str = "localhost"
    milvus_port: int = 19530

    # LangSmith
    langsmith_api_key: str = ""
    langsmith_project: str = "blacktea"

    # 应用
    secret_key: str = "change-me"
    fixture_record: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
