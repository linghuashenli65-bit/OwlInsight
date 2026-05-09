"""异步 CRUD 操作 — 设置 / 关注公司 / 研究笔记."""

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import AppSetting, WatchedCompany, ResearchNote


# ──────────── AppSettings ────────────


async def get_all_settings(db: AsyncSession) -> dict[str, str]:
    """读取所有设置项."""
    result = await db.execute(select(AppSetting))
    rows = result.scalars().all()
    return {row.key: row.value for row in rows}


async def upsert_setting(db: AsyncSession, key: str, value: str) -> None:
    """插入或更新一项设置."""
    stmt = select(AppSetting).where(AppSetting.key == key)
    result = await db.execute(stmt)
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        db.add(AppSetting(key=key, value=value))
    await db.commit()


async def save_settings(db: AsyncSession, data: dict[str, str]) -> None:
    """批量保存设置."""
    for key, value in data.items():
        stmt = select(AppSetting).where(AppSetting.key == key)
        result = await db.execute(stmt)
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            db.add(AppSetting(key=key, value=str(value)))
    await db.commit()


# ──────────── Watched Companies ────────────


async def list_companies(db: AsyncSession):
    """获取所有关注公司，按最近分析时间倒序."""
    result = await db.execute(
        select(WatchedCompany).order_by(WatchedCompany.last_analyzed.desc().nullslast())
    )
    return result.scalars().all()


async def get_company(db: AsyncSession, code: str):
    """获取单个公司详情."""
    result = await db.execute(
        select(WatchedCompany).where(WatchedCompany.company_code == code)
    )
    return result.scalar_one_or_none()


# ──────────── Research Notes ────────────


async def list_notes(db: AsyncSession, limit: int = 50):
    """获取研究笔记列表."""
    result = await db.execute(
        select(ResearchNote).order_by(ResearchNote.created_at.desc()).limit(limit)
    )
    return result.scalars().all()


async def get_note(db: AsyncSession, note_id: int):
    """获取单条笔记."""
    result = await db.execute(
        select(ResearchNote).where(ResearchNote.id == note_id)
    )
    return result.scalar_one_or_none()
