"""导入管线编排 — parse → chunk → embed → insert.

处理流程：
1. pdf_parser.parse_pdf()         → 页面级内容
2. chunker.chunk_document()       → Chunk 列表（含 period_rank）
3. embedder.embed_batch()         → 生成向量
4. vector_store.insert_batch()    → 写入 Milvus
"""

from backend.logger import logger
import time
from pathlib import Path
from typing import Any, Optional

from tqdm import tqdm

from backend.config import settings
from backend.ingestion.chunker import chunk_document
from backend.ingestion.pdf_parser import (
    extract_metadata_from_text,
    generate_doc_summary,
    parse_pdf,
)
from backend.rag.embeddings import embedder
from backend.rag.vector_store import vector_store

class IngestionResult:
    """导入结果."""
    def __init__(self) -> None:
        self.success = False
        self.total_pages = 0
        self.total_chunks = 0
        self.total_tables = 0
        self.company = ""
        self.company_code = ""
        self.period_rank_range: tuple[int, int] = (0, 0)
        self.doc_name = ""
        self.doc_type = ""
        self.errors: list[str] = []
        self.elapsed_seconds = 0.0
        self.inserted_ids: list[int] = []

def ingest_document(
    filepath: str,
    company_code: str = "",
    doc_type: str = "年报",
    doc_name: str = "",
) -> IngestionResult:
    """导入一份文档的完整流程.

    Args:
        filepath: PDF 文件路径。
        company_code: 股票代码（如 "600519"），为空则自动识别。
        doc_type: 文档类型，默认 "年报"。
        doc_name: 文档名称，为空则取文件名。

    Returns:
        导入结果对象。
    """
    result = IngestionResult()
    start_ts = time.time()
    fp = Path(filepath)
    result.doc_name = doc_name or fp.stem
    result.doc_type = doc_type

    # 确保 Milvus 已连接（首次使用自动初始化）
    if not vector_store.is_connected():
        vector_store.connect()

    # 确保 collection 存在
    if not vector_store.has_collection():
        vector_store.create_collection()
        logger.info("Collection '%s' 已自动创建", settings.MILVUS_COLLECTION)

    try:
        # ── Step 1: 解析 PDF ──
        pages = parse_pdf(str(fp))
        result.total_pages = len(pages)
        if not pages:
            result.errors.append("PDF 解析为空")
            return result

        # ── Step 2: 提取元数据 ──
        meta = _build_metadata(pages, company_code, doc_type, result.doc_name)
        result.company = meta.get("company", "") or ""
        result.company_code = meta.get("company_code", "") or ""

        # ── Step 3: 分块 ──
        chunks = chunk_document(pages, meta)
        result.total_chunks = len(chunks)
        result.total_tables = sum(1 for c in chunks if c.metadata.table_flag)

        # 记录 period_rank 范围
        ranks = [c.metadata.period_rank for c in chunks if c.metadata.period_rank is not None]
        if ranks:
            result.period_rank_range = (min(ranks), max(ranks))

        # ── Step 4: 生成向量 ──
        texts = [c.text for c in chunks]
        logger.info("正在生成 %d 个 chunk 的向量 ...", len(texts))
        vectors = embedder.embed_batch(texts)

        # ── Step 5: 写入 Milvus ──
        records = []
        for chunk, vec in zip(chunks, vectors):
            record = {
                "vector": vec,
                "text": chunk.text,
                **chunk.metadata.to_milvus_json(),
            }
            records.append(record)

        ids = vector_store.insert_batch(records)
        result.inserted_ids = ids
        result.success = True
        logger.info("已导入 %d 个 chunk 到 Milvus", len(ids))

    except Exception as e:
        logger.exception("文档导入失败: %s", filepath)
        result.errors.append(str(e))
    finally:
        result.elapsed_seconds = time.time() - start_ts

    return result

def _resolve_company_code(company_name: str, filename_candidate: str) -> str:
    """智能解析股票代码.

    优先级：
    1. 从内容提取的公司名反查代码（最可靠）
    2. 文件名候选代码（仅当看起来像有效代码时）
    3. 仍为空则返回空（文档可能无关企业）

    Args:
        company_name: 从内容提取的公司名。
        filename_candidate: 从文件名提取的候选数字。

    Returns:
        股票代码（可能为空）。
    """
    from backend.stock_map import COMMON_STOCKS, lookup_company_code

    # 1. 内容匹配优先
    if company_name:
        code = lookup_company_code(company_name)
        if code:
            return code

    # 2. 文件名候选代码验证
    if filename_candidate and len(filename_candidate) in (5, 6) and filename_candidate.isdigit():
        # 检查是否为已知代码（反向查找）
        known_codes = set(COMMON_STOCKS.values())
        if filename_candidate in known_codes:
            return filename_candidate

    return ""


def _build_metadata(
    pages: list[dict[str, Any]],
    company_code: str,
    doc_type: str,
    doc_name: str,
) -> dict[str, Any]:
    """构建文档级别的元数据字典.

    元数据完全由内容驱动，不强行填写不确定的字段。
    非企业文档（如经济学教材）的 company/company_code 为空。
    """
    # 从全文提取
    full_text = "\n".join(p["text"] for p in pages[:5])
    auto_meta = extract_metadata_from_text(full_text)

    company = auto_meta.get("company", "")

    # company_code: 内容匹配 > 文件名候选验证
    resolved_code = _resolve_company_code(company, company_code)

    # doc_type: 内容检测 > 文件名推断
    resolved_doc_type = auto_meta.get("doc_type", "") or doc_type

    # 文档摘要：从内容自动生成
    summary = generate_doc_summary(pages)

    meta = {
        "company": company,
        "company_code": resolved_code,
        "doc_type": resolved_doc_type,
        "doc_name": doc_name,
        "summary": summary,
        "report_date": auto_meta.get("report_date", ""),
        "report_year": auto_meta.get("report_year", 0),
    }
    return meta
