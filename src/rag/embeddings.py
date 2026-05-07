"""嵌入模型封装 — bge-m3 单例.

用法：
    from src.rag.embeddings import embedder
    vec = embedder.embed("query: 茅台2024年营收")
    vecs = embedder.embed_batch(["passage: ...", "passage: ..."])

首次调用会加载模型（约 2GB），后续复用单例。
"""

import logging
from functools import lru_cache
from typing import Optional

import numpy as np

from src.config import settings

logger = logging.getLogger(__name__)


class EmbeddingModel:
    """bge-m3 嵌入模型封装，单例模式."""

    def __init__(self) -> None:
        self._model = None
        self._device: Optional[str] = None
        self._dim = settings.MILVUS_EMBEDDING_DIM

    # ────────── 延迟加载 ──────────

    def _load(self) -> None:
        """首次调用时加载模型."""
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("正在加载嵌入模型: %s ...", settings.EMBEDDING_MODEL)
            self._model = SentenceTransformer(
                settings.EMBEDDING_MODEL,
                device=self._detect_device(),
            )
            self._dim = self._model.get_sentence_embedding_dimension()
            logger.info("嵌入模型加载完成, 维度=%d, 设备=%s", self._dim, self._device)
        except Exception as e:
            logger.warning("嵌入模型加载失败 (%s), 使用 mock 向量: %s", settings.EMBEDDING_MODEL, e)
            self._model = None  # 标记为 mock 模式

    @staticmethod
    def _detect_device() -> str:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        # MPS (Apple Silicon)
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    # ────────── 核心接口 ──────────

    def embed(self, text: str, is_query: bool = False) -> list[float]:
        """将单条文本转为向量.

        Args:
            text: 输入文本。
            is_query: True 自动加 "query: " 前缀，False 加 "passage: "。
        """
        self._load()
        if self._model is None:
            return self._mock_vector()

        prefix = "query: " if is_query else "passage: "
        vec = self._model.encode(prefix + text, normalize_embeddings=True)
        return vec.tolist()

    def embed_batch(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        """批量文本转向量."""
        if not texts:
            return []
        self._load()
        if self._model is None:
            return [self._mock_vector() for _ in texts]

        prefix = "query: " if is_query else "passage: "
        prefixed = [prefix + t for t in texts]
        vecs = self._model.encode(prefixed, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vecs]

    def _mock_vector(self) -> list[float]:
        """模型不可用时返回随机向量（用于开发调试）. """
        rng = np.random.default_rng(42)
        vec = rng.normal(0, 0.1, self._dim).astype(np.float32)
        vec = vec / np.linalg.norm(vec)  # 归一化
        return vec.tolist()

    @property
    def dim(self) -> int:
        self._load()
        return self._dim

    @property
    def is_mock(self) -> bool:
        return self._model is None


# 全局单例
embedder = EmbeddingModel()
