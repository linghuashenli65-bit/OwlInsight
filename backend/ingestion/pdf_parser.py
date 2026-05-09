"""PDF 解析器 — 文本提取 + 表格检测.

使用 PyMuPDF (fitz) 提取。
表格检测策略：识别连续多行中数值对齐的区域。
"""

from backend.logger import logger
import re
from typing import Any

import fitz  # PyMuPDF

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

    page_count = len(doc)
    doc.close()
    logger.info("PDF 解析完成: %s, %d 页/%d 非空页, %d 个表格",
                filepath, page_count, len(pages), sum(1 for p in pages if p["is_table"]))
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

def _extract_company_name(text: str) -> str:
    """从文本中提取公司名，支持多种格式.

    策略：
    1. 尝试标准公司全称: "XX股份有限公司/有限公司/集团公司"
    2. 尝试较短模式: "XX公司"
    3. 扫描已知公司名（COMMON_STOCKS 中的 key 是否出现在文本中）

    Returns:
        公司名，未识别则返回空字符串。
    """
    from backend.stock_map import COMMON_STOCKS

    head = text[:2000]

    # 策略1：标准公司全称 "腾讯控股有限公司" / "贵州茅台酒股份有限公司"
    m = re.search(r"([\u4e00-\u9fa5]{2,15}(?:股份|集团|有限|控股)[\u4e00-\u9fa5]{0,8})公司", head)
    if m:
        return m.group(0)

    # 策略2：较短模式 "XX公司"（2~6 个中文字符 + "公司"）
    m = re.search(r"([\u4e00-\u9fa5]{2,6})公司", head)
    if m:
        return m.group(0)

    # 策略3：扫描已知公司名 — 按长度降序优先匹配更长名称
    for name in sorted(COMMON_STOCKS, key=len, reverse=True):
        if name in head:
            return name

    return ""


def _detect_doc_type(text: str, filename_hint: str = "") -> str:
    """从文本+文件名推断文档类型.

    返回 "年报" | "研报" | "教材" | "其他".
    """
    head = text[:1000]

    # 半年报/季报（必须放在年报前，因"半年度报告"含"年度报告"子串）
    if re.search(r"(半年度报告|中期报告|季度报告)", head):
        return "季报"
    # 年报特征
    if re.search(r"(年度报告|年报|年报告)", head) or "年报" in filename_hint:
        return "年报"
    # 研报特征
    if re.search(r"(研究报告|研报|分析报告|行业研究)", head) or "研报" in filename_hint:
        return "研报"
    # 教材/书籍特征
    if re.search(r"(第.\s*章|目\s*录|前言|参考文献|出版社)", head[:500]):
        return "教材"
    # 招股书
    if re.search(r"(招股说明书|招股书|IPO)", head):
        return "招股书"

    return "其他"


def _detect_report_date(text: str) -> str:
    """提取报告期/日期."""
    head = text[:500]

    # 报告期: "报告期：2024年1月1日-2024年12月31日"
    # 先找第一个出现的日期
    m = re.search(r"(\d{4})[年\-\.](\d{1,2})[月\-\.](\d{1,2})[日]?", head)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    return ""


def extract_metadata_from_text(text: str) -> dict[str, Any]:
    """从 PDF 文本中提取公司名、文档类型、报告期等元数据.

    适配多种文档类型：年报、研报、教材、经济学文献等。
    非企业类文档相关字段返回空，不影响检索。
    """
    meta: dict[str, Any] = {
        "company": "",
        "doc_type": "",
        "report_date": "",
        "report_year": 0,
    }

    # 公司名：可能有也可能没有（经济学教材就没有）
    company = _extract_company_name(text)
    if company:
        meta["company"] = company

    # 文档类型：自适应检测
    meta["doc_type"] = _detect_doc_type(text)

    # 报告年: "2024年年度报告" / "2023年半年度报告"
    m = re.search(r"((?:20)\d{2})\s*年\s*(?:年度|半年度|一季度|二季度|三季度|四季度)", text[:500])
    if m:
        meta["report_year"] = int(m.group(1))

    # 报告期
    meta["report_date"] = _detect_report_date(text)

    return meta


_SECTION_HEADER_RE = re.compile(
    r"^(?:第[一二三四五六七八九十]+[节章]\s+|"
    r"[一二三四五六七八九十]+[、．.]\s*|"
    r"\(\d+\)\s+|"
    r"\d+\.\d+\s+|"
    r"(?:一|二|三|四|五|六|七|八|九|十)[、，])",
    re.MULTILINE,
)


def generate_doc_summary(pages: list[dict[str, Any]]) -> str:
    """从解析后的页面列表生成文档简要描述.

    策略：
    1. 取第一页中第一个有意义的段落（约 120 字）
    2. 扫描全文中的章节标题（最多 6 个）
    3. 组合为简洁摘要

    Returns:
        摘要字符串，不超过 500 字。
    """
    # 收集所有文本
    all_text = "\n".join(p["text"] for p in pages)

    # 1. 从第一页提取开篇段落
    first_page_text = pages[0]["text"] if pages else ""
    opening = ""
    # 找第一个长度 >20 的段落
    for para in first_page_text.split("\n"):
        para = para.strip()
        if len(para) > 20:
            # 去掉开头可能的页码/页眉
            para = re.sub(r"^[\d\s\-—·•*]+", "", para).strip()
            if len(para) > 20:
                opening = para[:120]
                break

    # 2. 提取章节标题
    headers = _SECTION_HEADER_RE.findall(all_text)
    # 去重 + 清理 + 取前 6 个
    seen = set()
    unique_headers = []
    for h in headers:
        h = h.strip().rstrip("，, ")
        if h and h not in seen:
            seen.add(h)
            unique_headers.append(h)
        if len(unique_headers) >= 6:
            break

    # 3. 组合摘要
    parts = []
    if opening:
        parts.append(opening)
    if unique_headers:
        parts.append("章节：" + " | ".join(unique_headers))

    summary = "；".join(parts)
    # 限制长度
    if len(summary) > 500:
        summary = summary[:497] + "..."
    return summary
