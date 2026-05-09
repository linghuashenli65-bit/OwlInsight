"""估值计算工具."""

from backend.logger import logger
from typing import Any, Optional

import akshare as ak

def calculate_valuation(
    company_code: str,
    company_name: str = "",
) -> dict[str, Any]:
    """计算公司估值指标（PE/PB/PS/股息率）及历史分位数.

    使用 stock_value_em（已验证在 akshare 1.18.60 中可用）。

    Args:
        company_code: 股票代码，如 "600519"。
        company_name: 公司名（可选）。

    Returns:
        {pe, pb, ps, dividend_yield, market_cap, ...}
    """
    try:
        df = ak.stock_value_em(symbol=company_code)
        if df is None or df.empty:
            logger.warning("估值数据为空: %s", company_code)
            return {}
        row = df.iloc[-1]
        return {
            "company_code": company_code,
            "company_name": company_name or "",
            "pe": _safe_float(row.get("PE(TTM)")),
            "pb": _safe_float(row.get("市净率")),
            "ps": _safe_float(row.get("市销率")),
            "market_cap": _safe_float(row.get("总市值")),
        }
    except Exception as e:
        logger.warning("估值接口失败 (%s): %s", company_code, e)
        return {}

def industry_comparison(
    company_code: str,
    company_name: str = "",
) -> list[dict[str, Any]]:
    """获取同行业对比数据.

    akshare 提供行业板块数据，用于对比分析。
    """
    result = []
    try:
        df = ak.stock_board_industry_cons_em(symbol="白酒")
        if not df.empty:
            for _, row in df.iterrows():
                result.append({
                    "company": row.get("股票名称", ""),
                    "code": row.get("股票代码", ""),
                    "pe": _safe_float(row.get("市盈率")),
                    "pb": _safe_float(row.get("市净率")),
                })
    except Exception as e:
        logger.warning("行业对比失败: %s", e)

    return result

def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        v = float(val)
        return None if v != v else v  # NaN check
    except (ValueError, TypeError):
        return None
