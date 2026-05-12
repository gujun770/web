import asyncio
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-plus"


class LLMConfigError(RuntimeError):
    pass


def get_api_key() -> str:
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise LLMConfigError("缺少 DASHSCOPE_API_KEY 或 OPENAI_API_KEY 环境变量")
    return api_key


def get_model() -> str:
    return os.getenv("DASHSCOPE_MODEL") or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL


def build_client() -> OpenAI:
    return OpenAI(
        api_key=get_api_key(),
        base_url=os.getenv("DASHSCOPE_BASE_URL") or DASHSCOPE_BASE_URL,
    )


def call_chat_completion_sync(messages: list[dict[str, str]], temperature: float = 0.35) -> str:
    client = build_client()
    completion = client.chat.completions.create(
        model=get_model(),
        messages=messages,
        temperature=temperature,
    )
    return completion.choices[0].message.content or ""


def stream_chat_completion_sync(messages: list[dict[str, str]], temperature: float = 0.35):
    client = build_client()
    stream = client.chat.completions.create(
        model=get_model(),
        messages=messages,
        temperature=temperature,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta
        content = getattr(delta, "content", None)
        if content:
            yield content


async def call_chat_completion(messages: list[dict[str, str]], temperature: float = 0.35) -> str:
    return await asyncio.to_thread(call_chat_completion_sync, messages, temperature)


def news_to_context(latest_news: list[Any], limit: int = 8) -> str:
    if not latest_news:
        return "当前新闻库为空。"

    lines = []
    for index, item in enumerate(latest_news[:limit], start=1):
        title = getattr(item, "title", "")
        description = getattr(item, "description", "") or ""
        author = getattr(item, "author", "") or "未知来源"
        views = getattr(item, "views", 0)
        publish_time = getattr(item, "publish_time", "")
        content = getattr(item, "content", "") or ""
        snippet = description or content[:180]
        lines.append(
            f"{index}. 标题：{title}\n"
            f"   来源：{author}；热度：{views}；发布时间：{publish_time}\n"
            f"   摘要：{snippet}"
        )
    return "\n".join(lines)


def normalize_history(history: list[Any], max_items: int = 8) -> list[dict[str, str]]:
    normalized = []
    for item in history[-max_items:]:
        role = getattr(item, "role", "user")
        content = getattr(item, "content", "")
        if role not in {"user", "assistant"}:
            continue
        if content:
            normalized.append({"role": role, "content": content[:1200]})
    return normalized
