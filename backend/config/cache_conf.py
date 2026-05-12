import json
import os
from typing import Any

import redis.asyncio as redis


REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))


redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True,
)


async def get_cache(key: str):
    try:
        return await redis_client.get(key)
    except Exception as exc:
        print(f"获取缓存失败：{exc}")
        return None


async def get_json_cache(key: str):
    try:
        data = await redis_client.get(key)
        if data:
            return json.loads(data)
        return None
    except Exception as exc:
        print(f"获取 JSON 缓存失败：{exc}")
        return None


async def set_cache(key: str, value: Any, expire: int = 3600):
    try:
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, default=str)
        await redis_client.setex(key, expire, value)
        return True
    except Exception as exc:
        print(f"设置缓存失败：{exc}")
        return False


async def delete_by_pattern(pattern: str) -> int:
    deleted = 0
    try:
        async for key in redis_client.scan_iter(match=pattern):
            deleted += await redis_client.delete(key)
    except Exception as exc:
        print(f"删除缓存失败：{exc}")
    return deleted
