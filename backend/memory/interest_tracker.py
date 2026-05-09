"""用户兴趣自动学习 — 从分析历史中发现用户关注的高频指标.

核心逻辑：
1. 每次分析完成后，记录该次关注的指标
2. 跨公司聚合 → 发现用户真正关心的指标（如毛利率、销售费用）
3. 后续分析时自动前置展示 + 个性化提示
"""

import json
from backend.logger import logger
from datetime import date, datetime
from typing import Optional

from backend.memory.store import memory_store

# 财务指标同义词映射（归一化）
_METRIC_SYNONYMS = {
    "毛利率": ["毛利率", "毛利"],
    "营收": ["营收", "营业收入", "收入", "总收入"],
    "净利润": ["净利润", "净利", "归母净利润"],
    "销售费用": ["销售费用", "销售"],
    "管理费用": ["管理费用", "管理"],
    "财务费用": ["财务费用", "财务"],
    "ROE": ["ROE", "roe", "净资产收益率", "股东权益回报率"],
    "ROA": ["ROA", "roa", "总资产收益率"],
    "资产负债率": ["资产负债率", "负债率", "杠杆"],
    "现金流": ["现金流", "经营性现金流", "自由现金流"],
    "PE": ["PE", "市盈率", "pe"],
    "PB": ["PB", "市净率", "pb"],
    "研发费用": ["研发费用", "研发", "研发投入"],
    "增长率": ["增长率", "增速", "同比增长", "环比增长"],
}

def normalize_metric(metric: str) -> str:
    """将指标名称归一化到标准名称."""
    for standard, synonyms in _METRIC_SYNONYMS.items():
        if metric in synonyms or any(s in metric for s in synonyms):
            return standard
    return metric

class InterestTracker:
    """用户兴趣跟踪器 — 学习 + 提示生成."""

    def learn_from_analysis(self, metrics: list[str], company_code: str) -> None:
        """从一次分析中学习用户兴趣.

        将用户本次关注的指标记录到 SQLite，并做同义词归一化。
        """
        if not metrics or not company_code:
            return

        try:
            memory_store.connect()
            for raw_metric in metrics:
                normalized = normalize_metric(raw_metric)
                memory_store.record_metric_mention(normalized, company_code)
        except Exception as e:
            logger.warning("兴趣学习失败: %s", e)
    def get_personalized_hint(self, company_code: str = "") -> Optional[str]:
        """生成个性化提示文本.

        Args:
            company_code: 当前分析的公司代码。如果提供，提示会关联该公司已关注的指标。

        Returns:
            提示文本，如 "你之前关注过毛利率、营收，我会前置展示"。
        """
        try:
            memory_store.connect()
            interests = memory_store.get_top_interests(limit=5)
            if not interests:
                return None

            top = interests[:3]
            metrics = []
            for i in top:
                metric = i["metric_name"]
                related = i.get("related_companies", [])
                if company_code and company_code in related:
                    metrics.append(f"**{metric}**（之前分析该公司时关注过）")
                else:
                    metrics.append(f"**{metric}**")

            if not metrics:
                return None

            return "你之前关注过：{}，我会把相关指标放在前面。".format("、".join(metrics))
        except Exception:
            return None
    def get_metric_summary(self, company_code: str = "") -> dict:
        """获取用户兴趣摘要（供前端展示）. """
        try:
            memory_store.connect()
            interests = memory_store.get_top_interests(limit=10)
            companies = memory_store.get_all_watched_companies()
            recent = memory_store.get_all_analysis(limit=5)

            # 公司关注的指标
            company_metrics = {}
            if company_code:
                history = memory_store.get_analysis_history(company_code, limit=20)
                all_metrics = []
                for h in history:
                    all_metrics.extend(h.get("key_metrics_mentioned", []))
                company_metrics[company_code] = list(set(all_metrics))

            return {
                "total_interests": len(interests),
                "top_interests": [
                    {"metric": i["metric_name"], "count": i["mention_count"],
                     "companies": i.get("related_companies", [])}
                    for i in interests
                ],
                "watched_companies": [
                    {"code": c["company_code"], "name": c["company_name"],
                     "count": c["analysis_count"]}
                    for c in companies
                ],
                "recent_analysis": [
                    {"id": r["id"], "company_code": r["company_code"],
                     "question": r["question"][:60],
                     "created_at": r["created_at"]}
                    for r in recent
                ],
                "company_metrics": company_metrics,
            }
        except Exception as e:
            logger.warning("获取兴趣摘要失败: %s", e)
            return {}
# 全局单例
interest_tracker = InterestTracker()
