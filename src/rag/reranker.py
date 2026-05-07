"""重排序 — Cross-encoder 对检索结果进行精排.

使用 BAAI/bge-reranker-v2-m3，在语义检索粗排后对候选集精排。
"""

import logging
from typing import Any, Optional

from src.config import settings

logger = logging.getLogger(__name__)


class Reranker:
    """Cross-encoder 重排序器，单例模式."""

    def __init__(self) -> None:
        self._model = None
        self._device: Optional[str] = None

    def _load(self) -> None:
        """延迟加载模型. 模型名为空或加载失败时进入 fallback 模式."""
        if self._model is not None:
            return
        # 模型名为空时跳过加载，直接 fallback（常见于开发环境或未配置代理）
        if not settings.RERANKER_MODEL:
            logger.info("重排序模型未配置 (RERANKER_MODEL=空), 跳过加载")
            return
        try:
            from sentence_transformers import CrossEncoder
            logger.info("正在加载重排序模型: %s ...", settings.RERANKER_MODEL)
            self._model = CrossEncoder(
                settings.RERANKER_MODEL,
                device=self._detect_device(),
            )
            logger.info("重排序模型加载完成, 设备=%s", self._device)
        except Exception as e:
            logger.warning("重排序模型加载失败 (%s), 跳过 rerank: %s", settings.RERANKER_MODEL, e)
            self._model = None

    @staticmethod
    def _detect_device() -> str:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """对候选项重排序.

        Args:
            query: 原始用户问题。
            candidates: 检索结果列表，每项需包含 "text" 字段。
            top_k: 返回条数，默认取配置值。

        Returns:
            按相关性降序排列的结果列表，每项新增 "rerank_score" 字段。
        """
        self._load()
        if top_k is None:
            top_k = settings.RERANK_TOP_K

        if self._model is None or not candidates:
            return candidates[:top_k]

        # 构造 (query, passage) 对
        pairs = [(query, c.get("text", "")) for c in candidates]
        scores = self._model.predict(pairs, show_progress_bar=False)

        # 为每个候选项附加 rerank_score
        for i, score in enumerate(scores):
            candidates[i]["rerank_score"] = float(score)

        # 按 rerank 分数降序排列
        reranked = sorted(candidates, key=lambda x: x.get("rerank_score", 0), reverse=True)
        return reranked[:top_k]


# 全局单例
reranker = Reranker()
