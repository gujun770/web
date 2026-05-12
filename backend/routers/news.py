import asyncio
import urllib.request
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from cache.news_cache import (
    clear_news_cache,
    get_cache_news_list,
    get_cached_categories,
    set_cache_categories,
    set_cache_news_list,
)
from config.db_conf import get_db
from crud import news
from services.hot_news_fetcher import (
    fetch_all_channel_hot_news,
    fetch_article_detail_from_content,
    fetch_hot_news,
    image_dimensions_from_bytes,
    MIN_IMAGE_BYTES,
    MIN_IMAGE_HEIGHT,
    MIN_IMAGE_WIDTH,
)
from services.main_agent_loader import rebuild_news_vector_store


router = APIRouter(prefix="/api/news", tags=["news"])


def fetch_image_bytes(url: str) -> tuple[bytes, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("图片地址不合法")

    referer = f"{parsed.scheme}://{parsed.netloc}/"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": referer,
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        content = response.read()
        media_type = response.headers.get_content_type() or "image/jpeg"
    if not media_type.startswith("image/") or media_type in {"image/svg+xml", "image/gif"}:
        raise ValueError("unsupported image type")
    if len(content) < MIN_IMAGE_BYTES:
        raise ValueError("image file is too small")
    width, height = image_dimensions_from_bytes(content[:262144])
    if width is not None and height is not None and (width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT):
        raise ValueError("image dimensions are too small")
    return content, media_type


async def sync_news_vector_store() -> dict:
    try:
        return await asyncio.to_thread(rebuild_news_vector_store, 200)
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/categories")
async def get_categories(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    if skip == 0:
        cached = await get_cached_categories()
        if cached:
            return {"code": 200, "message": "获取新闻分类成功", "data": cached}

    categories = await news.get_categories(db, skip, limit)
    if skip == 0:
        await set_cache_categories(jsonable_encoder(categories))
    return {"code": 200, "message": "获取新闻分类成功", "data": categories}


@router.get("/image")
async def proxy_image(url: str = Query(...)):
    try:
        content, media_type = await asyncio.to_thread(fetch_image_bytes, url)
    except Exception:
        raise HTTPException(status_code=404, detail="图片加载失败")
    return Response(
        content=content,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/list")
async def get_news_list(
    category_id: int = Query(..., alias="categoryId"),
    page: int = 1,
    page_size: int = Query(10, alias="pageSize", le=100),
    db: AsyncSession = Depends(get_db),
):
    await news.delete_generated_news(db)
    offset = (page - 1) * page_size
    cached = await get_cache_news_list(category_id, page, page_size)
    if cached:
        return {"code": 200, "message": "获取新闻列表成功", "data": cached}

    total = await news.get_news_count(db, category_id)
    news_list = await news.get_news_list(db, category_id, offset, page_size)
    has_more = (offset + len(news_list)) < total
    data = {"list": jsonable_encoder(news_list), "total": total, "hasMore": has_more}
    await set_cache_news_list(category_id, page, page_size, data)
    return {
        "code": 200,
        "message": "获取新闻列表成功",
        "data": data,
    }


@router.get("/detail")
async def get_news_detail(news_id: int = Query(..., alias="id"), db: AsyncSession = Depends(get_db)):
    news_detail = await news.get_news_detail(db, news_id)
    if not news_detail:
        raise HTTPException(status_code=404, detail="新闻不存在")

    views_res = await news.increase_news_views(db, news_detail.id)
    if not views_res:
        raise HTTPException(status_code=404, detail="新闻不存在")

    detail_data = await asyncio.to_thread(
        fetch_article_detail_from_content,
        news_detail.content,
        news_detail.title,
        False,
        news_detail.source_url,
    )
    if detail_data.get("trusted") and detail_data.get("content") and detail_data["content"] != news_detail.content:
        news_detail.content = detail_data["content"]
    elif not detail_data.get("trusted") and news_detail.description:
        source_url = news_detail.source_url or ""
        news_detail.content = f"{news_detail.description}\n\n原文链接：{source_url}".strip()
    if detail_data.get("description"):
        news_detail.description = detail_data["description"][:500]
    await db.flush()

    related_news = await news.get_related_news(db, news_detail.id, news_detail.category_id)
    return {
        "code": 200,
        "message": "success",
        "data": {
            "id": news_detail.id,
            "title": news_detail.title,
            "content": news_detail.content,
            "image": news_detail.image,
            "sourceUrl": news_detail.source_url,
            "author": news_detail.author,
            "publishTime": news_detail.publish_time,
            "categoryId": news_detail.category_id,
            "views": news_detail.views,
            "relatedNews": related_news,
        },
    }


@router.post("/fetch-hot")
async def fetch_hot(
    category_id: int = Query(1, alias="categoryId"),
    limit: int = Query(10, ge=1, le=50),
    replace: bool = Query(False, description="是否清空旧新闻后替换为本次抓取结果"),
    use_ai: bool = Query(False, alias="useAi", description="是否使用大模型生成中文摘要"),
    db: AsyncSession = Depends(get_db),
):
    if category_id == 0 and replace:
        hot_items, errors = await asyncio.to_thread(fetch_all_channel_hot_news, min(limit, 10), False)
        if not hot_items:
            raise HTTPException(status_code=502, detail={"message": "没有抓到真实中文新闻，已保留数据库现有内容", "errors": errors})
        result = await news.replace_all_news(db, hot_items)
    else:
        hot_items, errors = await asyncio.to_thread(fetch_hot_news, limit, category_id, True, use_ai)
        if not hot_items:
            raise HTTPException(status_code=502, detail={"message": "没有抓到真实中文新闻，已保留数据库现有内容", "errors": errors})
        result = await news.replace_category_news(db, category_id, hot_items) if replace else await news.upsert_hot_news(db, hot_items)

    await db.commit()
    await clear_news_cache()
    vector_sync = await sync_news_vector_store()

    return {
        "code": 200,
        "message": "热点新闻替换完成" if replace else "热点新闻抓取完成",
        "data": {
            "created": result["created"],
            "updated": result["updated"],
            "fetched": len(hot_items),
            "categoryCounts": {
                str(category_id): sum(1 for item in hot_items if item.get("category_id") == category_id)
                for category_id in range(1, 10)
            },
            "replace": replace,
            "vectorSync": vector_sync,
            "errors": errors,
            "list": result["items"],
        },
    }


@router.get("/hot")
async def get_hot_news(limit: int = Query(10, ge=1, le=50), db: AsyncSession = Depends(get_db)):
    latest_news = await news.get_latest_news(db, limit)
    return {"code": 200, "message": "获取热点新闻成功", "data": latest_news}
