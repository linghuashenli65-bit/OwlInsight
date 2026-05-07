"""RAG 检索工具 — 支持时间感知."""

import logging
from typing import Any, Optional

from src.rag.retriever import hybrid_retrieve

logger = logging.getLogger(__name__)


def read_financial_report(
    company_code: str = "",
    company_name: str = "",
    period_rank_gte: Optional[int] = None,
    query: str = "",
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """从已导入的财报文档中检索信息（支持时间感知）.

    Args:
        company_code: 股票代码。
        company_name: 公司名（用于构造搜索 query）。
        period_rank_gte: period_rank >= N，如 -3 表示最近三期。
        query: 用户问题原文（可选）。
        top_k: 返回条数。

    Returns:
        [{id, text, company, page_number, period_rank, score}, ...]
    """
    search_query = query or f"{company_name}财务数据"
    results = hybrid_retrieve(
        query=search_query,
        company_code=company_code,
        period_rank_gte=period_rank_gte,
        top_k=top_k,
    )
    return results


def search_research_reports(
    company_code: str = "",
    company_name: str = "",
    query: str = "",
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """搜索已导入的券商研报."""
    search_query = query or f"{company_name}研报"
    return hybrid_retrieve(
        query=search_query,
        company_code=company_code,
        doc_type="研报",
        top_k=top_k,
    )
