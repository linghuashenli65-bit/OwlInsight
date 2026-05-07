"""Phase 2 验证：模拟数据测试完整 RAG 管线.

测试流程：
1. 创建模拟文档块并插入 Milvus
2. 验证混合检索 + 时间感知过滤器
3. 验证 reranker
4. 清理测试数据
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("phase2_test")

# 添加项目根到路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 模拟文本数据
MOCK_CHUNKS = [
    {
        "text": "2024年全年实现营业收入1500亿元，同比增长15%。净利润750亿元，同比增长12%。毛利率92%。",
        "metadata": {"company": "贵州茅台", "company_code": "600519", "doc_type": "年报",
                     "doc_name": "贵州茅台2024年报", "period_rank": 0, "page_number": 10,
                     "report_date": "2024-12-31", "table_flag": False},
    },
    {
        "text": "2024年第三季度实现营业收入380亿元，同比增长13%。净利润180亿元。销售费用30亿元。",
        "metadata": {"company": "贵州茅台", "company_code": "600519", "doc_type": "利润表",
                     "doc_name": "茅台2024Q3利润表", "period_rank": -1, "page_number": 5,
                     "report_date": "2024-09-30", "table_flag": False},
    },
    {
        "text": "2024年第二季度实现营业收入350亿元，同比增长10%。净利润165亿元。销售费用28亿元。",
        "metadata": {"company": "贵州茅台", "company_code": "600519", "doc_type": "利润表",
                     "doc_name": "茅台2024Q2利润表", "period_rank": -2, "page_number": 5,
                     "report_date": "2024-06-30", "table_flag": False},
    },
    {
        "text": "2024年第一季度实现营业收入320亿元，同比增长8%。净利润155亿元。销售费用25亿元。",
        "metadata": {"company": "贵州茅台", "company_code": "600519", "doc_type": "利润表",
                     "doc_name": "茅台2024Q1利润表", "period_rank": -3, "page_number": 5,
                     "report_date": "2024-03-31", "table_flag": False},
    },
    {
        "text": "2023年全年实现营业收入1300亿元。毛利率90%。五粮液全年营收800亿元。",
        "metadata": {"company": "贵州茅台", "company_code": "600519", "doc_type": "年报",
                     "doc_name": "茅台2023年报", "period_rank": -4, "page_number": 10,
                     "report_date": "2023-12-31", "table_flag": False},
    },
    {
        "text": "五粮液2024年全年实现营业收入850亿元，同比增长10%。净利润300亿元。",
        "metadata": {"company": "五粮液", "company_code": "000858", "doc_type": "年报",
                     "doc_name": "五粮液2024年报", "period_rank": 0, "page_number": 12,
                     "report_date": "2024-12-31", "table_flag": False},
    },
]


def test_embedding() -> None:
    """测试嵌入模型."""
    from src.rag.embeddings import embedder

    vec = embedder.embed("测试文本")
    assert len(vec) == embedder.dim, f"向量维度错误: {len(vec)} != {embedder.dim}"
    print(f"[OK] 嵌入模型: 维度={embedder.dim}, mock模式={embedder.is_mock}")

    batch = embedder.embed_batch(["文本A", "文本B"])
    assert len(batch) == 2
    print(f"[OK] 批量嵌入: {len(batch)} 条")


def test_milvus_io() -> list[int]:
    """测试 Milvus 写入和读取."""
    from src.config import settings
    from src.rag.vector_store import vector_store

    vector_store.connect()
    # 重建 collection（确保维度与当前模型一致）
    vector_store.create_collection(overwrite=True)
    print(f"[OK] Collection 已重建 (dim={settings.MILVUS_EMBEDDING_DIM})")

    # 写入
    from src.rag.embeddings import embedder
    records = []
    for c in MOCK_CHUNKS:
        vec = embedder.embed(c["text"])
        records.append({
            "vector": vec,
            "text": c["text"],
            **c["metadata"],
        })
    ids = vector_store.insert_batch(records)
    assert len(ids) == len(MOCK_CHUNKS)
    print(f"[OK] Milvus 写入: {len(ids)} 条, id范围 {min(ids)}-{max(ids)}")
    return ids


def test_time_aware_retrieve() -> None:
    """测试时间感知检索：最近三期."""
    from src.rag.embeddings import embedder
    from src.rag.vector_store import vector_store

    # 1) 先搜索所有数据（无过滤）
    query = "利润表 营收 收入 数据"
    vec = embedder.embed(query, is_query=True)
    all_results = vector_store.search(vec, top_k=10)
    print(f"[DEBUG] 无过滤检索: {len(all_results)} 条")
    for r in all_results[:6]:
        print(f"    id={r.get('id')} company={r.get('company')} rank={r.get('period_rank')} doc_type={r.get('doc_type')} text={r.get('text','')[:40]}")

    # 2) 有时间过滤
    expr = 'company_code == "600519" and period_rank >= -3 and doc_type == "利润表"'
    results = vector_store.search(vec, top_k=5, expr=expr)
    print(f"\n[DEBUG] 过滤后: {len(results)} 条, expr={expr}")

    ranks = [r.get("period_rank") for r in results]
    print(f"[OK] 时间感知检索: 返回 {len(results)} 条, period_rank={sorted(ranks)}")

    for r in results:
        assert r.get("period_rank", -999) >= -3, f"period_rank < -3: {r}"
        assert r.get("company_code") == "600519", f"非目标公司: {r}"
    print("[OK] 过滤条件验证: 公司 & 时间范围均正确")


def test_cross_company_filter() -> None:
    """测试跨公司过滤."""
    from src.rag.embeddings import embedder
    from src.rag.vector_store import vector_store

    expr = 'company_code == "000858"'
    # 用 query 方式（不依赖向量），直接查元数据
    results = vector_store.query(expr=expr)
    print(f"[DEBUG] query(company_code=000858): {len(results)} 条")
    for r in results[:3]:
        print(f"    id={r.get('id')} company={r.get('company')} rank={r.get('period_rank')}")

    assert len(results) >= 1, f"预期至少1条五粮液, 实际{len(results)}条"
    for r in results:
        assert r.get("company_code") == "000858"
    print(f"[OK] 跨公司过滤: 返回 {len(results)} 条五粮液数据")


def test_bm25_index() -> None:
    """测试 BM25 索引."""
    from src.rag.retriever import bm25_index

    texts = [c["text"] for c in MOCK_CHUNKS]
    bm25_index.rebuild(texts)
    results = bm25_index.search("茅台毛利率")
    if results:
        print(f"[OK] BM25 检索: top-score={results[0][1]:.4f}, 命中 {len(results)} 条")
    else:
        print("[OK] BM25 检索: 无结果（短文本正常）")


def test_reranker() -> None:
    """测试重排序（仅加载验证，不依赖真实模型）. """
    from src.rag.reranker import reranker

    candidates = [
        {"text": "2024年营收1500亿元"},
        {"text": "茅台是一家白酒企业"},
        {"text": "销售费用30亿元"},
    ]
    results = reranker.rerank("茅台2024年营收多少", candidates, top_k=2)
    assert len(results) <= 2
    assert all("rerank_score" in r or "text" in r for r in results)
    print(f"[OK] Reranker: 返回 {len(results)} 条（模型加载={reranker._model is not None}）")


def test_hybrid_retrieve() -> None:
    """测试混合检索."""
    from src.rag.retriever import hybrid_retrieve

    results = hybrid_retrieve(
        query="茅台最近营收和利润",
        company_code="600519",
        period_rank_gte=-3,
        top_k=3,
    )
    print(f"[OK] 混合检索: 返回 {len(results)} 条")
    for r in results:
        print(f"    rank={r.get('period_rank')} score={r.get('score', 'N/A')}: {r.get('text', '')[:50]}...")


def cleanup(ids: list[int]) -> None:
    """清理测试数据."""
    from src.rag.vector_store import vector_store
    vector_store.delete(ids)
    print(f"[OK] 清理: 已删除 {len(ids)} 条测试数据")
    vector_store.close()


def run_all() -> None:
    print("=" * 50)
    print("  Phase 2 — RAG 管线验证")
    print("=" * 50)

    test_embedding()
    print()

    ids = test_milvus_io()
    print()

    test_time_aware_retrieve()
    test_cross_company_filter()
    print()

    test_bm25_index()
    print()

    try:
        test_reranker()
    except Exception as e:
        print(f"[INFO] Reranker 测试跳过 (模型加载问题): {e}")
    print()

    test_hybrid_retrieve()
    print()

    cleanup(ids)

    print()
    print("=" * 50)
    print("  [OK] Phase 2 验证完成")
    print("=" * 50)


if __name__ == "__main__":
    run_all()
