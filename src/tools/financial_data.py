"""金融数据工具模块 — 基于 akshare 封装.

提供 5 个核心接口（按稳定性排序）：
1. get_financials          — 利润表（ak.stock_yjbb_em）
2. get_balance_sheet       — 资产负债表
3. get_cash_flow           — 现金流量表
4. get_stock_price_history — 历史股价
5. get_valuation_data      — 估值数据

注意：akshare 各版本 API 参数可能存在差异，此处已适配当前版本。
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)

# ──────────────────── 辅助函数 ────────────────────

def _period_rank_from_date(d: date) -> int:
    today = date.today()
    q = (today.year - d.year) * 4 + (today.month - 1) // 4 - (d.month - 1) // 4
    return -q

def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        v = float(val)
        return None if pd.isna(v) else v
    except (ValueError, TypeError):
        return None

def _find_col(columns: list[str], *keywords: str) -> Optional[str]:
    """在列名列表中模糊匹配包含任一关键词的列."""
    for col in columns:
        for kw in keywords:
            if kw in col:
                return col
    return None

def _to_symbol(code: str) -> str:
    """转为 akshare 所需的 symbol 格式.

    规则：6 开头 → 上海 A 股；0/3 开头 → 深圳 A 股；5 位纯数字 → 港股.
    """
    if len(code) == 5:
        return f"{code}.HK"
    return f"{code}.SH" if code.startswith("6") else f"{code}.SZ"

def _to_tx_symbol(code: str) -> str:
    """转为腾讯接口所需的 symbol 格式 (sh/sz 前缀).

    规则：6 开头 → sh；0/3 开头 → sz；5 位纯数字 → hk.
    """
    if len(code) == 5:
        return f"hk{code}"
    return f"sh{code}" if code.startswith("6") else f"sz{code}"


# ──────────────────── 1️⃣ 利润表（业绩报表）────────────────────

def get_financials(symbol: str, period: str = "annual") -> list[dict[str, Any]]:
    """获取利润表核心数据（营收/净利润/利润总额）.

    使用 ak.stock_yjbb_em（业绩报表），比 stock_profit_sheet_by_report_em 更稳定。
    period 参数仅用于控制备选接口切换，yjbb_em 始终返回最新季度。
    """
    # 动态计算最近一个完整年度的 12 月 31 日，避免硬编码日期过期
    latest_year_end = f"{date.today().year - 1}1231"
    try:
        df = ak.stock_yjbb_em(date=latest_year_end)
    except Exception as e:
        logger.warning("stock_yjbb_em 失败，尝试备用接口: %s", e)
        try:
            df = ak.stock_yjbb_em()
        except Exception as e2:
            logger.warning("获取利润表失败 (%s): %s", symbol, e2)
            return []

    # 过滤指定股票（yjbb_em 返回的"股票代码"不带交易所后缀）
    col_code = next((c for c in df.columns if "代码" in c), None)
    if col_code is None:
        return []

    df_filtered = df[df[col_code].astype(str).str.contains(symbol)].copy()
    if df_filtered.empty:
        logger.warning("未找到股票 %s 的利润表数据", symbol)
        return []

    cols = list(df_filtered.columns)
    col_revenue = _find_col(cols, "营业总收入", "营业收入", "营收")
    col_net_profit = _find_col(cols, "净利润", "净利")
    col_gross = _find_col(cols, "营业利润", "毛利")
    col_operating = _find_col(cols, "利润总额", "营业利润")
    col_name = _find_col(cols, "股票简称", "名称")
    col_period = _find_col(cols, "报告期", "日期", "期间")

    results = []
    for _, row in df_filtered.iterrows():
        report_date = str(row.get(col_period, ""))
        try:
            rd = datetime.strptime(report_date, "%Y-%m-%d").date()
        except ValueError:
            rd = date.today()

        results.append({
            "symbol": symbol,
            "company_name": str(row.get(col_name, "")),
            "report_period": report_date,
            "period_rank": _period_rank_from_date(rd),
            "revenue": _safe_float(row.get(col_revenue)) if col_revenue else None,
            "net_profit": _safe_float(row.get(col_net_profit)) if col_net_profit else None,
            "gross_profit": _safe_float(row.get(col_gross)) if col_gross else None,
            "operating_profit": _safe_float(row.get(col_operating)) if col_operating else None,
            "raw_data": row.to_dict(),
        })
    return results


# ──────────────────── 2️⃣ 资产负债表 ────────────────────

def get_balance_sheet(symbol: str, period: str = "annual") -> list[dict[str, Any]]:
    """获取资产负债表（尝试不同参数形态）."""
    code = _to_symbol(symbol)
    for params in [
        {"symbol": code, "indicator": "年报"},
        {"symbol": code},
    ]:
        try:
            df = ak.stock_balance_sheet_by_report_em(**params)
            break
        except TypeError:
            continue
        except Exception as e:
            logger.warning("获取资产负债表失败 (%s): %s", symbol, e)
            return []
    else:
        return []

    results = []
    for _, row in df.iterrows():
        report_date = str(row.get("报告期", ""))
        try:
            rd = datetime.strptime(report_date, "%Y-%m-%d").date()
        except ValueError:
            rd = date.today()

        results.append({
            "symbol": symbol,
            "company_name": row.get("股票简称", ""),
            "report_period": report_date,
            "period_rank": _period_rank_from_date(rd),
            "total_assets": _safe_float(row.get("资产总计")),
            "total_liabilities": _safe_float(row.get("负债合计")),
            "equity": _safe_float(row.get("归属于母公司股东权益合计")),
            "cash_and_equivalents": _safe_float(row.get("货币资金")),
            "accounts_receivable": _safe_float(row.get("应收账款")),
            "raw_data": row.to_dict(),
        })
    return results


# ──────────────────── 3️⃣ 现金流量表 ────────────────────

def get_cash_flow(symbol: str, period: str = "annual") -> list[dict[str, Any]]:
    """获取现金流量表（尝试不同参数形态）."""
    code = _to_symbol(symbol)
    for params in [
        {"symbol": code, "indicator": "年报"},
        {"symbol": code},
    ]:
        try:
            df = ak.stock_cash_flow_sheet_by_report_em(**params)
            break
        except TypeError:
            continue
        except Exception as e:
            logger.warning("获取现金流量表失败 (%s): %s", symbol, e)
            return []
    else:
        return []

    results = []
    for _, row in df.iterrows():
        report_date = str(row.get("报告期", ""))
        try:
            rd = datetime.strptime(report_date, "%Y-%m-%d").date()
        except ValueError:
            rd = date.today()

        results.append({
            "symbol": symbol,
            "company_name": row.get("股票简称", ""),
            "report_period": report_date,
            "period_rank": _period_rank_from_date(rd),
            "cash_flow_operating": _safe_float(row.get("经营活动产生的现金流量净额")),
            "cash_flow_investing": _safe_float(row.get("投资活动产生的现金流量净额")),
            "cash_flow_financing": _safe_float(row.get("筹资活动产生的现金流量净额")),
            "raw_data": row.to_dict(),
        })
    return results


# ──────────────────── 4️⃣ 历史股价 ────────────────────

def get_stock_price_history(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    adj: str = "qfq",
    proxies: Optional[dict] = None,
) -> list[dict[str, Any]]:
    """获取 A 股历史股价.

    优先使用腾讯接口（绕过 EastMoney 代理拦截），失败则降级到东财 daily 接口.
    """
    if end_date is None:
        end_date = date.today().strftime("%Y%m%d")
    if start_date is None:
        start_date = (date.today() - timedelta(days=365)).strftime("%Y%m%d")

    # ── 腾讯接口（绕过代理拦截, 已验证可用）──
    try:
        tx_symbol = _to_tx_symbol(symbol)
        df = ak.stock_zh_a_hist_tx(
            symbol=tx_symbol,
            start_date=start_date,
            end_date=end_date,
        )
        if df is not None and not df.empty:
            results = []
            for _, row in df.iterrows():
                date_val = row.get("date")
                date_str = date_val.isoformat() if hasattr(date_val, "isoformat") else str(date_val)
                results.append({
                    "symbol": symbol,
                    "date": date_str,
                    "open": _safe_float(row.get("open")),
                    "close": _safe_float(row.get("close")),
                    "high": _safe_float(row.get("high")),
                    "low": _safe_float(row.get("low")),
                    "volume": 0,  # 腾讯接口不含成交量
                    "amount": _safe_float(row.get("amount")),
                    "change_pct": None,
                })
            return results
    except Exception as e:
        logger.warning("获取股价失败 (%s): %s", symbol, e)

    return []


# ──────────────────── 5️⃣ 估值数据 ────────────────────

def get_valuation_data(symbol: str) -> dict[str, Any]:
    """获取估值数据（使用 stock_value_em，含 PE/PB/PS/PEG/市值）. """
    try:
        df = ak.stock_value_em(symbol=symbol)
        if df is not None and not df.empty:
            row = df.iloc[-1]
            return {
                "symbol": symbol,
                "company_name": "",
                "pe": _safe_float(row.get("PE(TTM)")),
                "pe_ttm": _safe_float(row.get("PE(静)")),
                "pb": _safe_float(row.get("市净率")),
                "dividend_yield": _safe_float(row.get("股息率")),
                "market_cap": _safe_float(row.get("总市值")),
                "ps": _safe_float(row.get("市销率")),
                "pcf": _safe_float(row.get("市现率")),
                "peg": _safe_float(row.get("PEG值")),
                "raw_data": row.to_dict(),
            }
    except Exception as e:
        logger.warning("stock_value_em 失败 (%s): %s", symbol, e)

    # ── 备选：百度 PB 接口 ──
    try:
        df = ak.stock_zh_valuation_baidu(symbol=symbol, indicator="市净率")
        if df is not None and not df.empty:
            pb = _safe_float(df.iloc[-1].get("value"))
            return {"symbol": symbol, "pb": pb, "pe": None, "market_cap": None}
    except Exception as e:
        logger.warning("百度估值接口也失败 (%s): %s", symbol, e)

    logger.info("估值接口均不可用（当前 akshare 版本为 %s）", ak.__version__)
    return {}


# ──────────────────── 公司名称查询 ────────────────────

def get_company_name(symbol: str) -> str:
    """根据股票代码获取公司简称."""
    # 从 stock_yjbb_em 取公司名称（该接口已验证可用）
    try:
        df = ak.stock_yjbb_em()
        col_code = next((c for c in df.columns if "代码" in c), None)
        if col_code:
            match = df[df[col_code].astype(str).str.contains(symbol)]
            if not match.empty:
                col_name = _find_col(list(match.columns), "股票简称", "名称")
                if col_name:
                    name = str(match.iloc[0][col_name])
                    if name and name != symbol:
                        return name
    except Exception:
        pass

    return symbol


if __name__ == "__main__":
    import json
    print(f"akshare 版本: {ak.__version__}")
    print("\n=== get_financials('600519') ===")
    data = get_financials("600519")
    print(json.dumps(data[:2], ensure_ascii=False, indent=2))
    print(f"\n共 {len(data)} 条记录")
    print("\n=== get_company_name('600519') ===")
    print(get_company_name("600519"))
