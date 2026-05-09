"""LangGraph 状态定义.

整个 Agent 工作流的数据结构：
  用户输入 → [classify] → [clarify] → [interests] → [tools] → [hitl] → [synthesize] → 输出
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from langgraph.graph import MessagesState


@dataclass
class ToolPlan:
    """单次工具调用计划."""
    tool_name: str
    args: dict[str, Any]
    description: str  # 显示给用户的步骤描述
    depends_on: list[str] = field(default_factory=list)  # 前置依赖工具


@dataclass
class Citation:
    """引用信息."""
    index: int          # 上标数字
    source: str         # 来源描述
    detail: str         # 详细来源（文件+页码/API名称）


@dataclass
class Anomaly:
    """检测到的异常指标."""
    metric: str
    value: str
    change: str
    description: str


class FinanceBotState(MessagesState):
    """Agent 工作流状态."""

    # ── 意图识别 ──
    intent: Optional[str] = None
    """'financial_query' | 'price_query' | 'news_query' | 'comparison' | 'ambiguous' | 'multi_intent'"""
    intent_confidence: float = 0.0
    clarification_question: Optional[str] = None  # 反问用户的澄清问题

    # ── 实体提取 ──
    company_code: Optional[str] = None
    company_name: Optional[str] = None
    metrics: list[str] = field(default_factory=list)  # ["毛利率", "营收"]
    time_filter: Optional[dict] = None  # {"period_rank_gte": -3}

    # ── 工具执行 ──
    tool_plans: list[ToolPlan] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)

    # ── 流式展示 ──
    streaming_steps: list[str] = field(default_factory=list)
    """逐条显示的思考步骤，如 "正在获取 茅台 最近三期利润表...\""""

    # ── HITL ──
    anomalies: list[Anomaly] = field(default_factory=list)
    hitl_waiting: bool = False
    """True 表示正在等待用户回复 HITL 问题."""

    # ── 输出 ──
    final_answer: Optional[str] = None
    citations: list[Citation] = field(default_factory=list)
    data_status: list[str] = field(default_factory=list)
    """数据状态栏信息，如 "2024Q4现金流量表未获取到，已用Q3数据替代\"""" 
