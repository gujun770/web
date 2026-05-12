from __future__ import annotations

import re
import time
from functools import lru_cache
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from ..model.factory import chat_model
from ..rag.news_repository import NewsRepository
from ..rag.vector_store import VectorStore
from ..utils.logger_handler import logger


class ResearchState(TypedDict, total=False):
    topic: str
    depth: str
    intent: str
    plan: list[str]
    candidates: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    analysis: dict[str, list[str]]
    report: str
    retrieval_source: str
    errors: list[str]


STOP_WORDS = {
    "新闻",
    "热点",
    "分析",
    "研究",
    "报告",
    "总结",
    "一下",
    "帮我",
    "看看",
    "生成",
    "今日",
    "最新",
}


def intent_router(state: ResearchState) -> ResearchState:
    topic = state["topic"]
    research_words = ("研究", "报告", "研报", "深度", "行业", "趋势", "影响", "分析")
    intent = "deep_research" if any(word in topic for word in research_words) else "news_analysis"
    return {"intent": intent}


def planner_agent(state: ResearchState) -> ResearchState:
    topic = state["topic"]
    depth = state.get("depth", "standard")
    plan = [
        f"界定「{topic}」的研究范围和核心问题",
        "从新闻向量库和新闻数据库召回相关资料",
        "对召回内容进行相关性评分、去重和来源整理",
        "提炼关键事实、趋势、机会和风险",
        "生成带新闻来源编号的结构化 Markdown 报告",
    ]
    if depth == "deep":
        plan.insert(3, "检查证据覆盖是否不足，必要时扩大数据库检索范围")
    elif depth == "quick":
        plan = [plan[0], plan[1], plan[-1]]
    return {"plan": plan}


def retriever_agent(state: ResearchState) -> ResearchState:
    topic = state["topic"]
    depth = state.get("depth", "standard")
    limit = {"quick": 6, "standard": 10, "deep": 14}.get(depth, 10)
    errors: list[str] = []

    try:
        vector_store = VectorStore()
        if vector_store.has_index():
            docs = vector_store.search(topic, k=limit)
            candidates = [_document_to_evidence(doc, index) for index, doc in enumerate(docs, start=1)]
            if candidates:
                return {"candidates": candidates, "retrieval_source": "chroma", "errors": errors}
        else:
            errors.append("Chroma 向量库尚未构建，已降级为 MySQL 检索。")
    except Exception as exc:
        errors.append(f"Chroma 检索失败，已降级为 MySQL 检索：{exc}")
        logger.warning(errors[-1])

    repository = NewsRepository()
    try:
        rows = repository.search(topic, limit=limit)
        candidates = [_row_to_evidence(row, index) for index, row in enumerate(rows, start=1)]
        return {"candidates": candidates, "retrieval_source": "mysql", "errors": errors}
    except Exception as exc:
        errors.append(f"MySQL 新闻检索失败：{exc}")
        logger.error(errors[-1], exc_info=True)
        return {"candidates": [], "retrieval_source": "none", "errors": errors}


def evidence_judge_agent(state: ResearchState) -> ResearchState:
    topic_terms = tokenize(state["topic"])
    seen: set[str] = set()
    judged: list[dict[str, Any]] = []

    for item in state.get("candidates", []):
        key = item.get("url") or item.get("title") or item.get("id")
        if not key or key in seen:
            continue
        seen.add(key)

        text = f"{item.get('title', '')} {item.get('content', '')} {item.get('category', '')}"
        score = score_text(topic_terms, text) + int(item.get("score", 0))
        if score <= 0 and judged:
            continue

        judged.append(
            {
                **item,
                "score": score or 1,
                "reason": "标题、正文或分类与研究主题存在相关性，可作为报告证据。",
            }
        )

    judged.sort(key=lambda row: row["score"], reverse=True)
    return {"evidence": judged[:8]}


def analyst_agent(state: ResearchState) -> ResearchState:
    evidence = state.get("evidence", [])
    topic = state["topic"]
    refs = "、".join(f"[{item['id']}]" for item in evidence[:4]) or "当前证据"
    categories = sorted({item.get("category") for item in evidence if item.get("category")})

    analysis = {
        "conclusions": [
            f"围绕「{topic}」共筛选出 {len(evidence)} 条可追溯新闻证据，主要来源于 {state.get('retrieval_source', 'news')} 检索。",
            f"现有证据集中在 {('、'.join(categories) if categories else '新闻热点')} 方向，核心判断应以 {refs} 为依据。",
        ],
        "trends": [
            "相关事件呈现跨来源、跨分类的讨论特征，适合用结构化方式梳理背景、进展和影响。",
            "如果后续新闻继续更新，报告结论应随 Chroma 向量库和 MySQL 新闻库同步刷新。",
        ],
        "risks": [
            "当前证据只覆盖已入库新闻，不能代表全网信息。",
            "若某些分类新闻数量不足，报告应明确说明证据覆盖有限。",
        ],
    }
    return {"analysis": analysis}


def writer_agent(state: ResearchState) -> ResearchState:
    evidence = state.get("evidence", [])
    if not evidence:
        return {
            "report": (
                f"# {state['topic']} 深度研究报告\n\n"
                "当前新闻数据库和向量库中没有检索到足够证据，暂时无法生成可靠报告。"
            )
        }

    prompt = build_writer_prompt(state)
    try:
        response = chat_model.invoke([HumanMessage(content=prompt)])
        content = getattr(response, "content", "") or ""
        if content.strip():
            return {"report": content.strip()}
    except Exception as exc:
        logger.warning(f"[research writer] LLM report failed, fallback to local writer: {exc}")

    return {"report": build_local_report(state)}


@lru_cache(maxsize=1)
def get_research_graph():
    graph = StateGraph(ResearchState)
    graph.add_node("intent_router", intent_router)
    graph.add_node("planner", planner_agent)
    graph.add_node("retriever", retriever_agent)
    graph.add_node("evidence_judge", evidence_judge_agent)
    graph.add_node("analyst", analyst_agent)
    graph.add_node("writer", writer_agent)

    graph.add_edge(START, "intent_router")
    graph.add_edge("intent_router", "planner")
    graph.add_edge("planner", "retriever")
    graph.add_edge("retriever", "evidence_judge")
    graph.add_edge("evidence_judge", "analyst")
    graph.add_edge("analyst", "writer")
    graph.add_edge("writer", END)
    return graph.compile()


def run_research_events(topic: str, depth: str = "standard"):
    initial_state: ResearchState = {
        "topic": normalize_topic(topic),
        "depth": depth if depth in {"quick", "standard", "deep"} else "standard",
        "errors": [],
    }
    yield {
        "event": "start",
        "timestamp": round(time.time(), 3),
        "key": "start",
        "title": "Start",
        "status": "done",
        "topic": initial_state["topic"],
        "message": "DeepResearch LangGraph 任务已创建",
    }

    state_snapshot: ResearchState = dict(initial_state)
    for update in get_research_graph().stream(initial_state, stream_mode="updates"):
        for node_name, node_update in update.items():
            state_snapshot.update(node_update)
            yield build_stage_event(node_name, state_snapshot, node_update)


def run_research(topic: str, depth: str = "standard") -> ResearchState:
    state: ResearchState = {
        "topic": normalize_topic(topic),
        "depth": depth if depth in {"quick", "standard", "deep"} else "standard",
        "errors": [],
    }
    return get_research_graph().invoke(state)


def build_stage_event(node_name: str, state: ResearchState, node_update: ResearchState) -> dict[str, Any]:
    mapping = {
        "intent_router": ("intent", "Intent Router", f"识别为 {state.get('intent', 'news_analysis')} 任务"),
        "planner": ("planner", "Planner Agent", "已拆解研究步骤"),
        "retriever": (
            "retriever",
            "Retriever Agent",
            f"已从 {state.get('retrieval_source', 'news')} 召回 {len(state.get('candidates', []))} 条候选证据",
        ),
        "evidence_judge": (
            "evidence_judge",
            "Evidence Judge Agent",
            f"已筛选 {len(state.get('evidence', []))} 条可追溯证据",
        ),
        "analyst": ("analyst", "Analyst Agent", "已形成趋势、机会与风险判断"),
        "writer": ("writer", "Writer Agent", "已生成 Markdown 深度研究报告"),
    }
    key, title, message = mapping[node_name]
    event_name = "finish" if node_name == "writer" else "stage"
    return {
        "event": event_name,
        "timestamp": round(time.time(), 3),
        "key": key,
        "title": title,
        "status": "done",
        "message": message,
        "intent": state.get("intent"),
        "items": node_update.get("plan"),
        "evidence": node_update.get("evidence") or node_update.get("candidates"),
        "analysis": node_update.get("analysis"),
        "report": node_update.get("report"),
        "errors": state.get("errors", []),
    }


def build_writer_prompt(state: ResearchState) -> str:
    evidence_text = format_evidence_for_prompt(state.get("evidence", []))
    analysis = state.get("analysis", {})
    return f"""你是中文新闻深度研究报告助手。请严格基于证据写一份 Markdown 报告。

研究主题：{state['topic']}
研究深度：{state.get('depth', 'standard')}

分析要点：
{analysis}

证据材料：
{evidence_text}

要求：
1. 不要编造证据之外的新闻事实。
2. 关键结论后标注来源编号，例如 [N1]。
3. 输出结构包含：核心结论、证据分析、趋势判断、风险提示、后续关注。
4. 全文中文。"""


def build_local_report(state: ResearchState) -> str:
    topic = state["topic"]
    plan = state.get("plan", [])
    evidence = state.get("evidence", [])
    analysis = state.get("analysis", {})

    evidence_lines = "\n".join(
        f"- [{item['id']}] {item['title']}（{item.get('source') or '未知来源'}，{item.get('publish_time') or '未知时间'}）：{item.get('url') or '无链接'}"
        for item in evidence
    )
    plan_lines = "\n".join(f"{index}. {step}" for index, step in enumerate(plan, start=1))
    conclusion_lines = "\n".join(f"- {item}" for item in analysis.get("conclusions", []))
    trend_lines = "\n".join(f"- {item}" for item in analysis.get("trends", []))
    risk_lines = "\n".join(f"- {item}" for item in analysis.get("risks", []))

    return f"""# {topic} 深度研究报告

## 一、研究路径
{plan_lines}

## 二、核心结论
{conclusion_lines}

## 三、证据分析
{build_evidence_summary(evidence)}

## 四、趋势判断
{trend_lines}

## 五、风险提示
{risk_lines}

## 六、来源追踪
{evidence_lines}
"""


def build_evidence_summary(evidence: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"- [{item['id']}] {item['title']}：{shorten(item.get('content', ''), 120)}"
        for item in evidence
    )


def format_evidence_for_prompt(evidence: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        "\n".join(
            [
                f"编号：{item['id']}",
                f"标题：{item.get('title')}",
                f"分类：{item.get('category')}",
                f"来源：{item.get('source')}",
                f"发布时间：{item.get('publish_time')}",
                f"链接：{item.get('url')}",
                f"内容：{item.get('content')}",
            ]
        )
        for item in evidence
    )


def _document_to_evidence(doc, index: int) -> dict[str, Any]:
    metadata = doc.metadata or {}
    return {
        "id": f"N{index}",
        "newsId": metadata.get("news_id"),
        "title": metadata.get("title") or "未命名新闻",
        "source": metadata.get("author") or "新闻库",
        "url": metadata.get("source_url") or "",
        "content": shorten(doc.page_content, 500),
        "category": metadata.get("category_name") or metadata.get("category_id") or "",
        "publish_time": metadata.get("publish_time") or "",
        "score": 2,
    }


def _row_to_evidence(row: dict[str, Any], index: int) -> dict[str, Any]:
    published = row.get("publish_time")
    if hasattr(published, "strftime"):
        published = published.strftime("%Y-%m-%d %H:%M")
    return {
        "id": f"N{index}",
        "newsId": row.get("id"),
        "title": row.get("title") or "未命名新闻",
        "source": row.get("author") or "新闻库",
        "url": row.get("source_url") or "",
        "content": shorten(row.get("content") or row.get("description") or "", 500),
        "category": row.get("category_name") or row.get("category_id") or "",
        "publish_time": str(published or ""),
        "score": 1,
    }


def tokenize(text: str) -> set[str]:
    text = text or ""
    ascii_tokens = set(re.findall(r"[a-zA-Z0-9]{2,}", text.lower()))
    chinese_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}", text))
    compact = "".join(ch for ch in text if "\u4e00" <= ch <= "\u9fff")
    bigrams = {compact[i : i + 2] for i in range(max(0, len(compact) - 1))}
    return {token for token in ascii_tokens | chinese_tokens | bigrams if token not in STOP_WORDS}


def score_text(topic_terms: set[str], text: str) -> int:
    haystack = text.lower()
    return sum(1 for term in topic_terms if term.lower() in haystack)


def normalize_topic(topic: str) -> str:
    return re.sub(r"\s+", " ", topic or "").strip()


def shorten(text: str, max_len: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "..."
