"""全局配置管理."""

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置，支持环境变量覆盖."""

    # ---------- 项目路径 ----------
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"

    # ---------- LLM 配置 ----------
    LLM_PROVIDER: str = "openai"  # "openai" | "anthropic"
    LLM_MODEL: str = "gpt-4o"
    LLM_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    LLM_API_BASE: Optional[str] = os.getenv("OPENAI_API_BASE")
    LLM_TEMPERATURE: float = 0.1

    # ---------- Milvus 配置 ----------
    MILVUS_URI: str = "http://localhost:19530"
    MILVUS_COLLECTION: str = "finance_docs"
    MILVUS_EMBEDDING_DIM: int = 1024  # bge-m3 输出的维度

    # ---------- 嵌入模型 ----------
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"

    # ---------- 记忆 ----------
    MEMORY_DB_PATH: str = str(DATA_DIR / "memory.db")

    # ---------- 检索参数 ----------
    RETRIEVAL_TOP_K: int = 10
    RERANK_TOP_K: int = 5

    model_config = {"env_prefix": "FINANCEBOT_", "env_file": ".env", "extra": "ignore"}

    def ensure_dirs(self) -> None:
        """确保所有数据目录存在."""
        dirs = [
            self.DATA_DIR / "vector_store",
            self.DATA_DIR / "research_notes",
            self.DATA_DIR / "knowledge_base" / "financial_reports",
            self.DATA_DIR / "knowledge_base" / "research_reports",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)


# 全局单例
settings = Settings()
