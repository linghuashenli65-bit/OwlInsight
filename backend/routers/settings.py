"""设置接口 — 读写 SQLite 中的持久化设置（替代 MySQL app_settings）."""

from fastapi import APIRouter

from backend.memory.store import memory_store

router = APIRouter()


@router.get("/settings")
def get_settings():
    """读取所有设置 (返回 key-value 对象)."""
    memory_store.connect()
    settings_dict = memory_store.get_all_settings()
    # 类型转换：temperature 存为字符串，返回时转数字
    if "temperature" in settings_dict:
        settings_dict["temperature"] = float(settings_dict["temperature"])
    return settings_dict


@router.post("/settings")
def post_settings(data: dict):
    """保存设置 (接收 key-value 对象)."""
    memory_store.connect()
    str_data = {k: str(v) for k, v in data.items()}
    memory_store.save_settings(str_data)
    return {"status": "ok"}
