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

import logging
from typing import Any, Optional

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from src.agent.router import (
    build_tool_plans,
    classify_intent,
    extract_entities,
)
from src.agent.state import Anomaly, FinanceBotState, ToolPlan
from src.agent.synthesizer import Synthesizer, synthesizer
from src.memory.store import memory_store

logger = logging.getLogger(__name__)


# ────────── Nodes ──────────

def classify_node(state: FinanceBotState) -> dict[str, Any]:
    """意图分类节点."""
    user_input = state["messages"][-1].content if state.get("messages") else ""

    intent_result = classify_intent(user_input)
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
        finally:
            memory_store.close()

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
            result = _run_tool(plan)
            result["tool"] = plan.tool_name
            if result.get("status") == "ok" and result.get("data"):
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
    """合成最终答案节点."""
    results = state.get("tool_results", [])
    citations = list(state.get("citations", []))
    anomalies = state.get("anomalies", [])
    data_status = state.get("data_status", [])
    company_name = state.get("company_name", "")
    company_code = state.get("company_code", "")

    # 记录分析历史
    if company_code:
        try:
            memory_store.connect()
            memory_store.add_or_update_company(company_code, company_name or company_code)
            memory_store.add_analysis(
                company_code=company_code,
                question=state["messages"][-1].content if state.get("messages") else "",
                summary="",
                metrics=state.get("metrics", []),
            )
        except Exception:
            pass
        finally:
            memory_store.close()

    answer = synthesizer.synthesize(
        user_query=state["messages"][-1].content if state.get("messages") else "",
        tool_results=results,
        citations=citations,
        anomalies=anomalies,
        data_status=data_status,
    )

    return {
        "final_answer": answer,
        "citations": citations,
    }


# ────────── 工具执行器 ──────────

def _run_tool(plan: ToolPlan) -> dict[str, Any]:
    """执行单个工具调用."""
    tool_name = plan.tool_name
    args = plan.args

    if tool_name == "query_financials":
        from src.tools.financial_data import get_financials
        code = args.get("company_code", "")
        data = get_financials(code)
        if data:
            # 按 period_rank 过滤
            rank_range = args.get("period_rank_range", None)
            if rank_range:
                data = [d for d in data if rank_range[0] <= (d.get("period_rank") or 0) <= rank_range[1]]
            return {"status": "ok", "data": data}
        return {"status": "empty", "data": []}

    elif tool_name == "get_stock_price":
        from src.tools.financial_data import get_stock_price_history
        code = args.get("company_code", "")
        data = get_stock_price_history(code)
        if data:
            return {"status": "ok", "data": data}
        return {"status": "empty", "data": [],
                "message": "股价接口因网络限制不可用（公司代理拦截）"}

    elif tool_name == "search_news":
        from src.tools.news_search import search_news as _search_news
        company = args.get("company_name", args.get("company", ""))
        news = _search_news(query=company, max_results=5)
        if news:
            return {"status": "ok", "data": news}
        return {"status": "empty", "data": [],
                "message": f"未搜索到 {company} 相关新闻"}

    elif tool_name == "industry_comparison":
        from src.tools.valuation import industry_comparison as _industry_comp
        code = args.get("company_code", "")
        comp_data = _industry_comp(company_code=code)
        if comp_data:
            return {"status": "ok", "data": comp_data}
        return {"status": "empty", "data": [],
                "message": "行业对比数据不可用"}

    elif tool_name == "read_financial_report":
        from src.rag.retriever import hybrid_retrieve
        code = args.get("company_code", "")
        period = args.get("period_rank_gte")
        company_name = args.get("company_name", "")
        # 查询 RAG
        data = hybrid_retrieve(
            query=f"{company_name}利润表营收",
            company_code=code,
            period_rank_gte=period,
            top_k=3,
        )
        if data:
            return {"status": "ok", "data": data}
        return {"status": "empty", "data": []}

    return {"status": "error", "data": None, "error": f"未知工具: {tool_name}"}


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
    workflow.add_edge("clarify", "classify")  # 用户回答后重新分类

    workflow.add_edge("interests", "execute")

    workflow.add_conditional_edges(
        "execute",
        should_hitl,
        {"checkpoint": "checkpoint", "synthesize": "synthesize"},
    )
    workflow.add_edge("checkpoint", END)  # HITL 后等待用户输入
    workflow.add_edge("synthesize", END)

    # 编译
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    return app


# 全局单例
agent_app = build_agent()


def run_agent(user_input: str, thread_id: str = "default") -> dict[str, Any]:
    """运行 Agent 的便捷入口.

    Returns:
        包含 final_answer / streaming_steps / anomalies 等字段的最终状态。
    """
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = FinanceBotState(messages=[{"role": "user", "content": user_input}])

    # stream 执行所有节点后，用 get_state 获取完整最终状态
    for _ in agent_app.stream(initial_state, config):
        pass
    final_state = agent_app.get_state(config)

    return dict(final_state.values)
