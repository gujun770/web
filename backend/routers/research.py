import asyncio
import json
import time
import uuid
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.main_agent_loader import import_agent_module
from utils.response import success_response


router = APIRouter(prefix="/api/research", tags=["research"])


class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=120, description="研究主题")
    depth: str = Field(default="standard", description="研究深度：quick/standard/deep")
    user_id: str = Field(default="demo-user", description="演示用户 ID")


def research_module():
    return import_agent_module("agent.research_graph")


def sse_event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def run_pipeline(data: ResearchRequest):
    task_id = str(uuid.uuid4())
    module = research_module()

    for event in module.run_research_events(data.topic, data.depth):
        event.setdefault("timestamp", round(time.time(), 3))
        event["taskId"] = task_id
        event["userId"] = data.user_id
        yield sse_event(event)
        await asyncio.sleep(0)


async def collect_pipeline(data: ResearchRequest) -> dict[str, Any]:
    latest: dict[str, Any] = {}
    async for raw_event in run_pipeline(data):
        payload = raw_event.removeprefix("data: ").strip()
        latest = json.loads(payload)
    return latest


@router.post("/stream")
async def stream_research(data: ResearchRequest):
    return StreamingResponse(run_pipeline(data), media_type="text/event-stream")


@router.post("/run")
async def run_research(data: ResearchRequest):
    result = await collect_pipeline(data)
    return success_response(message="DeepResearch 调研完成", data=result)
