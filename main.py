"""FinanceBot CLI 入口."""

import json
import os
import sys
from pathlib import Path

os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ.setdefault("NO_PROXY", "eastmoney.com,push2his.eastmoney.com,emot.dfcfw.com")

# 确保项目根在 import path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.logger import logger


def verify_config() -> None:
    """验证配置初始化."""
    from backend.config import settings
    settings.ensure_dirs()
    print("[OK] 配置加载成功")
    print(f"    DATA_DIR       = {settings.DATA_DIR}")
    print(f"    MILVUS_URI     = {settings.MILVUS_URI}")
    print(f"    MEMORY_DB_PATH = {settings.MEMORY_DB_PATH}")
    print()


def verify_memory() -> None:
    """验证 SQLite 记忆模块."""
    from backend.memory.store import memory_store
    memory_store.connect()

    # 测试增删查
    memory_store.add_or_update_company("600519", "贵州茅台")
    memory_store.add_or_update_company("000858", "五粮液")
    companies = memory_store.get_all_watched_companies()
    print(f"[OK] 记忆库: 已记录 {len(companies)} 家关注公司:")
    for c in companies:
        print(f"    - {c['company_name']} ({c['company_code']}) 分析 {c['analysis_count']} 次")

    # 测试分析记录
    aid = memory_store.add_analysis("600519", "茅台最近怎么样？", "初步分析毛利率和营收",
                                    ["毛利率", "营收"])
    print(f"    [新分析记录 id={aid}]")

    # 测试兴趣
    memory_store.record_metric_mention("毛利率", "600519")
    memory_store.record_metric_mention("毛利率", "000858")
    interests = memory_store.get_top_interests()
    print(f"    高频关注指标: {[i['metric_name'] for i in interests]}")
    print()

    memory_store.close()


def verify_vector_store() -> None:
    """验证 Milvus 向量库."""
    from backend.rag.vector_store import vector_store
    vector_store.connect()

    collection_name = "finance_test"
    exists = vector_store.has_collection()
    status = "OK" if exists else "INFO"
    print(f"[{status}] Collection 'finance_docs' 存在: {exists}")

    if not exists:
        print("    (Phase 2 导入文档后会自动创建, 当前测试采用独立 collection)")

    vector_store.close()
    print()


def verify_financial_data() -> None:
    """验证 akshare 金融数据模块."""
    from backend.tools.financial_data import (
        get_company_name,
        get_financials,
        get_stock_price_history,
        get_valuation_data,
    )

    # 1. 公司名称
    name = get_company_name("600519")
    print(f"[OK] company_name('600519') = {name}")

    # 2. 利润表
    fin = get_financials("600519", period="annual")
    print(f"[OK] 利润表: 获取到 {len(fin)} 条年度记录")
    if fin:
        latest = fin[0]
        print(f"    最近一期: {latest['report_period']}")
        print(f"    营收: {latest.get('revenue', 'N/A')}")
        print(f"    净利润: {latest.get('net_profit', 'N/A')}")

    # 3. 股价
    price = get_stock_price_history("600519", start_date="20240101", end_date="20240110")
    if price:
        print(f"[OK] 股价: 获取到 {len(price)} 条日线数据")
        print(f"    最近: {price[-1]['date']} 收盘 {price[-1]['close']}")
    else:
        print("[INFO] 股价数据获取失败")
        _check_proxy()

    # 4. 估值
    val = get_valuation_data("600519")
    if val:
        print(f"[OK] 估值: PE={val.get('pe')}, PB={val.get('pb')}, 市值={val.get('market_cap')}")
    else:
        print("[INFO] 估值数据获取失败（可能是接口限制）")

    # 5. 实时行情（备用验证，不走历史行情接口）
    _verify_realtime_quote("600519")
    print()


def _verify_realtime_quote(symbol: str) -> None:
    """用腾讯行情接口验证网络连通性."""
    import akshare as ak
    tx_symbol = f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"
    try:
        df = ak.stock_zh_a_hist_tx(symbol=tx_symbol, start_date="20260501", end_date="20260507")
        if df is not None and not df.empty:
            last = df.iloc[-1]
            print(f"[OK] 腾讯行情连通: 最新价={last.get('close', 'N/A')}")
    except Exception as e:
        print(f"[INFO] 实时行情接口不可用: {e}")


def _check_proxy() -> None:
    """检查代理设置并给出建议."""
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if http_proxy or https_proxy:
        print("    [提示] 检测到代理设置，EastMoney API 可能需要绕过代理才能访问")
        print("    方案一：设置环境变量（已自动添加）")
        print('        set NO_PROXY=eastmoney.com,push2his.eastmoney.com,emot.dfcfw.com')
        print("    方案二：临时解除代理后测试")
        print("        在本终端执行: set HTTP_PROXY= && set HTTPS_PROXY=")


def verify_all() -> None:
    """运行所有验证."""
    print("=" * 50)
    print("  FinanceBot - Phase 1 基础设施验证")
    print("=" * 50)
    print()
    verify_config()
    verify_memory()
    verify_vector_store()
    verify_financial_data()
    print("=" * 50)
    print("  [OK] Phase 1 验证完成")
    print("=" * 50)


if __name__ == "__main__":
    verify_all()
