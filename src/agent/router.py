"""意图路由器 — 识别用户意图 + 反问澄清 + 多意图拆解.

使用 LLM 对用户输入进行分类：
- financial_query   → 查询财务指标
- price_query       → 查询股价
- news_query        → 搜索新闻
- comparison        → 对比分析
- ambiguous         → 需要反问澄清
- multi_intent      → 需要拆解为并行子任务
"""

import json
import logging
import re
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.agent.state import ToolPlan
from src.config import settings
from src.memory.store import memory_store

logger = logging.getLogger(__name__)

# 意图分类 prompt
_INTENT_CLASSIFY_PROMPT = """你是一个投资研究助手 FinanceBot 的意图分类器。

用户输入：{user_input}

请分析用户意图，输出 JSON（不要 markdown 包裹）：
{{
    "intent": "financial_query | price_query | news_query | comparison | ambiguous | multi_intent",
    "confidence": 0.0~1.0,
    "company": "提取的公司名（可为空）",
    "company_code": "股票代码（可为空）",
    "metrics": ["关注的指标列表"],
    "time_hint": "时间范围描述（可为空，如"最近三期""去年""2024年"）",
    "clarification_question": "如果意图模糊，生成反问句（如"你是想了解股价走势、最近一期财务数据、还是新闻动态？"）；否则为空字符串",
    "sub_intents": ["如果多意图，列出子意图列表，如["财务分析", "新闻搜索"]]"
}}

意图定义：
- financial_query: 查营收/利润/毛利率等财务指标
- price_query: 查股价/走势/技术指标
- news_query: 搜索新闻/公告/动态
- comparison: 多公司对比或同一公司不同时期对比
- ambiguous: 意图非常模糊（如"茅台最近怎么样"），需反问
- multi_intent: 包含多个意图（如"对比财务顺便看新闻"）

注意：
1. 如果用户提到具体公司名，尽量提取 company 和 company_code
2. metrics 提取用户关心的指标名，如["毛利率", "营收", "净利润"]
3. time_hint 提取时间限定词
"""

# 实体提取 prompt（用于模糊意图澄清后的再次判断）
_ENTITY_EXTRACT_PROMPT = """从用户输入中提取投资分析相关的实体信息。

用户输入：{user_input}

输出 JSON：
{{
    "company": "公司名或空字符串",
    "company_code": "股票代码或空字符串（上海 6 开头，深圳 0/3 开头）",
    "metrics": ["关注的财务指标列表"],
    "time_period": "时间范围或空字符串",
    "comparison_targets": ["若涉及对比，列出对比目标公司"]
}}
"""

# 常用 A 股公司名 → 代码映射
_COMMON_STOCKS: dict[str, str] = {
    "茅台": "600519", "贵州茅台": "600519",
    "五粮液": "000858",
    "宁德时代": "300750", "宁王": "300750",
    "比亚迪": "002594", "迪王": "002594",
    "腾讯": "00700", "腾讯控股": "00700",
    "阿里": "09988", "阿里巴巴": "09988",
    "海康威视": "002415",
    "招商银行": "600036",
    "中国平安": "601318",
    "美的集团": "000333",
    "格力电器": "000651",
    "隆基绿能": "601012",
    "药明康德": "603259",
}


def _get_llm() -> ChatOpenAI:
    """获取 LLM 实例."""
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_API_BASE,
    )


def classify_intent(user_input: str) -> dict[str, Any]:
    """分类用户意图，返回结构化结果."""
    try:
        llm = _get_llm()
        prompt = _INTENT_CLASSIFY_PROMPT.format(user_input=user_input)
        messages = [
            SystemMessage(content="你是一个专业的投资研究意图分类器。只返回 JSON。"),
            HumanMessage(content=prompt),
        ]
        response = llm.invoke(messages)
        result = _parse_json(response.content)
        # 清洗 LLM 返回的公司代码：去除交易所后缀（如 600519.SH → 600519）
        if result.get("company_code"):
            result["company_code"] = re.sub(r"\.(SH|SZ|sh|sz)$", "", result["company_code"])
    except Exception as e:
        logger.warning("LLM 意图分类失败 (%s), 使用规则 fallback: %s", e.__class__.__name__, e)
        result = _rule_based_classify(user_input)

    # 补充/补全公司代码
    result = _enrich_company_code(result, user_input)

    # 匹配历史兴趣
    result["matched_interests"] = _match_user_interests(result.get("metrics", []))

    return result


def _parse_json(text: str) -> dict[str, Any]:
    """安全解析 LLM 返回的 JSON."""
    # 去除可能的 markdown 包裹
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _rule_based_classify(user_input: str) -> dict[str, Any]:
    """基于规则的意图分类 fallback."""
    result: dict[str, Any] = {
        "intent": "ambiguous",
        "confidence": 0.5,
        "company": "",
        "company_code": "",
        "metrics": [],
        "time_hint": "",
        "clarification_question": "",
        "sub_intents": [],
    }

    # 关键词匹配（注意：最近、怎么样 等模糊词不单独触发新闻）
    financial_kw = ["营收", "利润", "毛利率", "净利", "收入", "费用", "ROE", "净资产", "负债", "ROA"]
    price_kw = ["股价", "走势", "行情", "K线", "涨", "跌", "开盘", "收盘", "技术分析"]
    news_kw = ["新闻", "公告", "动态", "快讯", "消息", "报道"]
    compare_kw = ["对比", "vs", "VS", "比较", "哪个好", "差距"]
    # 纯模糊查询（无任何金融关键词）
    vague_kw = ["最近", "怎么样", "如何", "表现", "情况", "看看"]

    has_fin = any(kw in user_input for kw in financial_kw)
    has_price = any(kw in user_input for kw in price_kw)
    has_news = any(kw in user_input for kw in news_kw)
    has_compare = any(kw in user_input for kw in compare_kw)

    has_vague = any(kw in user_input for kw in vague_kw)

    sub_intents = []
    if has_fin:
        sub_intents.append("financial_query")
    if has_price:
        sub_intents.append("price_query")
    if has_news:
        sub_intents.append("news_query")
    if has_compare:
        sub_intents.append("comparison")

    if len(sub_intents) > 1 or (has_compare and sub_intents):
        result["intent"] = "multi_intent"
        result["sub_intents"] = list(set(sub_intents))
        result["confidence"] = 0.7
    elif len(sub_intents) == 1:
        result["intent"] = sub_intents[0]
        result["confidence"] = 0.6
    elif has_vague:
        # 纯模糊查询：如"茅台最近怎么样"——没有任何金融/股价/新闻关键词
        # 注意：如果前面有关键词命中，has_vague 不生效。这是有意为之：
        # "看看茅台最近利润"虽然有"看看""最近"但也匹配到"利润"→financial_query
        # 只有在完全无匹配时才触发反问
        result["intent"] = "ambiguous"
        result["confidence"] = 0.4
        result["clarification_question"] = (
            "你是想了解股价走势、最近一期财务数据、还是新闻动态？"
        )
    else:
        # 无法识别的查询
        result["intent"] = "ambiguous"
        result["confidence"] = 0.3
        result["clarification_question"] = (
            "请更具体地描述你想了解的信息，比如「茅台2024年营收」或「五粮液股价走势」"
        )

    return result


def _enrich_company_code(result: dict[str, Any], user_input: str) -> dict[str, Any]:
    """补全公司代码映射."""
    if result.get("company_code"):
        return result

    company = result.get("company", "")
    if not company:
        # 从用户输入中查找
        for name, code in _COMMON_STOCKS.items():
            if name in user_input:
                result["company"] = name
                result["company_code"] = code
                break
    else:
        if company in _COMMON_STOCKS:
            result["company_code"] = _COMMON_STOCKS[company]

    return result


def _match_user_interests(metrics: list[str]) -> list[dict]:
    """匹配历史用户兴趣."""
    if not metrics:
        return []
    try:
        memory_store.connect()
        result = memory_store.get_matching_interests(metrics)
        return result
    except Exception:
        return []
    finally:
        memory_store.close()


def extract_entities(user_input: str) -> dict[str, Any]:
    """提取实体（用于澄清后的第二次分类）. """
    try:
        llm = _get_llm()
        prompt = _ENTITY_EXTRACT_PROMPT.format(user_input=user_input)
        response = llm.invoke([
            SystemMessage(content="只返回 JSON。"),
            HumanMessage(content=prompt),
        ])
        result = _parse_json(response.content)
    except Exception:
        result = {
            "company": "",
            "company_code": "",
            "metrics": [],
            "time_period": "",
            "comparison_targets": [],
        }

    result = _enrich_company_code(result, user_input)
    return result


def extract_company_from_input(user_input: str) -> tuple[str, str]:
    """从输入中提取公司名和代码（轻量版，不调 LLM）. """
    for name, code in _COMMON_STOCKS.items():
        if name in user_input:
            return name, code
    return "", ""


def build_tool_plans(intent_result: dict[str, Any]) -> list[ToolPlan]:
    """根据意图分类结果构建工具调用计划列表."""
    plans: list[ToolPlan] = []
    intent = intent_result.get("intent", "ambiguous")
    company_code = intent_result.get("company_code", "")
    company = intent_result.get("company", "")
    metrics = intent_result.get("metrics", [])
    time_hint = intent_result.get("time_hint", "")

    # 解析时间范围
    period_rank = None
    if "最近" in time_hint:
        m = re.search(r"(\d+)", time_hint)
        n = int(m.group(1)) if m else 3
        period_rank = -n
    elif "去年" in time_hint:
        period_rank = -4

    if intent == "financial_query":
        plans.append(ToolPlan(
            tool_name="query_financials",
            args={"company_code": company_code, "company_name": company,
                  "period_rank_range": [period_rank or -3, 0]},
            description=f"正在获取 {company} 最近几期财务数据...",
        ))
        # 并行检索已导入的财报文档（无论是否有时间范围）
        plans.append(ToolPlan(
            tool_name="read_financial_report",
            args={"company_code": company_code, "company_name": company,
                  "period_rank_gte": period_rank},
            description=f"正在检索已导入的 {company} 财报文档...",
        ))

    elif intent == "price_query":
        plans.append(ToolPlan(
            tool_name="get_stock_price",
            args={"company_code": company_code, "company_name": company},
            description=f"正在获取 {company} 近期股价数据...",
        ))

    elif intent == "news_query":
        plans.append(ToolPlan(
            tool_name="search_news",
            args={"company": company},
            description=f"正在搜索 {company} 相关新闻...",
        ))

    elif intent == "comparison":
        plans.append(ToolPlan(
            tool_name="industry_comparison",
            args={"company_code": company_code, "company_name": company},
            description=f"正在对比 {company} 与同行业公司数据...",
        ))

    elif intent == "multi_intent":
        sub_intents = intent_result.get("sub_intents", [])
        for sub in sub_intents:
            sub_result = dict(intent_result, intent=sub)
            plans.extend(build_tool_plans(sub_result))

    return plans
