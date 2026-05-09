"""导入接口 — PDF 上传解析 + 文档列表."""

import re

from fastapi import APIRouter, UploadFile, File

from pathlib import Path

from backend.ingestion.pipeline import ingest_document
from backend.logger import logger
from backend.rag.vector_store import vector_store
from backend.stock_map import COMMON_STOCKS

router = APIRouter()


@router.get("/documents")
def list_documents():
    """列出所有已导入的文档（缓存 60 秒）. """
    from backend.cache import cache_get_json, cache_set_json
    cached = cache_get_json("documents_list")
    if cached:
        return cached
    vector_store.connect()
    docs = vector_store.list_documents()
    result = {"documents": docs}
    cache_set_json("documents_list", result, ttl=60)
    return result


@router.delete("/documents")
def delete_document(doc_name: str):
    """按 doc_name 删除文档（从 Milvus 删除所有相关 chunks）. """
    from backend.cache import cache_invalidate
    import urllib.parse
    decoded = urllib.parse.unquote(doc_name)
    vector_store.connect()
    vector_store.delete_by_filter(f'doc_name == "{decoded}"')
    cache_invalidate("documents_list")
    logger.info("文档已删除: %s", decoded)
    return {"status": "ok"}


@router.post("/pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """上传并解析 PDF 文档。"""
    tmp = Path(__file__).resolve().parent.parent.parent / "data" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)

    fp = tmp / file.filename
    content = await file.read()
    fp.write_bytes(content)

    try:
        known_codes_set = set(COMMON_STOCKS.values())

        # 从文件名提取候选股票代码（5 位港股 / 6 位 A 股）
        code = re.search(r"(?:^|[_\s\-])(\d{5,6})(?:[_\s\-]|\.|$)", file.filename)
        filename_code = code.group(1) if code else ""

        # 验证：边界匹配提取的代码也需在已知集合中
        if filename_code and filename_code not in known_codes_set:
            filename_code = ""

        # 如果没有边界匹配或验证失败，退而求其次：只要不是长数字中的片段
        if not filename_code:
            code = re.search(r"(\d{5,6})", file.filename)
            if code:
                candidate = code.group(1)
                if candidate in known_codes_set:
                    filename_code = candidate

        r = ingest_document(
            filepath=str(fp),
            company_code=filename_code,
            doc_type="年报" if "年报" in file.filename else "研报",
            doc_name=file.filename.replace(".pdf", ""),
        )

        return {
            "success": r.success,
            "doc_name": r.doc_name,
            "total_pages": r.total_pages,
            "total_chunks": r.total_chunks,
            "total_tables": r.total_tables,
            "company": r.company,
            "company_code": r.company_code,
            "errors": r.errors,
            "elapsed_seconds": r.elapsed_seconds,
        }
    finally:
        if fp.exists():
            fp.unlink()
