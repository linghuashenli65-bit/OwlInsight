"""混合检索器 — 语义检索 + BM25 + 时间感知过滤.

流程：
1. 构造时间过滤器表达式 → Milvus expr
2. 语义检索 → VectorStore.search()
3. BM25 检索 → rank_bm25 + jieba
4. RRF 融合 → 加权合并
5. 输出结果送入 reranker
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

import jieba
from rank_bm25 import BM25Okapi

from src.config import settings
from src.rag.embeddings import embedder
from src.rag.vector_store import vector_store

logger = logging.getLogger(__name__)


class BM25Index:
    """BM25 倒排索引（内存中维护，持久化到 JSON）.

    维护 doc_id 映射以支持混合检索时的 RRF 融合。
    """

    def __init__(self) -> None:
        self._corpus: list[str] = []
        self._doc_ids: list[int] = []  # 与 _corpus 一一对应，记录每条文本在 Milvus 中的 doc id
        self._tokenized: list[list[str]] = []
        self._bm25: Optional[BM25Okapi] = None
        self._index_path = settings.DATA_DIR / "vector_store" / "bm25_index.json"

    def rebuild(self, texts: list[str], doc_ids: Optional[list[int]] = None) -> None:
        """重建 BM25 索引.

        Args:
            texts: 文档文本列表。
            doc_ids: 与 texts 一一对应的 Milvus 主键 ID 列表，不传时使用文本匹配回退。
        """
        self._corpus = texts
        self._doc_ids = doc_ids or []
        self._tokenized = [list(jieba.cut(t)) for t in texts]
        self._bm25 = BM25Okapi(self._tokenized)
        logger.info("BM25 索引已重建: %d 篇文档", len(texts))

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        """BM25 检索，返回 [(corpus_index, score), ...].

        corpus_index 可用于访问 _corpus / _doc_ids 获取文本或 Milvus ID。
        """
        if self._bm25 is None:
            return []
        tokenized_query = list(jieba.cut(query))
        scores = self._bm25.get_scores(tokenized_query)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [(idx, score) for idx, score in ranked if score > 0][:top_k]

    def add(self, text: str, doc_id: Optional[int] = None) -> None:
        """增量添加一篇文档."""
        self._corpus.append(text)
        if doc_id is not None:
            self._doc_ids.append(doc_id)
        tokenized = list(jieba.cut(text))
        self._tokenized.append(tokenized)
        # 增量更新 BM25 较复杂，标记需要重建
        self._bm25 = None

    def persist(self) -> None:
        """持久化索引到 JSON."""
        data = {"corpus": self._corpus}
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def load(self) -> bool:
        """从磁盘加载索引."""
        if not self._index_path.exists():
            return False
        with open(self._index_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.rebuild(data.get("corpus", []))
        return True


# 全局 BM25 索引
bm25_index = BM25Index()


# ────────── 时间感知过滤器构造 ──────────

def build_time_filter(
    company_code: str = "",
    period_rank_gte: Optional[int] = None,
    doc_type: str = "",
) -> str:
    """构造 Milvus 布尔过滤表达式.

    Args:
        company_code: 股票代码。
        period_rank_gte: period_rank >= N（如 -3 表示最近三期）。
        doc_type: 文档类型（年报/研报等）。

    Returns:
        Milvus 表达式字符串，如 'company_code == "600519" and period_rank >= -3'
    """
    conditions = []
    if company_code:
        conditions.append(f'company_code == "{company_code}"')
    if period_rank_gte is not None:
        conditions.append(f"period_rank >= {period_rank_gte}")
    if doc_type:
        conditions.append(f'doc_type == "{doc_type}"')

    return " and ".join(conditions) if conditions else ""


# ────────── 混合检索 ──────────

def hybrid_retrieve(
    query: str,
    company_code: str = "",
    period_rank_gte: Optional[int] = None,
    doc_type: str = "",
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """混合检索：语义 + BM25，RRF 融合.

    Args:
        query: 用户问题。
        company_code: 股票代码过滤。
        period_rank_gte: 时间范围过滤，如 -3=最近三期。
        doc_type: 文档类型过滤。
        top_k: 最终返回条数。

    Returns:
        [{"id", "text", "company", ..., "score"}, ...]
    """
    expr = build_time_filter(company_code, period_rank_gte, doc_type)
    top_k_retrieval = max(top_k * 2, settings.RETRIEVAL_TOP_K)

    # ── 1. 语义检索 ──
    query_vec = embedder.embed(query, is_query=True)
    sem_results = vector_store.search(
        query_embedding=query_vec,
        top_k=top_k_retrieval,
        expr=expr if expr else None,
    )
    # idx -> score
    sem_dict = {r.get("id"): r.get("distance", 0) for r in sem_results}

    # ── 2. BM25 检索 ──
    bm25_results = bm25_index.search(query, top_k=top_k_retrieval)

    # ── 3. RRF 融合（语义 + BM25） ──
    rrf_scores: dict[int, float] = {}
    K = 60

    # 语义检索 RRF 贡献
    for rank, hit in enumerate(sem_results):
        doc_id = hit.get("id") or hit.get("pk")
        if doc_id is not None:
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (K + rank + 1)

    # BM25 结果 → Milvus doc_id 映射，参与 RRF
    if bm25_results and bm25_index._corpus:
        # 优先使用 BM25 索引中存储的 doc_id 映射
        has_doc_ids = len(bm25_index._doc_ids) == len(bm25_index._corpus)
        # 文本匹配作为回退（当 doc_ids 未提供时）
        text_to_id: dict[str, int] = {}
        if not has_doc_ids:
            for hit in sem_results:
                doc_id = hit.get("id") or hit.get("pk")
                text = hit.get("text", "")
                if doc_id is not None and text:
                    text_to_id[text] = doc_id

        # 收集 BM25 结果中每个命中的 doc_id
        bm25_scored_ids: list[int] = []
        for corpus_idx, _ in bm25_results:
            doc_id: Optional[int] = None
            if has_doc_ids and corpus_idx < len(bm25_index._doc_ids):
                doc_id = bm25_index._doc_ids[corpus_idx]
            elif corpus_idx < len(bm25_index._corpus):
                doc_id = text_to_id.get(bm25_index._corpus[corpus_idx])
            if doc_id is not None:
                bm25_scored_ids.append(doc_id)

        # BM25 RRF 贡献（去重后按首次出现顺序作为 rank）
        seen: set[int] = set()
        rank = 0
        for doc_id in bm25_scored_ids:
            if doc_id not in seen:
                seen.add(doc_id)
                rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (K + rank + 1)
                rank += 1

    # 排序返回
    ranked_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    id_to_hit = {r.get("id") or r.get("pk"): r for r in sem_results}
    results = []
    for doc_id, score in ranked_ids[:top_k]:
        hit = id_to_hit.get(doc_id)
        if hit:
            h = dict(hit)  # 拷贝，避免污染原始数据
            h["score"] = round(score, 4)
            results.append(h)

    return results


# ────────── 表达式解析（从 LLM 输出） ──────────

def parse_time_filter_from_query(user_query: str) -> dict[str, Any]:
    """从用户问题中解析时间/公司/文档过滤器.

    此函数供 Agent 使用，LLM 提取结构化参数后调用 build_time_filter。
    示例：
        "最近三期利润表有什么变化"
        → {"period_rank_gte": -3, "doc_type": "利润表"}
    """
    filters: dict[str, Any] = {}

    # 时间关键词
    if re.search(r"最近\s*[一二三四五六七八九]?\s*期", user_query):
        m = re.search(r"(\d+)", user_query)
        n = int(m.group(1)) if m else 3
        filters["period_rank_gte"] = -n
    elif re.search(r"去年|上一年", user_query):
        filters["period_rank_gte"] = -4

    # 文档类型
    doc_types = {
        "利润表": "利润表",
        "资产负债表": "资产负债表",
        "现金流量表": "现金流量表",
        "年报": "年报",
        "研报": "研报",
        "财报": "年报",
    }
    for keyword, dt in doc_types.items():
        if keyword in user_query:
            filters["doc_type"] = dt
            break

    return filters
