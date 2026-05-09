"""文档分块器 — 智能分块 + period_rank 预计算.

分块策略：
1. 按财务报告章节标题分割（一、/ 第一节 / 1.1）
2. 表格单独成块（table_flag=True）
3. 非表格长文本滑动窗口（max_tokens=512, overlap=64）
4. 每个 chunk 携带完整元数据（company, period_rank, doc_type 等）
"""

from backend.logger import logger
import re
from datetime import date, datetime
from typing import Any, Optional

from backend.models.schemas import Chunk, DocMetadata

# ────────── 中文章节标题正则 ──────────
_SECTION_PATTERNS = [
    r"^第[一二三四五六七八九十]+节\s",           # 第一节
    r"^[一二三四五六七八九十]+[、．.]\s*",        # 一、
    r"^\(\d+\)\s",                               # (1)
    r"^\d+\.\d+\s",                              # 1.1
    r"^(?:一|二|三|四|五|六|七|八|九|十)、",     # 一、二、
]

# 合并为一个正则
_SECTION_RE = re.compile("|".join(f"({p})" for p in _SECTION_PATTERNS), re.MULTILINE)

# 滑动窗口参数
_MAX_TOKENS = 512
_OVERLAP_TOKENS = 64

def chunk_document(
    pages: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> list[Chunk]:
    """将解析后的 PDF 页面列表分块.

    Args:
        pages: pdf_parser.parse_pdf() 的输出。
        metadata: 文档级别的元数据（company, company_code, doc_type, doc_name 等）。

    Returns:
        分块后的 Chunk 列表，每个带有向量化所需的元数据。
    """
    # 预计算 period_rank
    period_rank = _compute_period_rank(metadata)

    # 合并所有页面文本为整体
    full_text = "\n".join(f"【第{p['page']}页】\n{p['text']}" for p in pages)

    # 提取表格块
    table_chunks = _extract_tables(pages, metadata, period_rank)

    # 文本部分：去掉表格区域后的纯文本分块
    text_chunks = _split_by_sections(full_text, metadata, period_rank)

    # 合并
    result = table_chunks + text_chunks
    logger.info("文档分块完成: %d 个文本块 + %d 个表格块 = %d 个 chunks",
                len(text_chunks), len(table_chunks), len(result))
    return result

# ────────── period_rank 计算 ──────────

def _compute_period_rank(meta: dict[str, Any]) -> int:
    """根据文档元数据预计算 period_rank.

    逻辑：当前日期 - 报告期，每差一个季度 rank-1。
    如报告期未知则返回 0。
    """
    report_date = meta.get("report_date")
    if report_date:
        try:
            rd = datetime.strptime(str(report_date), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            rd = date.today()
    elif meta.get("report_year"):
        # 默认取该年 12月31日
        rd = date(meta["report_year"], 12, 31)
    else:
        return 0

    today = date.today()
    q = (today.year - rd.year) * 4 + max(0, (today.month - 1) // 4 - (rd.month - 1) // 4)
    return -q

# ────────── 表格提取 ──────────

def _extract_tables(
    pages: list[dict[str, Any]],
    meta: dict[str, Any],
    period_rank: int,
) -> list[Chunk]:
    """从页面中提取表格作为独立 chunk."""
    chunks = []
    for p in pages:
        for table_text in p.get("tables", []):
            if not table_text.strip():
                continue
            dm = DocMetadata(
                company=meta.get("company", ""),
                company_code=meta.get("company_code", ""),
                doc_type=meta.get("doc_type", ""),
                doc_name=meta.get("doc_name", ""),
                summary=meta.get("summary", ""),
                page_number=p["page"],
                period_rank=period_rank,
                table_flag=True,
            )
            chunks.append(Chunk(text=table_text, metadata=dm))
    return chunks

# ────────── 文本分块 ──────────

def _split_by_sections(
    text: str,
    meta: dict[str, Any],
    period_rank: int,
) -> list[Chunk]:
    """按章节标题分块，长章节滑动窗口."""
    # 先按章节拆
    sections = _split_sections(text)
    chunks = []

    for section_text, section_title in sections:
        # 跳过极短片段（纯标题或空白）
        clean = section_text.strip()
        if len(clean) < 10:
            continue

        dm = DocMetadata(
            company=meta.get("company", ""),
            company_code=meta.get("company_code", ""),
            doc_type=meta.get("doc_type", ""),
            doc_name=meta.get("doc_name", ""),
            summary=meta.get("summary", ""),
            period_rank=period_rank,
        )

        # 按 token 数滑动窗口（粗略按 1 字 ≈ 0.7 token 估算）
        max_chars = int(_MAX_TOKENS / 0.7)
        overlap_chars = int(_OVERLAP_TOKENS / 0.7)

        if len(clean) <= max_chars:
            chunks.append(Chunk(text=clean, metadata=dm.model_copy()))
        else:
            start = 0
            while start < len(clean):
                end = min(start + max_chars, len(clean))
                chunk_text = clean[start:end]
                if len(chunk_text.strip()) >= 10:
                    chunks.append(Chunk(text=chunk_text, metadata=dm.model_copy()))
                if end >= len(clean):
                    break
                start = end - overlap_chars

    return chunks

def _split_sections(text: str) -> list[tuple[str, str]]:
    """按章节标题分割全文，返回 [(section_text, section_title), ...]."""
    lines = text.split("\n")
    sections: list[tuple[str, str]] = []
    current_lines: list[str] = []
    current_title = ""

    for line in lines:
        stripped = line.strip()
        match = _SECTION_RE.match(stripped)
        if match:
            # 保存上一章节
            if current_lines:
                sections.append(("\n".join(current_lines), current_title))
            current_lines = [line]
            current_title = stripped[:40]
        else:
            current_lines.append(line)

    # 最后一章节
    if current_lines:
        sections.append(("\n".join(current_lines), current_title))

    # 如果没识别出任何章节，整篇作为一个块
    if not sections:
        sections = [(text, "" )]

    return sections
