"""Redis 缓存工具."""

from backend.logger import logger
from typing import Any, Optional
import json

_REDIS_HOST = "localhost"
_REDIS_PORT = 6380  # 已映射到宿主机的 6380

_redis = None

def _get_redis():
    global _redis
    if _redis is None:
        try:
            import redis as _redis_module
            _redis = _redis_module.Redis(
                host=_REDIS_HOST,
                port=_REDIS_PORT,
                db=0,
                decode_responses=True,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
            _redis.ping()
            logger.info("Redis 缓存已连接 (%s:%s)", _REDIS_HOST, _REDIS_PORT)
        except Exception as e:
            logger.warning("Redis 不可用（将使用本地缓存）: %s", e)
            _redis = None
    return _redis

def cache_get(key: str) -> Optional[str]:
    """获取缓存."""
    r = _get_redis()
    if r is None:
        return None
    try:
        return r.get(key)
    except Exception:
        return None

def cache_set(key: str, value: str, ttl: int = 300) -> None:
    """设置缓存（默认 5 分钟失效）. """
    r = _get_redis()
    if r is None:
        return
    try:
        r.setex(key, ttl, value)
    except Exception:
        pass

def cache_get_json(key: str) -> Any:
    """获取 JSON 缓存."""
    data = cache_get(key)
    return json.loads(data) if data else None

def cache_set_json(key: str, value: Any, ttl: int = 300) -> None:
    """设置 JSON 缓存."""
    cache_set(key, json.dumps(value, ensure_ascii=False), ttl)


def cache_invalidate(key: str) -> None:
    """删除指定缓存项."""
    r = _get_redis()
    if r is None:
        return
    try:
        r.delete(key)
    except Exception:
        pass
