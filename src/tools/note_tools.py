"""研究笔记工具 — 保存/读取分析报告."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.config import settings

logger = logging.getLogger(__name__)


def write_research_note(
    company_code: str,
    company_name: str,
    content: str,
    metrics: Optional[list[str]] = None,
    tags: Optional[list[str]] = None,
) -> str:
    """保存分析结果到本地研究笔记.

    Args:
        company_code: 股票代码。
        company_name: 公司名。
        content: 分析结果 Markdown。
        metrics: 涉及的指标列表。
        tags: 标签。

    Returns:
        笔记文件路径。
    """
    notes_dir = settings.DATA_DIR / "research_notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{company_code}_{company_name}_{timestamp}.md"
    filepath = notes_dir / filename

    header = f"""---
title: {company_name} ({company_code}) 分析笔记
created: {datetime.now().isoformat()}
metrics: {json.dumps(metrics or [], ensure_ascii=False)}
tags: {json.dumps(tags or [], ensure_ascii=False)}
---

"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(header + content)

    logger.info("研究笔记已保存: %s", filepath)
    return str(filepath)


def list_research_notes(
    company_code: Optional[str] = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """列出研究笔记.

    Args:
        company_code: 可选，按公司筛选。
        limit: 最多返回条数。

    Returns:
        [{"filename", "company", "created", "path"}, ...]
    """
    notes_dir = settings.DATA_DIR / "research_notes"
    if not notes_dir.exists():
        return []

    notes = []
    for f in sorted(notes_dir.glob("*.md"), reverse=True):
        if company_code and company_code not in f.stem:
            continue
        parts = f.stem.split("_", 2)
        notes.append({
            "filename": f.name,
            "company": parts[1] if len(parts) > 1 else "",
            "code": parts[0] if parts else "",
            "created": parts[2] if len(parts) > 2 else "",
            "path": str(f),
        })
        if len(notes) >= limit:
            break

    return notes
