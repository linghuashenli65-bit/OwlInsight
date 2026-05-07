"""Pydantic 数据模型."""

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ──────────────────── 文档相关 ────────────────────

class DocMetadata(BaseModel):
    """文档块元数据."""
    chunk_id: str = ""
    company: str = ""
    company_code: str = ""
    doc_type: str = ""  # "年报" | "研报" | "笔记" | "公告"
    doc_name: str = ""
    page_number: Optional[int] = None
    period_rank: Optional[int] = None  # 报告期排序（0=最新, -1=上一期...）
    report_date: Optional[date] = None
    publish_date: Optional[datetime] = None
    table_flag: bool = False
    table_columns: list[str] = Field(default_factory=list)

    def to_milvus_json(self) -> dict[str, Any]:
        """转 Milvus 可写入的 dict."""
        return self.model_dump(mode="json", exclude_none=True)


class Chunk(BaseModel):
    """文档块，含文本和元数据."""
    text: str
    metadata: DocMetadata
    embedding: Optional[list[float]] = None


# ──────────────────── 记忆相关 ────────────────────

class WatchedCompany(BaseModel):
    """用户关注的公司."""
    company_code: str
    company_name: str
    first_analyzed: date
    last_analyzed: date
    analysis_count: int = 0


class AnalysisHistory(BaseModel):
    """分析历史记录."""
    id: Optional[int] = None
    company_code: str
    question: str
    summary: str
    key_metrics_mentioned: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)


class UserInterest(BaseModel):
    """用户高频关注指标."""
    metric_name: str
    mention_count: int = 1
    last_mentioned: date
    related_companies: list[str] = Field(default_factory=list)


# ──────────────────── 金融数据相关 ────────────────────

class FinancialReport(BaseModel):
    """财务报表数据结构."""
    company_code: str
    company_name: str
    report_period: str  # "2024Q4", "2024Q3" ...
    period_rank: int = 0
    revenue: Optional[float] = None         # 营业收入
    net_profit: Optional[float] = None      # 净利润
    gross_profit: Optional[float] = None    # 毛利润
    operating_profit: Optional[float] = None  # 营业利润
    total_assets: Optional[float] = None    # 总资产
    total_liabilities: Optional[float] = None  # 总负债
    cash_flow_operating: Optional[float] = None  # 经营活动现金流
    raw_data: dict[str, Any] = Field(default_factory=dict)  # 原始数据


class StockPrice(BaseModel):
    """股价数据."""
    date: date
    open: float
    close: float
    high: float
    low: float
    volume: int
    adj_close: Optional[float] = None


class Valuation(BaseModel):
    """估值数据."""
    company_code: str
    company_name: str
    pe: Optional[float] = None          # 市盈率
    pb: Optional[float] = None          # 市净率
    ps: Optional[float] = None          # 市销率
    dividend_yield: Optional[float] = None  # 股息率
    hist_pe_percentile: Optional[float] = None   # PE 历史分位数
    hist_pb_percentile: Optional[float] = None   # PB 历史分位数
