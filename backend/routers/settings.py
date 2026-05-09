"""设置接口 — 读写 MySQL 中的持久化设置."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.database.crud import save_settings, get_all_settings

router = APIRouter()


@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """读取所有设置 (返回 key-value 对象)."""
    settings_dict = await get_all_settings(db)
    # 类型转换：temperature 存为字符串，返回时转数字
    if "temperature" in settings_dict:
        settings_dict["temperature"] = float(settings_dict["temperature"])
    return settings_dict


@router.post("/settings")
async def post_settings(data: dict, db: AsyncSession = Depends(get_db)):
    """保存设置 (接收 key-value 对象)."""
    # 转换所有值为字符串存储
    str_data = {k: str(v) for k, v in data.items()}
    await save_settings(db, str_data)
    return {"status": "ok"}
