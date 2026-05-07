"""PDF 解析器 — 文本提取 + 表格检测.

使用 PyMuPDF (fitz) 提取。
表格检测策略：识别连续多行中数值对齐的区域。
"""

import logging
import re
from typing import Any

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# 表格启发式阈值：一行中数字占比超过此值视为表格行
_TABLE_NUM_RATIO = 0.4
# 表格至少需要的行数
_TABLE_MIN_ROWS = 3


def parse_pdf(filepath: str) -> list[dict[str, Any]]:
    """解析 PDF 文件，返回页面级内容列表.

    Returns:
        [{"page": int, "text": str, "is_table": bool, "tables": [str, ...]}, ...]
    """
    doc = fitz.open(filepath)
    pages = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")

        # 空页跳过
        if not text.strip():
            continue

        # 表格检测
        tables = _detect_tables(page)
        is_table = len(tables) > 0

        pages.append({
            "page": page_num + 1,
            "text": text.strip(),
            "is_table": is_table,
            "tables": tables,
        })

    doc.close()
    logger.info("PDF 解析完成: %s, %d 页/%d 非空页, %d 个表格",
                filepath, len(doc), len(pages), sum(1 for p in pages if p["is_table"]))
    return pages


def _detect_tables(page: fitz.Page) -> list[str]:
    """从页面中检测表格区域并提取为文本.

    方法：按行检查，如果一行中纯数字/tab分割的数值占比高，判定为表格行。
    连续 TABLE_MIN_ROWS 行以上即作为一个表格。
    """
    text = page.get_text("text")
    lines = text.split("\n")
    table_lines = []
    current_table: list[str] = []
    tables: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if len(current_table) >= _TABLE_MIN_ROWS:
                tables.append("\n".join(current_table))
            current_table = []
            continue

        # 判断是否为表格行：含多个数字/空白分割的数值
        tokens = re.split(r"\s{2,}|\t", stripped)
        num_count = sum(1 for t in tokens if _looks_like_number(t))
        if num_count >= 2:
            current_table.append(stripped)
        else:
            if len(current_table) >= _TABLE_MIN_ROWS:
                tables.append("\n".join(current_table))
            current_table = []

    # 末尾检查
    if len(current_table) >= _TABLE_MIN_ROWS:
        tables.append("\n".join(current_table))

    return tables


def _looks_like_number(s: str) -> bool:
    """判断字符串是否像数字（含千分位逗号、负号、百分号）. """
    s = s.strip().replace(",", "").replace("%", "").replace("(", "").replace(")", "")
    if not s:
        return False
    try:
        float(s)
        return True
    except ValueError:
        return False


def extract_metadata_from_text(text: str) -> dict[str, Any]:
    """从 PDF 文本中提取公司名、报告期等元数据."""
    meta: dict[str, Any] = {}

    # 公司名: "XX公司" 模式
    m = re.search(r"([\u4e00-\u9fa5]{2,8}(?:股份|集团|有限))?公司", text[:2000])
    if m:
        meta["company"] = m.group(0)

    # 报告年: "2024年年度报告" / "2023年半年度报告"
    m = re.search(r"((?:20)\d{2})\s*年\s*(?:年度|半年度|一季度|二季度|三季度|四季度|第三季|第一季|第二季)", text[:500])
    if m:
        meta["report_year"] = int(m.group(1))

    # 报告期: "报告期：2024年1月1日-2024年12月31日"
    m = re.search(r"(\d{4})[年\-\.](\d{1,2})[月\-\.](\d{1,2})[日]?", text[:500])
    if m:
        meta["report_date"] = f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"

    return meta
