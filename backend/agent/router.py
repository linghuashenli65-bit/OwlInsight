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
from backend.logger import logger
import re
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from backend.agent.state import ToolPlan
from backend.config import settings
from backend.memory.store import memory_store
from backend.stock_map import COMMON_STOCKS, INDEX_CODES

# 意图分类 prompt
_INTENT_CLASSIFY_PROMPT = """你是一个投资研究助手 FinanceBot 的意图分类器。

用户输入：{user_input}
{context_section}
请分析用户意图，输出 JSON（不要 markdown 包裹）：
{{
    "intent": "financial_query | price_query | news_query | rag_query | comparison | review | deep_report | save_note | ambiguous | multi_intent",
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
- price_query: 查股价/行情数据
- news_query: 搜索新闻/公告/动态
- comparison: 多公司对比或同一公司不同时期对比
- review: 回顾历史分析/之前研究
- deep_report: 生成深度研究报告/全面分析
- save_note: 用户明确要求保存/收藏当前分析到笔记
- rag_query: 搜索已导入的文档/财报内容，用户想查PDF文档里的具体信息
- ambiguous: 意图非常模糊（如"茅台最近怎么样"），需反问；或者包含"预测""走向""会涨吗"等预测性问题（本系统无法预测股价）
- multi_intent: 包含多个意图（如"对比财务顺便看新闻"）

注意：
1. 如果用户提到具体公司名，尽量提取 company 和 company_code
2. 【重要】如果用户没有提及公司名，但对话上下文中最近讨论过某公司，请必须继承该公司并填入 company 和 company_code
3. metrics 提取用户关心的指标名，如["毛利率", "营收", "净利润"]
4. time_hint 提取时间限定词
5. 【重要】"预测""后续走向""会涨吗""能到多少"等预测性问题 → 意图设为 ambiguous，clarification_question 设为 "我无法预测未来股价，但可以帮你分析近期的走势和关键指标，需要吗？"
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

# 大盘指数代码映射（别名，兼容旧代码）
_INDEX_CODES = INDEX_CODES
# 常用公司映射（别名）
_COMMON_STOCKS = COMMON_STOCKS

def _get_llm() -> ChatOpenAI:
    """获取 LLM 实例."""
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_API_BASE,
        request_timeout=30,
        max_retries=1,
    )

def classify_intent(user_input: str, context: str = "") -> dict[str, Any]:
    """分类用户意图，返回结构化结果."""
    try:
        import time
        context_section = f"对话上下文（最近讨论）：{context}" if context else ""
        llm = _get_llm()
        prompt = _INTENT_CLASSIFY_PROMPT.format(user_input=user_input, context_section=context_section)
        messages = [
            SystemMessage(content="你是一个专业的投资研究意图分类器。只返回 JSON。"),
            HumanMessage(content=prompt),
        ]
        t0 = time.time()
        logger.info("LLM 意图分类 → %s ...", user_input[:40])
        response = llm.invoke(messages)
        elapsed = time.time() - t0
        result = _parse_json(response.content)
        logger.info("LLM 意图分类 ← intent=%s confidence=%.2f (%.1fs)",
                    result.get("intent"), result.get("confidence", 0), elapsed)
        # 清洗 LLM 返回的公司代码：去除交易所后缀
        if result.get("company_code"):
            code = re.sub(r"\.(SH|SZ|HK|sh|sz|hk)$", "", result["company_code"])
            if code.isdigit() and len(code) == 4:
                code = "0" + code
            result["company_code"] = code
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

    # 预测类关键词 → 高优匹配，明确告知无法预测
    prediction_kw = ["预测", "走向", "会涨", "会跌", "能到多少", "目标价", "看到多少", "后续"]
    if any(kw in user_input for kw in prediction_kw):
        result["intent"] = "ambiguous"
        result["confidence"] = 0.7
        result["clarification_question"] = "我无法预测未来股价走势，但可以帮你分析近期的走势和关键指标，需要吗？"
        return result

    financial_kw = ["营收", "利润", "毛利率", "净利", "收入", "费用", "ROE", "净资产", "负债", "ROA"]
    price_kw = ["股价", "走势", "行情", "K线", "涨", "跌", "开盘", "收盘", "技术分析"]
    news_kw = ["新闻", "公告", "动态", "快讯", "消息", "报道"]
    rag_search_kw = ["搜索文档", "查文档", "检索", "向量搜索", "文档内容", "财报内容", "搜索财报", "文档搜索"]
    compare_kw = ["对比", "vs", "VS", "比较", "哪个好", "差距"]
    review_kw = ["回顾", "历史分析", "上次分析", "以前", "回想"]
    deep_report_kw = ["深度", "研报", "研究报告", "全面分析"]
    save_note_kw = ["存入笔记", "保存笔记", "保存分析", "记下来", "收藏", "保存"]
    vague_kw = ["最近", "怎么样", "如何", "表现", "情况", "看看"]

    has_fin = any(kw in user_input for kw in financial_kw)
    has_price = any(kw in user_input for kw in price_kw)
    has_news = any(kw in user_input for kw in news_kw)
    has_rag = any(kw in user_input for kw in rag_search_kw)
    has_compare = any(kw in user_input for kw in compare_kw)
    has_review = any(kw in user_input for kw in review_kw)
    has_deep = any(kw in user_input for kw in deep_report_kw)
    has_save = any(kw in user_input for kw in save_note_kw)
    has_vague = any(kw in user_input for kw in vague_kw)

    sub_intents = []
    if has_save:
        result['intent'] = 'save_note'
        result['confidence'] = 0.8
        return result

    if has_deep:
        sub_intents.append('deep_report')
        for name, code in _COMMON_STOCKS.items():
            if name in user_input:
                result['company'] = name
                result['company_code'] = code
                break

    if has_review:
        sub_intents.append("review")
        for name, code in _COMMON_STOCKS.items():
            if name in user_input:
                result["company"] = name
                result["company_code"] = code
                break
    if has_fin:
        sub_intents.append("financial_query")
    if has_price:
        sub_intents.append("price_query")
    if has_news:
        sub_intents.append("news_query")
    if has_rag:
        sub_intents.append("rag_query")
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
        result["intent"] = "ambiguous"
        result["confidence"] = 0.4
        result["clarification_question"] = (
            "你是想了解股价走势、最近一期财务数据、还是新闻动态？"
        )
    else:
        result["intent"] = "ambiguous"
        result["confidence"] = 0.3
        result["clarification_question"] = (
            "请更具体地描述你想了解的信息，比如「茅台2024年营收」或「五粮液股价走势」"
        )

    return result

def _enrich_company_code(result: dict[str, Any], user_input: str) -> dict[str, Any]:
    """补全公司/指数代码映射."""
    if result.get("company_code"):
        return result

    company = result.get("company", "")
    search_text = company if company else user_input

    for name, code in _INDEX_CODES.items():
        if name in search_text:
            result["company"] = name
            result["company_code"] = code
            return result

    for name, code in _COMMON_STOCKS.items():
        if name in search_text:
            result["company"] = name
            result["company_code"] = code
            break

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

def _extract_multiple_companies(intent_result: dict) -> list[tuple[str, str]]:
    """从意图结果中提取多家公司 (name, code)."""
    seen = set()
    result = []
    # 从 comparison_targets 提取
    for target in intent_result.get("comparison_targets", []):
        for name, code in _COMMON_STOCKS.items():
            if name in target and code not in seen:
                seen.add(code)
                result.append((name, code))
                break
    # 从 company 和 user_query 补充
    user_query = intent_result.get("user_query", "")
    if not result and user_query:
        for name, code in _COMMON_STOCKS.items():
            if name in user_query and code not in seen:
                seen.add(code)
                result.append((name, code))
    return result


def extract_company_from_input(user_input: str) -> tuple[str, str]:
    """从输入中提取公司名或指数代码（轻量版，不调 LLM）. """
    for name, code in _INDEX_CODES.items():
        if name in user_input:
            return name, code
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

    # 需要公司代码的意图但没有提取到公司 → 返回空计划
    if company_code == "" and intent in ("financial_query", "price_query", "comparison", "review"):
        return plans

    if intent == "financial_query":
        plans.append(ToolPlan(
            tool_name="query_financials",
            args={"company_code": company_code, "company_name": company,
                  "period_rank_range": [period_rank or -3, 0]},
            description=f"正在获取 {company} 最近几期财务数据...",
        ))
        plans.append(ToolPlan(
            tool_name="read_financial_report",
            args={"company_code": company_code, "company_name": company,
                  "period_rank_gte": period_rank,
                  "query": intent_result.get("user_query", "")},
            description=f"正在检索已导入的 {company} 财报文档...",
        ))

    elif intent == "price_query":
        from datetime import date, timedelta
        start_date = None
        if "最近" in time_hint:
            import re as _re2
            m = _re2.search(r"(\d+)", time_hint)
            n = int(m.group(1)) if m else 3
            start_date = (date.today() - timedelta(days=n * 30)).strftime("%Y%m%d")
        elif "今年" in time_hint:
            start_date = f"{date.today().year}0101"
        plans.append(ToolPlan(
            tool_name="get_stock_price",
            args={"company_code": company_code, "company_name": company,
                  "start_date": start_date},
            description=f"正在获取 {company} 近期股价数据...",
        ))

    elif intent == "news_query":
        search_query = intent_result.get("user_query", "") or company or "财经新闻"
        plans.append(ToolPlan(
            tool_name="search_news",
            args={"company": search_query},
            description=f"正在搜索 {search_query[:40]}...",
        ))

    elif intent == "rag_query":
        user_query = intent_result.get("user_query", "")
        plans.append(ToolPlan(
            tool_name="search_documents",
            args={
                "query": user_query,
                "company_code": company_code,
                "company_name": company,
                "top_k": 5,
            },
            description=f"正在搜索已导入文档中的相关内容...",
        ))

    elif intent == "comparison":
        # 提取多个公司
        companies = _extract_multiple_companies(intent_result)
        if len(companies) >= 2:
            codes = [c[1] for c in companies]
            names = [c[0] for c in companies]
            plans.append(ToolPlan(
                tool_name="compare_companies",
                args={"company_codes": codes, "company_names": names},
                description=f"正在对比 {' vs '.join(names[:3])} 的财务数据...",
            ))
        else:
            plans.append(ToolPlan(
                tool_name="industry_comparison",
                args={"company_code": company_code, "company_name": company or company_code},
                description=f"正在对比 {company or company_code} 与同行业数据...",
            ))

    elif intent == "deep_report":
        plans.append(ToolPlan(
            tool_name="generate_report",
            args={"company_code": company_code, "company_name": company or company_code},
            description=f"正在生成 {company or company_code} 深度研究报告...",
        ))
        plans.append(ToolPlan(
            tool_name="search_documents",
            args={"query": f"{company}年报 财报 经营情况",
                  "company_code": company_code,
                  "company_name": company,
                  "top_k": 5},
            description=f"正在检索文档库中 {company} 的相关资料...",
        ))

    elif intent == "review":
        plans.append(ToolPlan(
            tool_name="review_analysis",
            args={"company_code": company_code, "company_name": company or company_code,
                  "keyword": time_hint or company},
            description=f"正在回顾 {company or company_code} 的历史分析记录...",
        ))

    elif intent == "save_note":
        plans.append(ToolPlan(
            tool_name="save_last_note",
            args={},
            description="正在保存到研究笔记...",
        ))

    elif intent == "multi_intent":
        sub_intents = intent_result.get("sub_intents", [])
        for sub in sub_intents:
            sub_result = dict(intent_result, intent=sub)
            plans.extend(build_tool_plans(sub_result))

    return plans
