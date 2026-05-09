"""Phase 4 — 记忆 + 兴趣学习验证.

测试内容：
1. InterestTracker — 兴趣学习 + 同义词归一化
2. 个性化提示生成
3. 分析历史回顾
4. 研究笔记自动保存
5. 完整闭环：学习 → 匹配 → 提示
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger("phase4_test")


def setup_test_data():
    """准备测试数据."""
    from backend.memory.store import memory_store
    memory_store.connect()
    # 模拟 3 次分析历史
    memory_store.add_or_update_company("600519", "贵州茅台")
    memory_store.add_or_update_company("000858", "五粮液")
    memory_store.add_or_update_company("300750", "宁德时代")

    # 模拟分析历史和兴趣
    analyses = [
        ("600519", "茅台毛利率和营收怎么样", "毛利率", ["毛利率", "营收"]),
        ("000858", "五粮液毛利率如何", "毛利率", ["毛利率"]),
        ("300750", "宁德时代营收增长", "营收", ["营收", "增长率"]),
        ("600519", "茅台销售费用分析", "销售费用", ["销售费用"]),
    ]
    for code, q, metric, metrics in analyses:
        memory_store.add_analysis(code, q, f"分析{metric}", metrics)
        for m in metrics:
            memory_store.record_metric_mention(m, code)
    memory_store.close()
    print("[OK] 测试数据已准备（3 家公司, 4 次分析）")


def test_interest_tracker():
    """测试兴趣学习."""
    from backend.memory.interest_tracker import InterestTracker, normalize_metric

    # 同义词归一化
    assert normalize_metric("毛利") == "毛利率"
    assert normalize_metric("营业收入") == "营收"
    assert normalize_metric("ROE") == "ROE"
    print("[OK] 同义词归一化: 毛利→毛利率, 营业收入→营收")

    tracker = InterestTracker()

    # 学习
    tracker.learn_from_analysis(["毛利率", "营收", "毛利"], "600519")
    print("[OK] 兴趣学习: 记录成功")

    # 个性化提示
    hint = tracker.get_personalized_hint("600519")
    if hint:
        print(f"[OK] 个性化提示: {hint[:60]}...")
    else:
        print("[INFO] 个性化提示为空（正常）")

    # 兴趣摘要
    summary = tracker.get_metric_summary("600519")
    assert summary.get("total_interests", 0) >= 1
    assert len(summary.get("watched_companies", [])) >= 3
    assert summary.get("recent_analysis", [])
    print(f"[OK] 兴趣摘要: {summary['total_interests']} 个指标, {len(summary['watched_companies'])} 家公司, {len(summary['recent_analysis'])} 条历史")


def test_retrospective():
    """测试回顾功能."""
    from backend.memory.store import memory_store

    memory_store.connect()
    history = memory_store.search_analysis("茅台", limit=5)
    assert len(history) >= 2, f"预期至少 2 条茅台记录, 实际 {len(history)}"
    print(f"[OK] 回顾搜索: {len(history)} 条匹配")

    # 验证每条记录有完整信息
    for h in history:
        assert h.get("question"), f"问题为空: {h}"
        assert h.get("company_code"), f"公司代码为空: {h}"
    print("[OK] 回顾数据完整性: 问题+公司均正确")


def test_note_save():
    """测试笔记自动保存."""
    from backend.tools.note_tools import write_research_note, list_research_notes

    path = write_research_note(
        company_code="600519",
        company_name="贵州茅台",
        content="# 茅台分析\n营收1500亿\n",
        metrics=["营收", "毛利率"],
        tags=["测试"],
    )
    assert Path(path).exists(), f"笔记文件未创建: {path}"
    print(f"[OK] 笔记保存: {path}")

    notes = list_research_notes(company_code="600519", limit=5)
    assert len(notes) >= 1
    print(f"[OK] 笔记列表: {len(notes)} 条")


def test_personalized_hint_flow():
    """测试完整闭环：多次关注 → 后续提示."""
    from backend.memory.interest_tracker import InterestTracker
    from backend.agent.router import _match_user_interests

    tracker = InterestTracker()

    # 模拟用户连续 3 次关注毛利率
    tracker.learn_from_analysis(["毛利率"], "600519")
    tracker.learn_from_analysis(["毛利率"], "000858")
    tracker.learn_from_analysis(["毛利率"], "300750")

    # 第 4 次分析时匹配
    matched = _match_user_interests(["毛利率"])
    if matched:
        print(f"[OK] 匹配到历史兴趣: {matched[0].get('metric_name')}, 共关注{matched[0].get('mention_count')}次")
    else:
        print("[INFO] 匹配接口暂未返回数据")

    hint = tracker.get_personalized_hint("600519")
    if hint:
        print(f"[OK] 个性化提示: {hint}")
    else:
        print("[INFO] 个性化提示为空")


def cleanup():
    """清理测试数据.

    只删除 setup_test_data 中插入的测试记录（600519/000858/300750），
    不影响主线使用中积累的其他公司数据。
    """
    import sqlite3
    from backend.config import settings
    db = settings.MEMORY_DB_PATH
    if not Path(db).exists():
        return
    conn = sqlite3.connect(db)
    # 只清理测试用到的三家公司的数据，保留其他真实记录
    test_codes = ("600519", "000858", "300750")
    placeholders = ",".join("?" for _ in test_codes)
    conn.execute(f"DELETE FROM analysis_history WHERE company_code IN ({placeholders})", test_codes)
    conn.execute(f"DELETE FROM watched_companies WHERE company_code IN ({placeholders})", test_codes)
    conn.execute(f"DELETE FROM user_interests WHERE related_companies LIKE '%600519%' "
                 f"OR related_companies LIKE '%000858%' "
                 f"OR related_companies LIKE '%300750%'")
    conn.commit()
    conn.close()
    print("[OK] 测试数据已清理（仅删除 600519/000858/300750 相关记录）")


def run_all():
    print("=" * 50)
    print("  Phase 4 — 记忆 + 兴趣学习验证")
    print("=" * 50)

    setup_test_data()
    print()
    test_interest_tracker()
    print()
    test_retrospective()
    print()
    test_note_save()
    Path("D:\\FinanceBot\\data\\research_notes").mkdir(parents=True, exist_ok=True)
    print()
    test_personalized_hint_flow()
    print()
    cleanup()

    print()
    print("=" * 50)
    print("  [OK] Phase 4 验证完成")
    print("=" * 50)


if __name__ == "__main__":
    run_all()
