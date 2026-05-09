"""LangGraph Agent 工作流图.

Nodes:
  1. classify  — 意图分类 & 实体提取
  2. clarify   — 反问澄清后二次分类
  3. interests — 匹配历史关注点
  4. execute   — 并行执行工具
  5. checkpoint — HITL 检查点
  6. synthesize — 合成最终答案

Edges:
  classify → ambiguous → clarify → classify
  classify → clear → interests → execute → checkpoint → synthesize → END
"""

from backend.logger import logger
from typing import Any, Optional

from langgraph.graph import END, StateGraph

from backend.agent.router import (
    build_tool_plans,
    classify_intent,
    extract_entities,
    extract_company_from_input,
)
from backend.agent.state import Anomaly, FinanceBotState, ToolPlan
from backend.agent.synthesizer import Synthesizer, synthesizer
from backend.memory.store import memory_store

# ────────── Nodes ──────────

def _msg_text(m: Any) -> str:
    """安全获取消息文本（兼容 dict 和 LangChain Message 对象）. """
    if isinstance(m, dict):
        return m.get("content", "") or ""
    return getattr(m, "content", "") or ""


def _msg_role(m: Any) -> str:
    if isinstance(m, dict):
        return m.get("role", "user")
    return getattr(m, "role", "user")


def classify_node(state: FinanceBotState) -> dict[str, Any]:
    """意图分类节点，支持多轮上下文。"""
    messages = state.get("messages", [])
    if not messages:
        return {"intent": "ambiguous", "streaming_steps": []}

    user_input = _msg_text(messages[-1])

    # 构建对话上下文（最近 3 轮）
    context_parts = []
    for m in messages[-6:-1]:
        role = _msg_role(m)
        content = _msg_text(m)
        if role == "assistant" and content:
            context_parts.append(f"AI: {content[:80]}")
        elif role == "user" and content:
            context_parts.append(f"User: {content}")
    context = " | ".join(context_parts[-3:])

    intent_result = classify_intent(user_input, context=context)

    # Fallback: LLM 没提取到公司代码时，从历史消息中查找
    if not intent_result.get("company_code") and len(messages) > 1:
        for m in messages[-4:-1]:  # 最近几轮用户消息
            text = _msg_text(m)
            role = _msg_role(m)
            if role == "user" and text:
                name, code = extract_company_from_input(text)
                if code:
                    intent_result["company_code"] = code
                    intent_result["company"] = name or code
                    break

    intent_result["user_query"] = user_input
    tool_plans = build_tool_plans(intent_result)

    streaming = []
    if intent_result.get("matched_interests"):
        names = [i.get("metric_name", "")
                 for i in intent_result["matched_interests"][:3]]
        streaming.append(f"[提示] 历史分析显示你关注过：{'、'.join(names)}")

    return {
        "intent": intent_result.get("intent", "ambiguous"),
        "intent_confidence": intent_result.get("confidence", 0.0),
        "company_code": intent_result.get("company_code", ""),
        "company_name": intent_result.get("company", ""),
        "metrics": intent_result.get("metrics", []),
        "clarification_question": intent_result.get("clarification_question", ""),
        "tool_plans": tool_plans,
        "tool_results": [],
        "streaming_steps": streaming,
    }

def clarify_node(state: FinanceBotState) -> dict[str, Any]:
    """反问澄清节点（只输出反问，等待用户回复）. """
    q = state.get("clarification_question", "你想了解哪方面信息？")
    return {
        "final_answer": q,
        "hitl_waiting": True,
    }

def interests_node(state: FinanceBotState) -> dict[str, Any]:
    """匹配用户历史关注点（增强体验）. """
    metrics = state.get("metrics", [])
    company_code = state.get("company_code", "")

    streaming = list(state.get("streaming_steps", []))

    if metrics and company_code:
        try:
            memory_store.connect()
            for m in metrics:
                memory_store.record_metric_mention(m, company_code)
        except Exception:
            pass
    return {"streaming_steps": streaming}

def execute_node(state: FinanceBotState) -> dict[str, Any]:
    """执行工具节点（按计划串行/并行执行）. """
    plans = state.get("tool_plans", [])
    existing_results = list(state.get("tool_results", []))
    streaming = list(state.get("streaming_steps", []))
    data_status = list(state.get("data_status", []))
    citations = list(state.get("citations", []))

    for plan in plans:
        streaming.append(plan.description)

        try:
            result = _run_tool(plan, state)
            result["tool"] = plan.tool_name
            if plan.tool_name == "save_last_note":
                if result.get("message"):
                    data_status.append(result["message"])
                if result.get("status") == "error":
                    data_status.append(str(result.get("error", "保存失败")))
            elif result.get("status") == "ok" and result.get("data"):
                existing_results.append(result)
            if result.get("status") == "partial":
                existing_results.append(result)
                if result.get("message"):
                    data_status.append(result["message"])
        except Exception as e:
            logger.error("工具执行失败 %s: %s", plan.tool_name, e)
            existing_results.append({
                "tool": plan.tool_name,
                "status": "error",
                "error": str(e),
                "data": None,
            })

    return {
        "tool_results": existing_results,
        "streaming_steps": streaming,
        "data_status": data_status,
    }

def checkpoint_node(state: FinanceBotState) -> dict[str, Any]:
    """HITL 检查点：检测异常，暂停问用户是否深入. """
    results = state.get("tool_results", [])
    anomalies: list[Anomaly] = []
    streaming = list(state.get("streaming_steps", []))

    # 简单异常检测：检查利润表数据中的大幅变化
    for r in results:
        if r.get("tool") == "query_financials" and r.get("data"):
            data = r["data"]
            if isinstance(data, list) and len(data) >= 2:
                # 对比最新两期
                latest = data[0] if data[0].get("period_rank", -999) >= data[1].get("period_rank", -999) else data[1]
                prev = data[1] if data[0].get("period_rank", -999) >= data[1].get("period_rank", -999) else data[0]

                for metric, label in [("revenue", "营收"), ("net_profit", "净利润")]:
                    cur_val = latest.get(metric)
                    prev_val = prev.get(metric)
                    if cur_val and prev_val and prev_val != 0:
                        change_pct = (cur_val - prev_val) / abs(prev_val) * 100
                        if abs(change_pct) > 20:
                            direction = "增长" if change_pct > 0 else "下降"
                            anomalies.append(Anomaly(
                                metric=label,
                                value=Synthesizer._fmt_money(cur_val),
                                change=f"{direction} {abs(change_pct):.1f}%",
                                description=f"环比{label}变化 {change_pct:+.1f}%",
                            ))

    if anomalies:
        streaming.append(f"发现 {len(anomalies)} 个异常指标，等待你的选择...")
        streaming.append(synthesizer._build_anomaly_prompt(anomalies))

    return {
        "anomalies": anomalies,
        "hitl_waiting": bool(anomalies),
        "streaming_steps": streaming,
    }

def synthesize_node(state: FinanceBotState) -> dict[str, Any]:
    """合成最终答案 + 返回 note_info 供前端弹确认."""
    results = state.get("tool_results", [])
    citations = list(state.get("citations", []))
    anomalies = state.get("anomalies", [])
    data_status = state.get("data_status", [])
    company_name = state.get("company_name", "")
    company_code = state.get("company_code", "")
    metrics = state.get("metrics", [])
    streaming = list(state.get("streaming_steps", []))

    # 生成答案
    answer = synthesizer.synthesize(
        user_query=state["messages"][-1].content if state.get("messages") else "",
        tool_results=results,
        citations=citations,
        anomalies=anomalies,
        data_status=data_status,
    )

    # 记录分析历史（轻量，不存全文）
    if company_code:
        try:
            memory_store.connect()
            memory_store.add_or_update_company(company_code, company_name or company_code)
            memory_store.add_analysis(
                company_code=company_code,
                question=state["messages"][-1].content if state.get("messages") else "",
                summary=answer[:200] if answer else "",
                metrics=metrics,
            )
        except Exception:
            pass

    # 不再自动保存笔记 — 返回 note_info 供前端弹确认
    note_info = None
    if company_code and answer:
        note_info = {
            "company_code": company_code,
            "company_name": company_name or company_code,
            "title": "",  # 保存时由 LLM 自动生成
            "content": answer,
            "metrics": metrics,
            "tags": [company_name or company_code] + (metrics[:3] if metrics else []),
        }

    return {
        "final_answer": answer,
        "citations": citations,
        "streaming_steps": streaming,
        "note_info": note_info,
    }

def _build_search_context(state: Optional[FinanceBotState]) -> str:
    """从 agent state 构建搜索上下文."""
    if not state:
        return ""
    messages = state.get("messages", [])
    if len(messages) < 2:
        return ""
    ctx_parts = []
    for m in messages[-4:-1]:
        text = _msg_text(m)
        role = _msg_role(m)
        if role == "user" and text:
            ctx_parts.append(str(text)[:60])
    return " | ".join(ctx_parts[-2:])


# ────────── 工具执行器 ──────────

def _run_tool(plan: ToolPlan, state: Optional[dict] = None) -> dict[str, Any]:
    """执行单个工具调用."""
    tool_name = plan.tool_name
    args = plan.args

    if tool_name == "query_financials":
        from backend.tools.financial_data import get_financials
        code = args.get("company_code", "")
        if not code:
            return {"status": "empty", "data": [],
                    "message": "未指定公司代码，无法查询财务数据"}
        data = get_financials(code)
        if data:
            # 按 period_rank 过滤
            rank_range = args.get("period_rank_range", None)
            if rank_range:
                data = [d for d in data if rank_range[0] <= (d.get("period_rank") or 0) <= rank_range[1]]
            return {"status": "ok", "data": data}
        return {"status": "empty", "data": []}

    elif tool_name == "get_stock_price":
        from backend.tools.financial_data import get_stock_price_history
        code = args.get("company_code", "")
        if not code:
            return {"status": "empty", "data": [],
                    "message": "未指定公司代码，无法获取股价"}
        sd = args.get("start_date")
        data = get_stock_price_history(code, start_date=sd) if sd else get_stock_price_history(code)
        if data:
            return {"status": "ok", "data": data}
        return {"status": "empty", "data": [],
                "message": "股价接口因网络限制不可用（公司代理拦截）"}

    elif tool_name == "search_news":
        from backend.tools.news_search import search_news as _search_news
        query = args.get("company_name", args.get("company", ""))
        if not query:
            query = "财经新闻"  # 兜底
        # 从 agent state 获取对话上下文
        context = _build_search_context(state)
        news = _search_news(query=query, max_results=5, context=context)
        if news:
            return {"status": "ok", "data": news}
        return {"status": "empty", "data": [],
                "message": f"未搜索到 {company} 相关新闻"}


    elif tool_name == "save_last_note":
        messages = state.get("messages", []) if state else []
        last_assistant = ""
        company_code = ""
        company_name = ""
        if state:
            company_code = state.get("company_code", "") or ""
            company_name = state.get("company_name", "") or ""
        for m in reversed(messages):
            text = _msg_text(m)
            role = _msg_role(m)
            if role == "assistant" and text and not last_assistant:
                last_assistant = text
            if role == "user" and text and not company_code:
                from backend.agent.router import extract_company_from_input
                name, code = extract_company_from_input(text)
                if code:
                    company_code = code
                    company_name = name or code

        # 优先用助理回复（两轮对话场景），否则从 tool_results 拼接笔记内容
        if not last_assistant:
            tool_results = state.get("tool_results", []) if state else []
            if tool_results:
                parts = []
                for r in tool_results:
                    t = r.get("tool", "")
                    data = r.get("data")
                    if data:
                        if t == "query_financials" and isinstance(data, list):
                            rows = data[:3]
                            for row in rows:
                                name_v = row.get("company_name", row.get("symbol", ""))
                                period = str(row.get("report_period", ""))[:10]
                                rev = row.get("revenue")
                                np_ = row.get("net_profit")
                                parts.append(f"{name_v} ({period}): 营收={rev}, 净利润={np_}")
                        elif t == "get_stock_price" and isinstance(data, list):
                            if data:
                                last = data[-1]
                                parts.append(f"股价({last.get('date','')}): 收盘{last.get('close','')}")
                        elif isinstance(data, list):
                            for item in data[:2]:
                                if isinstance(item, dict):
                                    items = [f"{k}={v}" for k, v in item.items() if v is not None and k != "raw_data"]
                                    if items:
                                        parts.append(", ".join(items))
                        elif isinstance(data, dict):
                            items = [f"{k}={v}" for k, v in data.items() if v is not None]
                            if items:
                                parts.append(", ".join(items))
                if parts:
                    last_assistant = "\n".join(parts)
            if not last_assistant:
                # 从用户输入提取作为笔记内容
                user_msgs = [_msg_text(m) for m in messages if _msg_role(m) == "user"]
                if user_msgs:
                    last_assistant = "用户查询: " + " | ".join(user_msgs[-2:])

        if not last_assistant:
            return {"status": "empty", "data": [], "message": "没有可保存的分析内容"}
        # LLM 生成标题和摘要
        title = _generate_note_summary(last_assistant, company_name or company_code)
        abstract = _generate_note_abstract(last_assistant)
        # 标题 + 摘要说明 + 原始内容
        final_content = f"## {abstract}\n\n{last_assistant}" if abstract else last_assistant
        memory_store.connect()
        note_id = memory_store.upsert_note(
            company_code=company_code or "general",
            company_name=company_name or "通用",
            title=title,
            content=final_content,
            tags=[company_name or "通用", "用户保存"],
        )
        company_tag = f" [{company_name}]" if company_name else ""
        return {"status": "ok", "data": {"note_id": note_id},
                "message": f"笔记已保存{company_tag}"}

    elif tool_name == "generate_report":
        from backend.tools.financial_data import get_financials, get_stock_price_history, get_valuation_data
        from backend.tools.news_search import search_news as _search_news
        code = args.get("company_code", "")
        name = args.get("company_name", "")
        if not code:
            return {"status": "empty", "data": [], "message": "未指定公司代码"}
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            f_fin = pool.submit(get_financials, code)
            f_price = pool.submit(get_stock_price_history, code)
            f_val = pool.submit(get_valuation_data, code)
            f_news = pool.submit(_search_news, query=name or code, max_results=3)
        report = {
            "company_code": code,
            "company_name": name or code,
            "financials": f_fin.result() or [],
            "price_history": f_price.result() or [],
            "valuation": f_val.result() or {},
            "news": f_news.result() or [],
        }
        return {"status": "ok", "data": report}

    elif tool_name == "compare_companies":

        from backend.tools.financial_data import get_financials
        codes = args.get("company_codes", [])
        names = args.get("company_names", [])
        if len(codes) < 2:
            return {"status": "empty", "data": [], "message": "需要至少两家公司才能对比"}
        all_data = {}
        for code, name in zip(codes, names):
            fin = get_financials(code)
            if fin:
                all_data[name or code] = fin[:4]  # 最近 4 期
        if len(all_data) < 2:
            return {"status": "empty", "data": [], "message": "无法获取对比数据"}
        return {"status": "ok", "data": {"companies": all_data, "metrics": ["revenue", "net_profit"]}}

    elif tool_name == "industry_comparison":
        from backend.tools.valuation import industry_comparison as _industry_comp
        code = args.get("company_code", "")
        comp_data = _industry_comp(company_code=code)
        if comp_data:
            return {"status": "ok", "data": comp_data}
        return {"status": "empty", "data": [],
                "message": "行业对比数据不可用"}

    elif tool_name == "read_financial_report":
        from backend.rag.retriever import hybrid_retrieve
        code = args.get("company_code", "")
        period = args.get("period_rank_gte")
        company_name = args.get("company_name", "")
        user_query = args.get("query", "")
        query = user_query if user_query else f"{company_name}利润表营收"
        data = hybrid_retrieve(
            query=query,
            company_code=code,
            period_rank_gte=period,
            top_k=5,
        )
        if data:
            return {"status": "ok", "data": data}

        # 降级：不限制公司代码
        data = hybrid_retrieve(query=query, period_rank_gte=period, top_k=5)
        if data:
            return {"status": "ok", "data": data,
                    "message": "未找到限定公司的文档内容，已展示其他相关结果"}

        return {"status": "empty", "data": []}

    elif tool_name == "search_documents":
        from backend.rag.retriever import hybrid_retrieve
        query = args.get("query", "")
        company_code = args.get("company_code", "")
        company_name = args.get("company_name", "")
        top_k = args.get("top_k", 5)
        if not query:
            return {"status": "empty", "data": [], "message": "未指定搜索内容"}

        # 先用公司代码过滤检索
        data = hybrid_retrieve(
            query=query,
            company_code=company_code,
            top_k=top_k,
        )
        if data:
            return {"status": "ok", "data": data, "message": f"从文档中找到 {len(data)} 条相关内容"}

        # 公司代码过滤无结果时，降级为全文搜索（应对文档元数据代码不匹配的情况）
        logger.info("公司代码 %s 过滤无结果，降级为全文搜索", company_code)
        data = hybrid_retrieve(query=query, top_k=top_k)
        if data:
            return {"status": "ok", "data": data,
                    "message": f"从文档中找到 {len(data)} 条相关内容（未限定公司）"}

        return {"status": "empty", "data": [], "message": "未在已导入文档中找到相关内容"}

    elif tool_name == "review_analysis":
        code = args.get("company_code", "")
        company_name = args.get("company_name", "")
        keyword = args.get("keyword", "")
        try:
            memory_store.connect()
            history = memory_store.search_analysis(keyword or company_name, limit=5)
            return {"status": "ok", "data": history}
        except Exception as e:
            return {"status": "error", "data": None, "error": str(e)}
    return {"status": "error", "data": None, "error": f"未知工具: {tool_name}"}


# ────────── LLM 笔记摘要 ──────────

def _generate_note_summary(content: str, company: str) -> str:
    """用 LLM 生成笔记标题（简短概括）. """
    from backend.config import settings
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage
    try:
        llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0.3,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
            request_timeout=15,
        )
        text = content[:2000]
        resp = llm.invoke([
            SystemMessage(content="你是一个投资研究笔记助手。用一句话（20字以内）概括以下分析笔记的核心主题，直接输出标题，不要引号和多余内容。"),
            HumanMessage(content=f"公司：{company}\n分析内容：{text}"),
        ])
        title = resp.content.strip().strip('"').strip("'").strip()
        return title[:60] if title else company
    except Exception:
        return company


def _generate_note_abstract(content: str) -> str:
    """用 LLM 生成一段简短的说明（100字以内）. """
    from backend.config import settings
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage
    try:
        llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0.3,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
            request_timeout=15,
        )
        text = content[:3000]
        resp = llm.invoke([
            SystemMessage(content="你是一个投资研究笔记助手。用一段话（100字以内）总结以下分析内容的核心发现和关键数据。直接输出总结，不要多余内容。"),
            HumanMessage(content=text),
        ])
        abstract = resp.content.strip().strip('"').strip("'").strip()
        return abstract[:200] if abstract else ""
    except Exception:
        return ""


# ────────── Conditional Edges ──────────

def should_clarify(state: FinanceBotState) -> str:
    """判断是否需要反问澄清."""
    if state.get("intent") == "ambiguous" and state.get("clarification_question"):
        return "clarify"
    return "continue"

def should_hitl(state: FinanceBotState) -> str:
    """判断是否需要 HITL 暂停."""
    if state.get("anomalies"):
        return "checkpoint"
    return "synthesize"

# ────────── Build Graph ──────────

def build_agent() -> StateGraph:
    """构建并编译 Agent 工作流图."""
    workflow = StateGraph(FinanceBotState)

    # 添加节点
    workflow.add_node("classify", classify_node)
    workflow.add_node("clarify", clarify_node)
    workflow.add_node("interests", interests_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("checkpoint", checkpoint_node)
    workflow.add_node("synthesize", synthesize_node)

    # 设置入口
    workflow.set_entry_point("classify")

    # 条件边
    workflow.add_conditional_edges(
        "classify",
        should_clarify,
        {"clarify": "clarify", "continue": "interests"},
    )
    workflow.add_edge("clarify", END)  # 反问直接返回，由 UI 收集用户答复后重新调用 agent

    workflow.add_edge("interests", "execute")

    workflow.add_conditional_edges(
        "execute",
        should_hitl,
        {"checkpoint": "checkpoint", "synthesize": "synthesize"},
    )
    workflow.add_edge("checkpoint", END)  # HITL 后等待用户输入
    workflow.add_edge("synthesize", END)

    # 编译（不使用 checkpointer，上下文由 run_agent 的 history 参数管理）
    app = workflow.compile()
    return app

# 全局单例
agent_app = build_agent()

def run_agent(
    user_input: str,
    thread_id: str = "default",
    history: Optional[list[dict]] = None,
) -> dict[str, Any]:
    """运行 Agent 的便捷入口，支持多轮对话上下文.

    Args:
        user_input: 用户当前输入。
        thread_id: 对话线程 ID（保留用于兼容）。
        history: 历史消息列表，每项 {"role": "user"|"assistant", "content": str}。

    Returns:
        包含 final_answer / streaming_steps / anomalies 等字段的最终状态。
    """
    messages = list(history or [])
    messages.append({"role": "user", "content": user_input})
    initial_state = FinanceBotState(messages=messages)

    final_state = {}
    # stream_mode="values" 每次 yield 全量 State，而非 {node_name: update}
    for step in agent_app.stream(initial_state, stream_mode="values"):
        final_state = step

    return dict(final_state)
