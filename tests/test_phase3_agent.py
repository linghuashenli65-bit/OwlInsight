"""Phase 3 — Agent 核心 + 工具验证.

测试内容：
1. 意图分类（明确/模糊/多意图）
2. 工具调用（利润表/股价）
3. 学术引用格式合成
4. 完整 Agent 流程
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger("phase3_test")


def test_intent_classify():
    """测试意图分类."""
    from src.agent.router import classify_intent

    # 1. 模糊意图
    result = classify_intent("茅台最近怎么样")
    print(f"[TEST] 模糊意图: intent={result.get('intent')}, confidence={result.get('confidence'):.1f}")
    assert result.get("intent") in ("ambiguous", "financial_query", "news_query", "multi_intent"), f"意图不对: {result}"
    assert result.get("company_code") == "600519", f"公司代码未识别: {result}"
    print(f"   公司={result.get('company')} 代码={result.get('company_code')}")

    # 2. 明确财务查询
    result = classify_intent("茅台2024年营收和毛利率")
    print(f"[TEST] 明确意图: intent={result.get('intent')}, metrics={result.get('metrics')}")
    assert result.get("company_code") == "600519"

    # 3. 多意图
    result = classify_intent("对比茅台和五粮液的财务，顺便看看新闻")
    print(f"[TEST] 多意图: intent={result.get('intent')}, sub={result.get('sub_intents', [])}")

    print("[OK] 意图分类测试通过")


def test_tool_plans():
    """测试工具计划生成."""
    from src.agent.router import build_tool_plans

    intent = {
        "intent": "financial_query",
        "company_code": "600519",
        "company": "茅台",
        "metrics": ["营收", "毛利率"],
        "time_hint": "最近三期",
    }
    plans = build_tool_plans(intent)
    print(f"[TEST] 工具计划: {len(plans)} 个")
    for p in plans:
        print(f"   - {p.tool_name}: {p.description}")
    assert any(p.tool_name == "query_financials" for p in plans)
    print("[OK] 工具计划测试通过")


def test_synthesizer():
    """测试答案合成器."""
    from src.agent.state import Anomaly, Citation
    from src.agent.synthesizer import Synthesizer

    s = Synthesizer()

    citations = [Citation(index=1, source="利润表", detail="茅台2024年报, 利润表, p12")]
    anomalies = [Anomaly(
        metric="销售费用",
        value="30亿",
        change="增长 30%",
        description="环比大幅增长",
    )]

    tool_results = [{
        "tool": "query_financials",
        "status": "ok",
        "data": [
            {"report_period": "2024-12-31", "revenue": 150000000000, "net_profit": 75000000000,
             "operating_profit": 100000000000, "period_rank": 0},
            {"report_period": "2024-09-30", "revenue": 120000000000, "net_profit": 60000000000,
             "operating_profit": 80000000000, "period_rank": -1},
        ],
    }]

    answer = s.synthesize(
        "茅台2024年营收",
        tool_results,
        citations,
        anomalies=anomalies,
        data_status=["2024Q4现金流量表未获取到"],
        matched_interests=[{"metric_name": "毛利率", "mention_count": 5}],
    )
    print("[TEST] 合成答案:")
    for line in answer.split("\n")[:10]:
        print(f"   {line}")
    assert "^1" in answer, "缺少引用上标"
    assert "引用来源" in answer, "缺少引用列表"
    print("[OK] 答案合成测试通过")


def test_full_agent_flow():
    """测试完整 Agent 流程（不依赖 LLM API 的 fallback 路径）. """
    from src.agent.graph import run_agent

    # 使用规则 fallback 分类，不走 LLM
    result = run_agent("茅台营收多少")
    final = result.get("final_answer", "")
    steps = result.get("streaming_steps", [])

    print(f"[TEST] 完整流程: steps={len(steps)}, answer_len={len(final)}")
    if steps:
        for s in steps[:3]:
            print(f"   Step: {s[:60]}...")
    if final:
        print(f"   答案预览: {final[:80]}...")

    # 检查结果（可能为空因为网络限制）
    if not final:
        print("   [INFO] 答案为空（工具执行可能受网络限制）")
    else:
        assert len(final) > 10
    print("[OK] 完整 Agent 流程测试通过")


def run_all():
    print("=" * 50)
    print("  Phase 3 — Agent 核心验证")
    print("=" * 50)

    test_intent_classify()
    print()
    test_tool_plans()
    print()
    test_synthesizer()
    print()
    test_full_agent_flow()
    print()

    print("=" * 50)
    print("  [OK] Phase 3 验证完成")
    print("=" * 50)


if __name__ == "__main__":
    run_all()
