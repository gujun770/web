import asyncio
import json
import os

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.main_agent_loader import get_react_agent, rebuild_news_vector_store
from utils.response import success_response


router = APIRouter(prefix="/api/ai", tags=["ai"])


class ChatMessage(BaseModel):
    role: str = Field(..., examples=["user", "assistant"])
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="当前用户输入")
    history: list[ChatMessage] = Field(default_factory=list, description="前端传来的历史消息")


def build_agent_query(data: ChatRequest) -> str:
    history = [
        item
        for item in data.history[-8:]
        if item.content and item.role in {"user", "assistant"}
    ]
    if not history:
        return data.message

    lines = ["下面是最近几轮对话，请结合上下文回答最后一个问题。"]
    for item in history:
        role = "用户" if item.role == "user" else "助手"
        lines.append(f"{role}：{item.content[:1000]}")
    lines.append(f"最后一个问题：{data.message}")
    return "\n".join(lines)


def collect_agent_reply(data: ChatRequest) -> str:
    agent = get_react_agent()
    query = build_agent_query(data)
    chunks = list(agent.execute_stream(query))
    return "".join(chunks).strip()


def sse_payload(event: str, data: dict) -> str:
    return f"data: {json.dumps({'event': event, **data}, ensure_ascii=False)}\n\n"


def stream_agent_events(data: ChatRequest):
    try:
        yield sse_payload("start", {"agent": "main-react-news-rag"})
        reply = collect_agent_reply(data)
        if not reply:
            reply = "AI 助手没有生成有效回复，请稍后重试。"
        yield sse_payload("delta", {"content": reply})
        yield sse_payload("done", {"usedFallback": False})
    except Exception as exc:
        yield sse_payload(
            "fallback",
            {
                "content": f"AI 助手调用失败：{exc}",
                "usedFallback": True,
                "message": "main Agent 调用失败",
            },
        )
        yield sse_payload("done", {"usedFallback": True})


@router.get("/status")
async def ai_status():
    return success_response(
        message="AI 配置状态",
        data={
            "agent": "DeepResearch-Agent-Platform/main",
            "rag": "mysql_news_to_chroma",
            "hasDashScopeKey": bool(os.getenv("DASHSCOPE_API_KEY")),
            "hasOpenAIKey": bool(os.getenv("OPENAI_API_KEY")),
            "model": os.getenv("DASHSCOPE_MODEL") or os.getenv("OPENAI_MODEL") or "qwen3-max",
        },
    )


@router.post("/chat")
async def chat(data: ChatRequest):
    try:
        reply = await asyncio.to_thread(collect_agent_reply, data)
        used_fallback = False
        message = "AI 回复成功"
    except Exception as exc:
        reply = f"AI 助手调用失败：{exc}"
        used_fallback = True
        message = "main Agent 调用失败"

    return success_response(
        message=message,
        data={
            "reply": reply,
            "usedFallback": used_fallback,
            "agent": "main-react-news-rag",
        },
    )


@router.post("/chat/stream")
async def chat_stream(data: ChatRequest):
    return StreamingResponse(
        stream_agent_events(data),
        media_type="text/event-stream",
    )


@router.post("/rag/rebuild")
async def rebuild_rag(limit: int = 200):
    try:
        result = await asyncio.to_thread(rebuild_news_vector_store, limit)
        return success_response(message="新闻向量库重建完成", data=result)
    except Exception as exc:
        return success_response(message="新闻向量库重建失败", data={"error": str(exc)})
