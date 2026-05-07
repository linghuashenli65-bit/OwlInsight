"""新闻搜索工具 — DuckDuckGo."""

import logging
from datetime import date, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


def search_news(
    query: str,
    max_results: int = 5,
    days_back: int = 30,
) -> list[dict[str, Any]]:
    """搜索相关新闻.

    Args:
        query: 搜索关键词。
        max_results: 最多返回条数。
        days_back: 搜索最近 N 天的新闻。

    Returns:
        [{"title", "link", "snippet", "source", "date"}, ...]
    """
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.news(
                keywords=query,
                max_results=max_results,
                timelimit=f"d{days_back}",
            ))
            return [
                {
                    "title": r.get("title", ""),
                    "link": r.get("link", ""),
                    "snippet": r.get("body", r.get("snippet", "")),
                    "source": r.get("source", ""),
                    "date": str(r.get("date", ""))[:10],
                }
                for r in results
            ]
    except ImportError:
        logger.warning("duckduckgo_search 未安装，跳过新闻搜索")
        return []
    except Exception as e:
        logger.warning("新闻搜索失败 (%s): %s", query, e)
        return []
