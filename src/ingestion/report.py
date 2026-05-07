"""导入摘要生成 — 将 IngestionResult 转为人类可读的格式."""

from typing import Any

from src.ingestion.pipeline import IngestionResult

# 中文报告期 rank → 标签
_RANK_LABELS = {
    0: "最新一期",
    -1: "上一期",
    -2: "往前第 2 期",
    -3: "往前第 3 期",
}


def generate_import_summary(result: IngestionResult) -> str:
    """生成导入摘要文本."""
    lines: list[str] = []

    if result.errors:
        lines.append("---")
        lines.append("⚠️ 导入过程出现以下问题：")
        for err in result.errors:
            lines.append(f"  ❌ {err}")
        lines.append("---")

    if not result.success:
        lines.append("❌ 文档导入失败")
        return "\n".join(lines)

    # 成功摘要
    lines.append(f"✅ 成功导入 {result.doc_name}")
    lines.append(f"   总页数: {result.total_pages}")
    lines.append(f"   文档块: {result.total_chunks} 个")

    if result.total_tables > 0:
        lines.append(f"   📊 表格: {result.total_tables} 个（已单独索引）")

    if result.company:
        lines.append(f"   🏢 识别公司: {result.company}")
    if result.company_code:
        lines.append(f"   🔖 股票代码: {result.company_code}")

    if result.period_rank_range != (0, 0):
        min_r, max_r = result.period_rank_range
        labels = [_RANK_LABELS.get(r, f"rank={r}") for r in (min_r, max_r)]
        lines.append(f"   📅 报告期范围: {labels[0]} ~ {labels[1]}")

    lines.append(f"   ⏱ 处理耗时: {result.elapsed_seconds:.1f}s")

    return "\n".join(lines)


def generate_import_summary_json(result: IngestionResult) -> dict[str, Any]:
    """返回结构化的导入摘要（用于前端展示）. """
    return {
        "success": result.success,
        "doc_name": result.doc_name,
        "doc_type": result.doc_type,
        "total_pages": result.total_pages,
        "total_chunks": result.total_chunks,
        "total_tables": result.total_tables,
        "company": result.company,
        "company_code": result.company_code,
        "period_rank_min": result.period_rank_range[0],
        "period_rank_max": result.period_rank_range[1],
        "errors": result.errors,
        "elapsed_seconds": round(result.elapsed_seconds, 1),
        "inserted_count": len(result.inserted_ids),
    }
