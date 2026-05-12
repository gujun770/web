from datetime import datetime

from langchain_core.tools import tool

from ...rag.news_repository import NewsRepository, format_news_context, format_news_list
from ...rag.rag_service import RagSummarizeService
from ...utils.logger_handler import logger


@tool(description="根据用户问题从新闻数据库中检索相关新闻，并调用大模型生成中文总结。入参 query 为用户问题或检索词。")
def rag_summarize(query: str) -> str:
    rag = RagSummarizeService()
    return rag.rag_summarize(query)


@tool(description="从新闻数据库中搜索相关新闻。入参 query 为中文关键词或问题，返回匹配新闻列表。")
def search_news(query: str, limit: int = 8) -> str:
    repository = NewsRepository()
    rows = repository.search(query=query, limit=limit)
    return format_news_list(rows, include_content=False)


@tool(description="获取数据库中最新新闻。limit 默认为 10，适合用户询问最新热点、今日新闻、热门新闻。")
def get_latest_news(limit: int = 10) -> str:
    repository = NewsRepository()
    rows = repository.latest(limit=limit)
    return format_news_list(rows, include_content=False)


@tool(description="按分类获取新闻。category 支持头条、推荐、社会、国内、国际、娱乐、体育、军事、科技、财经等中文分类名。")
def get_category_news(category: str, limit: int = 10) -> str:
    repository = NewsRepository()
    rows = repository.latest(category=category, limit=limit)
    return format_news_list(rows, include_content=False)


@tool(description="获取单条新闻详情。可传入 news_id；如果没有 id，可传入 title 用标题模糊匹配。")
def get_news_detail(news_id: int | None = None, title: str | None = None) -> str:
    repository = NewsRepository()
    row = repository.detail(news_id=news_id, title=title)
    if not row:
        return "没有在数据库中找到对应新闻详情。"
    return format_news_context([row], include_content=True)


@tool(description="生成九个新闻分类的热点摘要素材，每个分类返回若干条新闻，适合生成日报、行业简报、今日热点概览。")
def build_hot_news_brief(limit_per_category: int = 3) -> str:
    repository = NewsRepository()
    groups = repository.latest_by_categories(limit_per_category=limit_per_category)
    if not groups:
        return "数据库中暂时没有可用于生成热点摘要的新闻。"

    parts: list[str] = []
    for category_name, rows in groups.items():
        parts.append(f"## {category_name}")
        parts.append(format_news_list(rows, include_content=False))
    return "\n\n".join(parts)


@tool(description="获取当前日期时间，返回中文格式字符串。")
def get_current_date() -> str:
    return datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")


@tool(description="无入参。用户明确要求生成新闻深度报告、热点日报、行业研究报告时先调用本工具，用于切换报告型提示词。")
def fill_context_for_report() -> str:
    logger.info("[fill_context_for_report] switched to news report prompt")
    return "已切换为新闻报告生成模式。"
