"""股票代码映射 — 公司名 ↔ 代码双向查找.

提供两个核心功能：
1. COMMON_STOCKS: 公司名(简称) → 代码的正向映射
2. lookup_company_code(): 从公司全称/片段模糊匹配到股票代码
"""

from typing import Optional

# ──────────────────── 正向映射：公司名(简称) → 股票代码 ────────────────────

COMMON_STOCKS: dict[str, str] = {
    # A 股
    "贵州茅台": "600519",
    "茅台": "600519",
    "五粮液": "000858",
    "宁德时代": "300750",
    "宁王": "300750",
    "比亚迪": "002594",
    "迪王": "002594",
    "海康威视": "002415",
    "招商银行": "600036",
    "中国平安": "601318",
    "美的集团": "000333",
    "格力电器": "000651",
    "隆基绿能": "601012",
    "药明康德": "603259",
    "迈瑞医疗": "300760",
    "中信证券": "600030",
    "万华化学": "600309",
    "恒瑞医药": "600276",
    "兴业银行": "601166",
    "工商银行": "601398",
    "建设银行": "601939",
    "农业银行": "601288",
    "中国银行": "601988",
    "平安银行": "000001",
    "京东方": "000725",
    "立讯精密": "002475",
    "伊利股份": "600887",
    "海尔智家": "600690",
    "三一重工": "600031",
    "中芯国际": "688981",
    "金山办公": "688111",
    # 港股
    "腾讯控股": "00700",
    "腾讯": "00700",
    "阿里巴巴": "09988",
    "阿里": "09988",
    "美团": "03690",
    "美团点评": "03690",
    "小米集团": "01810",
    "小米": "01810",
    "京东": "09618",
    "网易": "09999",
    "百度": "09888",
    "快手": "01024",
    "香港交易所": "00388",
    "港交所": "00388",
    "友邦保险": "01299",
    "中国移动": "00941",
    "中国海洋石油": "00883",
    "中海油": "00883",
    "中石油": "00857",
    "中国石油": "00857",
    "中石化": "00386",
    "中国石化": "00386",
    "联想集团": "00992",
    # 美股
    "苹果": "AAPL",
    "苹果公司": "AAPL",
    "微软": "MSFT",
    "微软公司": "MSFT",
    "谷歌": "GOOGL",
    "谷歌公司": "GOOGL",
    "Google": "GOOGL",
    "亚马逊": "AMZN",
    "特斯拉": "TSLA",
    "特斯拉公司": "TSLA",
    "Meta": "META",
    "脸书": "META",
    "英伟达": "NVDA",
    "NVIDIA": "NVDA",
    "台积电": "TSM",
    "伯克希尔": "BRK.B",
    "伯克希尔哈撒韦": "BRK.B",
    "强生": "JNJ",
    "沃尔玛": "WMT",
    "Visa": "V",
    "万事达": "MA",
    "迪士尼": "DIS",
    "可口可乐": "KO",
    "百事可乐": "PEP",
    "麦当劳": "MCD",
    "耐克": "NKE",
    "奈飞": "NFLX",
    "Netflix": "NFLX",
    "Adobe": "ADBE",
    "英特尔": "INTC",
    "Intel": "INTC",
    "AMD": "AMD",
    "超威半导体": "AMD",
    "IBM": "IBM",
    "甲骨文": "ORCL",
    "思科": "CSCO",
    "高通": "QCOM",
    "博通": "AVGO",
    "德州仪器": "TXN",
    "应用材料": "AMAT",
    "阿斯麦": "ASML",
    "ASML": "ASML",
    "优步": "UBER",
    "Uber": "UBER",
    "Salesforce": "CRM",
    "PayPal": "PYPL",
    "贝宝": "PYPL",
    "拼多多": "PDD",
    "PDD": "PDD",
}

# 大盘指数代码映射
INDEX_CODES: dict[str, str] = {
    "上证指数": "000001",
    "大盘": "000001",
    "上证": "000001",
    "沪指": "000001",
    "深证成指": "399001",
    "深成指": "399001",
    "创业板指": "399006",
    "创业板": "399006",
    "沪深300": "000300",
    "科创50": "000688",
}


# ──────────────────── US 中概股代码 → 港股/A股代码 ────────────────────
# 当 LLM 返回美股代码时，翻译为系统支持的港股/A股代码
US_TO_HK_STOCKS: dict[str, str] = {
    "BABA": "09988",      # 阿里巴巴
    "TCEHY": "00700",     # 腾讯控股 (ADR)
    "TCTZF": "00700",     # 腾讯控股 (OTC)
    "NTES": "09999",      # 网易
    "BIDU": "09888",      # 百度
    "JD": "09618",        # 京东
    "JDCF": "09618",      # 京东 (OTC)
    "MPNGY": "03690",     # 美团 (OTC)
    "MPNGF": "03690",     # 美团 (OTC)
    "XIAOMI": "01810",    # 小米集团 (OTC)
    "XIACY": "01810",     # 小米集团 (OTC)
    "KUAISHOU": "01024",  # 快手 (OTC)
    "TME": "01698",       # 腾讯音乐
    "WBD": "09626",       # 哔哩哔哩
    "BILI": "09626",      # 哔哩哔哩
    "YUMC": "09987",      # 百胜中国
    "ZTO": "02057",       # 中通快递
    "NIO": "09866",       # 蔚来
    "LI": "02015",        # 理想汽车
    "XPEV": "09868",      # 小鹏汽车
}


# ──────────────────── 美股代码反向查找（ticker → 中文名） ────────────────────

_US_NAME_MAP: dict[str, str] = {code: name for name, code in COMMON_STOCKS.items() if not code.isdigit()}


def lookup_company_code(company_name: str) -> str:
    """从公司名（全称/片段）模糊匹配股票代码.

    先尝试精确匹配（COMMON_STOCKS），再尝试子串匹配。
    港股代码保留 5 位格式（如 "00700"），A 股代码为 6 位。

    Returns:
        匹配到的代码，未匹配返回空字符串。
    """
    if not company_name:
        return ""

    # 1. 精确匹配
    if company_name in COMMON_STOCKS:
        return COMMON_STOCKS[company_name]

    # 2. 子串匹配：COMMON_STOCKS 的 key 是否在 company_name 中
    #    按 key 长度降序，优先匹配更长（更精确）的 key
    for name in sorted(COMMON_STOCKS, key=len, reverse=True):
        if name in company_name:
            return COMMON_STOCKS[name]

    # 3. 反向子串：company_name 是否在某个 key 中
    for name, code in COMMON_STOCKS.items():
        if company_name in name:
            return code

    return ""


def match_stock_in_text(text: str) -> tuple[str, str]:
    """在文本中扫描最可能出现的公司名，返回 (公司名, 代码).

    Args:
        text: 待扫描文本（如 PDF 首页内容）。

    Returns:
        (匹配到的公司名, 股票代码)，均可能为空。
    """
    best_name = ""
    best_code = ""
    # 按 key 长度降序，优先匹配更长（更精确）的公司名
    for name in sorted(COMMON_STOCKS, key=len, reverse=True):
        if name in text:
            best_name = name
            best_code = COMMON_STOCKS[name]
            break
    return best_name, best_code
