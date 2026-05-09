"""金融事件提醒系统 — 盘前/盘中/盘后定时推送.

提供三个时段的事件检测与通知：
- 盘前：新闻摘要 + 财报提醒（邮件）
- 盘中：股价异常 + 资金流异动（前端弹窗）
- 盘后：当日总结（邮件）
"""

from backend.alerter.engine import AlertEngine

alert_engine = AlertEngine()

__all__ = ["alert_engine"]
