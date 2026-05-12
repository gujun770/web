from __future__ import annotations

import os
import re
from collections import OrderedDict
from typing import Any

try:
    import pymysql
    from pymysql.cursors import DictCursor
except Exception:  # pragma: no cover - handled at runtime for user-friendly errors.
    pymysql = None
    DictCursor = None


STANDARD_CATEGORIES = ["头条", "社会", "国内", "国际", "娱乐", "体育", "军事", "科技", "财经"]


CATEGORY_ALIASES = {
    "头条": ["头条", "推荐", "热点", "综合", "全部"],
    "社会": ["社会", "民生"],
    "国内": ["国内", "中国", "政务"],
    "国际": ["国际", "国外", "全球"],
    "娱乐": ["娱乐", "明星", "影视"],
    "体育": ["体育", "比赛", "足球", "篮球"],
    "军事": ["军事", "军情", "军武"],
    "科技": ["科技", "互联网", "ai", "人工智能", "数码"],
    "财经": ["财经", "金融", "股票", "经济", "商业"],
}


class NewsRepository:
    """Small sync repository for reading the DeepResearch news database."""

    def __init__(self):
        self.host = os.getenv("NEWS_DB_HOST", "127.0.0.1")
        self.port = int(os.getenv("NEWS_DB_PORT", "3306"))
        self.user = os.getenv("NEWS_DB_USER", "root")
        self.password = os.getenv("NEWS_DB_PASSWORD", "123456")
        self.database = os.getenv("NEWS_DB_NAME", "news_app")

    def _connect(self):
        if pymysql is None:
            raise RuntimeError("当前环境缺少 pymysql，请先安装 pymysql 或在运行新闻后端的环境中启动本助手。")

        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset="utf8mb4",
            cursorclass=DictCursor,
        )

    def _query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        try:
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, params)
                    return list(cursor.fetchall())
        except Exception as exc:
            raise RuntimeError(f"读取新闻数据库失败：{exc}") from exc

    def categories(self) -> list[dict[str, Any]]:
        return self._query(
            """
            SELECT id, name, sort_order
            FROM news_category
            ORDER BY sort_order ASC, id ASC
            """
        )

    def latest(self, limit: int = 10, category: str | None = None) -> list[dict[str, Any]]:
        limit = _clamp_limit(limit)
        category_id = self._resolve_category_id(category) if category else None

        where = "WHERE n.category_id = %s" if category_id else ""
        params: tuple[Any, ...] = (category_id, limit) if category_id else (limit,)

        return self._query(
            f"""
            SELECT n.id, n.title, n.description, n.content, n.image, n.source_url,
                   n.author, n.category_id, n.publish_time, c.name AS category_name
            FROM news n
            LEFT JOIN news_category c ON c.id = n.category_id
            {where}
            ORDER BY n.publish_time DESC, n.id DESC
            LIMIT %s
            """,
            params,
        )

    def latest_by_categories(self, limit_per_category: int = 3) -> OrderedDict[str, list[dict[str, Any]]]:
        limit_per_category = _clamp_limit(limit_per_category, max_value=10)
        result: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
        for category in self.categories():
            if category["name"] not in STANDARD_CATEGORIES:
                continue
            rows = self.latest(limit=limit_per_category, category=category["name"])
            if rows:
                result[category["name"]] = rows
        return result

    def all_news(self, limit: int = 200) -> list[dict[str, Any]]:
        limit = _clamp_limit(limit, max_value=1000)
        return self._query(
            """
            SELECT n.id, n.title, n.description, n.content, n.image, n.source_url,
                   n.author, n.category_id, n.publish_time, c.name AS category_name
            FROM news n
            LEFT JOIN news_category c ON c.id = n.category_id
            ORDER BY n.publish_time DESC, n.id DESC
            LIMIT %s
            """,
            (limit,),
        )

    def detail(self, news_id: int | None = None, title: str | None = None) -> dict[str, Any] | None:
        if news_id:
            rows = self._query(
                """
                SELECT n.id, n.title, n.description, n.content, n.image, n.source_url,
                       n.author, n.category_id, n.publish_time, c.name AS category_name
                FROM news n
                LEFT JOIN news_category c ON c.id = n.category_id
                WHERE n.id = %s
                LIMIT 1
                """,
                (news_id,),
            )
            return rows[0] if rows else None

        if title:
            rows = self.search(title, limit=1)
            return rows[0] if rows else None

        return None

    def search(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        limit = _clamp_limit(limit)
        query = (query or "").strip()
        category = self._infer_category(query)

        if category and _looks_like_category_query(query):
            return self.latest(limit=limit, category=category)

        terms = _extract_terms(query)
        if not terms:
            return self.latest(limit=limit)

        where_parts: list[str] = []
        params: list[Any] = []
        for term in terms:
            like = f"%{term}%"
            where_parts.append("(n.title LIKE %s OR n.description LIKE %s OR n.content LIKE %s)")
            params.extend([like, like, like])

        rows = self._query(
            f"""
            SELECT n.id, n.title, n.description, n.content, n.image, n.source_url,
                   n.author, n.category_id, n.publish_time, c.name AS category_name
            FROM news n
            LEFT JOIN news_category c ON c.id = n.category_id
            WHERE {" OR ".join(where_parts)}
            ORDER BY n.publish_time DESC, n.id DESC
            LIMIT %s
            """,
            tuple(params + [limit]),
        )

        if rows:
            return _sort_by_keyword_score(rows, terms)[:limit]

        if category:
            return self.latest(limit=limit, category=category)

        return self.latest(limit=limit)

    def _resolve_category_id(self, category: str | None) -> int | None:
        if not category:
            return None

        normalized = self._infer_category(category) or category.strip()
        rows = self.categories()
        for row in rows:
            if row["name"] == normalized or str(row["id"]) == normalized:
                return int(row["id"])

        for row in rows:
            if normalized in row["name"] or row["name"] in normalized:
                return int(row["id"])

        return None

    def _infer_category(self, text: str) -> str | None:
        lower_text = (text or "").lower()
        for category, aliases in CATEGORY_ALIASES.items():
            if any(alias.lower() in lower_text for alias in aliases):
                return category
        return None


def format_news_list(rows: list[dict[str, Any]], include_content: bool = False) -> str:
    if not rows:
        return "数据库中暂时没有找到相关新闻。"

    lines = [f"共找到 {len(rows)} 条新闻："]
    for index, row in enumerate(rows, start=1):
        lines.append(_format_single_news(row, index=index, include_content=include_content))
    return "\n\n".join(lines)


def format_news_context(rows: list[dict[str, Any]], include_content: bool = True) -> str:
    if not rows:
        return "数据库中暂时没有找到相关新闻。"

    blocks = []
    for index, row in enumerate(rows, start=1):
        blocks.append(_format_single_news(row, index=index, include_content=include_content))
    return "\n\n".join(blocks)


def _format_single_news(row: dict[str, Any], index: int, include_content: bool) -> str:
    published = row.get("publish_time")
    if hasattr(published, "strftime"):
        published_text = published.strftime("%Y-%m-%d %H:%M")
    else:
        published_text = str(published or "未知时间")

    title = _clean_text(row.get("title"), max_len=200)
    description = _clean_text(row.get("description") or row.get("content"), max_len=220)
    source = _clean_text(row.get("author"), max_len=50) or "未知来源"
    category = _clean_text(row.get("category_name"), max_len=50) or str(row.get("category_id") or "未分类")
    source_url = row.get("source_url") or ""
    image = row.get("image") or ""

    lines = [
        f"{index}. [{category}] {title}",
        f"发布时间：{published_text} | 来源：{source} | 新闻ID：{row.get('id')}",
        f"摘要：{description}",
    ]
    if source_url:
        lines.append(f"原文链接：{source_url}")
    if image:
        lines.append(f"图片：{image}")
    if include_content:
        content = _clean_text(row.get("content") or row.get("description"), max_len=1200)
        lines.append(f"正文：{content}")
    return "\n".join(lines)


def _extract_terms(query: str) -> list[str]:
    query = (query or "").strip()
    if not query:
        return []

    stop_words = {
        "今天",
        "最新",
        "新闻",
        "热点",
        "一下",
        "总结",
        "帮我",
        "看看",
        "有哪些",
        "是什么",
        "为什么",
    }
    terms = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9]{2,}", query)
    cleaned = []
    for term in terms:
        term = term.strip()
        if not term or term in stop_words:
            continue
        for stop_word in stop_words:
            term = term.replace(stop_word, "")
        if len(term) >= 2 and term not in cleaned:
            cleaned.append(term)
    return cleaned[:6]


def _sort_by_keyword_score(rows: list[dict[str, Any]], terms: list[str]) -> list[dict[str, Any]]:
    def score(row: dict[str, Any]) -> int:
        haystack = " ".join(
            str(row.get(field) or "")
            for field in ("title", "description", "content", "author", "category_name")
        ).lower()
        return sum(haystack.count(term.lower()) for term in terms)

    return sorted(rows, key=score, reverse=True)


def _looks_like_category_query(query: str) -> bool:
    return any(word in query for word in ["分类", "列表", "最新", "热点", "新闻", "十条", "10条", "有哪些"])


def _clamp_limit(limit: int | str | None, max_value: int = 20) -> int:
    try:
        value = int(limit or 10)
    except (TypeError, ValueError):
        value = 10
    return max(1, min(value, max_value))


def _clean_text(value: Any, max_len: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "..."
