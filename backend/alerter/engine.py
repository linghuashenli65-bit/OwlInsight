"""调度引擎 — 基于 APScheduler 的定时任务管理.

注册三个核心任务：
1. 盘前邮件（默认 08:30）— 新闻摘要 + 财报提醒
2. 盘中检测（09:30-15:00 每 5 分钟）— 价格/资金流异常
3. 盘后邮件（默认 15:30）— 当日总结
"""

from backend.logger import logger
from datetime import datetime, time
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from backend.alerter.detector import (
    check_price_alerts,
    get_pre_market_alerts,
    get_post_market_summaries,
)
from backend.alerter.notifier import (
    is_email_enabled,
    get_email_time,
    send_email,
    render_pre_market_html,
    render_post_market_html,
    sse_manager,
)
from backend.memory.store import memory_store


class AlertEngine:
    """告警调度引擎，管理所有定时任务."""

    def __init__(self) -> None:
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._started = False

    # ────────── 生命周期 ──────────

    def start(self) -> None:
        """启动调度器，注册所有定时任务."""
        if self._started:
            return

        self.scheduler = AsyncIOScheduler()
        self._register_jobs()
        self.scheduler.start()
        self._started = True
        logger.info("告警调度引擎已启动")

    def stop(self) -> None:
        """停止调度器."""
        if self.scheduler and self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False
            logger.info("告警调度引擎已停止")

    # ────────── 任务注册 ──────────

    def _register_jobs(self) -> None:
        """注册所有定时任务。时间从 app_settings 读取，支持运行时修改."""
        if not self.scheduler:
            return

        # 盘前任务 — 每天在用户设定的时间执行
        pre_time = get_email_time("alert_email_premarket_time", "08:30")
        pre_hour, pre_minute = pre_time.split(":") if ":" in pre_time else ("08", "30")
        self.scheduler.add_job(
            self._pre_market_job,
            trigger=CronTrigger(hour=int(pre_hour), minute=int(pre_minute)),
            id="pre_market",
            name="盘前简报",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        logger.info("盘前任务已注册: 每日 %s:%s", pre_hour, pre_minute)

        # 盘中检测 — 09:30-15:00 每 5 分钟
        self.scheduler.add_job(
            self._intraday_job,
            trigger=IntervalTrigger(minutes=5),
            id="intraday",
            name="盘中检测",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        logger.info("盘中检测已注册: 每 5 分钟")

        # 盘后任务 — 每天在用户设定的时间执行
        post_time = get_email_time("alert_email_postmarket_time", "15:30")
        post_hour, post_minute = post_time.split(":") if ":" in post_time else ("15", "30")
        self.scheduler.add_job(
            self._post_market_job,
            trigger=CronTrigger(hour=int(post_hour), minute=int(post_minute)),
            id="post_market",
            name="盘后总结",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        logger.info("盘后任务已注册: 每日 %s:%s", post_hour, post_minute)

    def refresh_jobs(self) -> None:
        """刷新任务（用户更改时间配置后调用）.

        删除旧任务并重新注册，使新时间配置生效。
        """
        if not self.scheduler or not self._started:
            return
        for job_id in ("pre_market", "post_market"):
            try:
                self.scheduler.remove_job(job_id)
            except Exception:
                pass
        # 重新注册
        pre_time = get_email_time("alert_email_premarket_time", "08:30")
        pre_hour, pre_minute = pre_time.split(":") if ":" in pre_time else ("08", "30")
        self.scheduler.add_job(
            self._pre_market_job,
            trigger=CronTrigger(hour=int(pre_hour), minute=int(pre_minute)),
            id="pre_market",
            name="盘前简报",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        post_time = get_email_time("alert_email_postmarket_time", "15:30")
        post_hour, post_minute = post_time.split(":") if ":" in post_time else ("15", "30")
        self.scheduler.add_job(
            self._post_market_job,
            trigger=CronTrigger(hour=int(post_hour), minute=int(post_minute)),
            id="post_market",
            name="盘后总结",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        logger.info("告警任务时间已刷新: 盘前=%s 盘后=%s", pre_time, post_time)

    # ────────── 任务实现 ──────────

    async def _pre_market_job(self) -> None:
        """盘前任务：生成简报 + 发送邮件."""
        logger.info("[盘前] 开始生成盘前简报")
        try:
            report = get_pre_market_alerts()
            company_alerts = report.get("company_alerts", [])
            if not company_alerts:
                logger.info("[盘前] 无关注公司，跳过")
                return

            date_str = datetime.now().strftime("%Y-%m-%d")
            html = render_pre_market_html(report, date_str)

            # 推送到前端
            await sse_manager.broadcast({
                "type": "pre_market",
                "title": f"盘前简报 {date_str}",
                "report": report,
                "time": date_str,
            })

            # 发送邮件
            if is_email_enabled():
                send_email(
                    subject=f"盘前简报 {date_str} — {len(company_alerts)} 家公司",
                    html_body=html,
                )

            logger.info("[盘前] 简报完成: %d 家公司", len(company_alerts))
        except Exception as e:
            logger.exception("[盘前] 任务异常: %s", e)

    async def _intraday_job(self) -> None:
        """盘中检测：检查价格异常，触发弹窗推送."""
        # 非交易时段跳过（周一至周五 09:30-15:00）
        now = datetime.now()
        if now.weekday() >= 5 or not (time(9, 30) <= now.time() <= time(15, 0)):
            return
        try:
            events = check_price_alerts()
            for event in events:
                # 记录到数据库
                memory_store.record_alert(event)
                # SSE 推送到前端
                await sse_manager.broadcast({
                    "type": "alert",
                    "alert_type": event["event_type"],
                    "title": event["title"],
                    "message": event["message"],
                    "severity": event["severity"],
                    "company_code": event["company_code"],
                    "data": event.get("data", {}),
                    "time": datetime.now().isoformat(),
                })
                logger.info("价格告警: %s", event["title"][:50])
        except Exception as e:
            logger.exception("[盘中] 检测异常: %s", e)

    async def _post_market_job(self) -> None:
        """盘后任务：生成总结 + 发送邮件."""
        logger.info("[盘后] 开始生成盘后总结")
        try:
            summaries = get_post_market_summaries()
            if not summaries:
                logger.info("[盘后] 无关注公司数据，跳过")
                return

            date_str = datetime.now().strftime("%Y-%m-%d")
            html = render_post_market_html(summaries, date_str)

            # 推送到前端
            await sse_manager.broadcast({
                "type": "post_market",
                "title": f"盘后总结 {date_str}",
                "summaries": summaries,
                "time": date_str,
            })

            # 发送邮件
            if is_email_enabled():
                send_email(
                    subject=f"盘后总结 {date_str} — {len(summaries)} 家公司",
                    html_body=html,
                )

            logger.info("[盘后] 总结完成: %d 家公司", len(summaries))
        except Exception as e:
            logger.exception("[盘后] 任务异常: %s", e)
