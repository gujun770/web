from sqlalchemy import delete, select, func, update, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from models.favorite import Favorite
from models.history import History
from models.news import Category, News

DEFAULT_CATEGORIES = [
    (1, "头条", 1),
    (2, "社会", 2),
    (3, "国内", 3),
    (4, "国际", 4),
    (5, "娱乐", 5),
    (6, "体育", 6),
    (7, "军事", 7),
    (8, "科技", 8),
    (9, "财经", 9),
    (10, "更多", 10),
]

SCHEMA_CHECKED = False


async def get_categories(db: AsyncSession, skip: int = 0, limit: int = 100):
    await ensure_default_categories(db)
    stmt = select(Category).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


async def ensure_default_categories(db: AsyncSession):
    await ensure_news_schema(db)
    for category_id, name, sort_order in DEFAULT_CATEGORIES:
        result = await db.execute(select(Category).where(Category.id == category_id))
        category = result.scalar_one_or_none()
        if category:
            if category.name != name:
                category.name = name
            category.sort_order = sort_order
            continue

        name_result = await db.execute(select(Category).where(Category.name == name))
        category = name_result.scalar_one_or_none()
        if category:
            db.add(Category(id=category_id, name=f"{name}-{category_id}", sort_order=sort_order))
            continue

        db.add(Category(id=category_id, name=name, sort_order=sort_order))
    await db.flush()


async def ensure_news_schema(db: AsyncSession):
    global SCHEMA_CHECKED
    if SCHEMA_CHECKED:
        return
    try:
        await db.execute(text("ALTER TABLE news MODIFY COLUMN image VARCHAR(1000) NULL COMMENT '封面图片URL'"))
        await db.execute(text("ALTER TABLE news ADD COLUMN source_url VARCHAR(1000) NULL COMMENT '原文链接'"))
    except Exception:
        pass
    try:
        await db.execute(text("CREATE INDEX idx_news_source_url ON news (source_url(255))"))
    except Exception:
        pass
    try:
        SCHEMA_CHECKED = True
    except Exception:
        SCHEMA_CHECKED = True
        pass


async def delete_generated_news(db: AsyncSession):
    generated_conditions = [
        News.author == "本地兜底热点",
        News.author.like("%热点源"),
        News.content.like("%本地热点数据%"),
        News.content.like("%保证演示%"),
        News.title.like("%热点：%成为今日关注焦点%"),
    ]
    news_ids_result = await db.execute(select(News.id).where(or_(*generated_conditions)))
    news_ids = [row[0] for row in news_ids_result.all()]
    if not news_ids:
        return 0

    await db.execute(delete(Favorite).where(Favorite.news_id.in_(news_ids)))
    await db.execute(delete(History).where(History.news_id.in_(news_ids)))
    await db.execute(delete(News).where(News.id.in_(news_ids)))
    await db.flush()
    return len(news_ids)


async def get_news_list(db: AsyncSession, category_id: int, skip: int = 0, limit: int = 10):
    await ensure_news_schema(db)
    # 查询的是指定分类下的所有新闻
    conditions = [News.category_id == category_id]
    stmt = (
        select(News)
        .where(*conditions)
        .order_by(News.publish_time.desc(), News.views.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_news_count(db: AsyncSession, category_id: int):
    await ensure_news_schema(db)
    # 查询的是指定分类下的新闻数量
    conditions = [News.category_id == category_id]
    stmt = select(func.count(News.id)).where(*conditions)
    result = await db.execute(stmt)
    return result.scalar_one()  # 只能有一个结果，否则报错


async def get_news_detail(db: AsyncSession, news_id: int):
    await ensure_news_schema(db)
    stmt = select(News).where(News.id == news_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def increase_news_views(db: AsyncSession, news_id: int):
    stmt = update(News).where(News.id == news_id).values(views=News.views + 1)
    result = await db.execute(stmt)
    await db.commit()

    # 更新 → 检查数据库是否真的命中了数据 → 命中了返回True
    return result.rowcount > 0


async def get_related_news(db: AsyncSession, news_id: int, category_id: int, limit: int = 5):
    # order_by 排序 → 浏览量和发布时间
    stmt = select(News).where(
        News.category_id == category_id,
        News.id != news_id
    ).order_by(
        News.views.desc(),  # 默认是升序，desc 表示降序
        News.publish_time.desc()
    ).limit(limit)
    result = await db.execute(stmt)
    # return result.scalars().all()
    related_news = result.scalars().all()
    # 列表推导式 推导出新闻的核心数据，然后再 return
    return [{
        "id": news_detail.id,
        "title": news_detail.title,
        "content": news_detail.content,
        "image": news_detail.image,
        "author": news_detail.author,
        "publishTime": news_detail.publish_time,
        "categoryId": news_detail.category_id,
        "views": news_detail.views
    } for news_detail in related_news]


async def get_latest_news(db: AsyncSession, limit: int = 8):
    stmt = (
        select(News)
        .order_by(News.publish_time.desc(), News.views.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def upsert_hot_news(db: AsyncSession, news_items: list[dict]):
    await ensure_default_categories(db)
    created = 0
    updated = 0
    saved_items = []

    for item in news_items:
        source_url = item.get("source_url")
        stmt = select(News).where(News.source_url == source_url) if source_url else select(News).where(News.title == item["title"])
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        values = {
            "title": item["title"],
            "description": (item.get("description") or "")[:500],
            "content": item.get("content") or item.get("description") or item["title"],
            "image": (item.get("image") or "")[:1000] or None,
            "source_url": (source_url or "")[:1000] or None,
            "author": item.get("source_name", "热点新闻"),
            "category_id": item.get("category_id", 1),
            "views": item.get("hot_score", 0),
            "publish_time": item.get("publish_time"),
        }

        if existing:
            for key, value in values.items():
                if value is not None:
                    setattr(existing, key, value)
            updated += 1
            saved_items.append(existing)
        else:
            news = News(**values)
            db.add(news)
            created += 1
            saved_items.append(news)

    await db.flush()
    return {
        "created": created,
        "updated": updated,
        "items": saved_items,
    }


async def replace_all_news(db: AsyncSession, news_items: list[dict]):
    await db.execute(delete(Favorite))
    await db.execute(delete(History))
    await db.execute(delete(News))
    await db.flush()
    return await upsert_hot_news(db, news_items)


async def replace_category_news(db: AsyncSession, category_id: int, news_items: list[dict]):
    if category_id == 1:
        return await replace_all_news(db, news_items)

    news_ids_result = await db.execute(select(News.id).where(News.category_id == category_id))
    news_ids = [row[0] for row in news_ids_result.all()]
    if news_ids:
        await db.execute(delete(Favorite).where(Favorite.news_id.in_(news_ids)))
        await db.execute(delete(History).where(History.news_id.in_(news_ids)))
        await db.execute(delete(News).where(News.id.in_(news_ids)))
        await db.flush()
    return await upsert_hot_news(db, news_items)
