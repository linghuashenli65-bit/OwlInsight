"""全局配置管理."""

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（无论从哪启动都能找到 .env）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """应用配置，支持环境变量与 .env 文件覆盖.

    优先级：实际环境变量 > .env 文件 > 代码默认值

    使用方式：
        1. 在项目根目录创建 .env 文件（参考 .env.example）
        2. 所有配置项前缀为 FINANCEBOT_，例如 FINANCEBOT_LLM_API_KEY=sk-xxx
        3. 也可直接设置同名环境变量（推荐生产环境）
    """

    model_config = SettingsConfigDict(
        env_prefix="FINANCEBOT_",
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- 项目路径 ----------
    PROJECT_ROOT: Path = _PROJECT_ROOT
    DATA_DIR: Path = _PROJECT_ROOT / "data"

    # ---------- 服务器配置 ----------
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8897
    FRONTEND_URL: str = "http://localhost:3000"

    # ---------- LLM 配置 ----------
    LLM_PROVIDER: str = "openai"  # "openai" | "anthropic"
    LLM_MODEL: str = "gpt-4o"
    LLM_API_KEY: Optional[str] = None
    LLM_API_BASE: Optional[str] = None
    LLM_TEMPERATURE: float = 0.1

    # ---------- Milvus 配置 ----------
    MILVUS_URI: str = "http://localhost:19530"
    MILVUS_COLLECTION: str = "finance_docs"
    MILVUS_EMBEDDING_DIM: int = 512  # bge-small-zh 输出 512 维；bge-m3 为 1024

    # ---------- 嵌入模型 ----------
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"

    # ---------- MySQL 配置 ----------
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "financebot"

    # ---------- 记忆 ----------
    MEMORY_DB_PATH: str = str(DATA_DIR / "memory.db")

    # ---------- 检索参数 ----------
    RETRIEVAL_TOP_K: int = 10
    RERANK_TOP_K: int = 5

    def model_post_init(self, __context) -> None:
        """初始化后回退到旧环境变量名（兼容已有配置）. """
        if self.LLM_API_KEY is None:
            self.LLM_API_KEY = os.getenv("OPENAI_API_KEY")
        if self.LLM_API_BASE is None:
            self.LLM_API_BASE = os.getenv("OPENAI_API_BASE")

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
