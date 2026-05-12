from langchain.agents import create_agent

from .tools.agent_tools import (
    build_hot_news_brief,
    fill_context_for_report,
    get_category_news,
    get_current_date,
    get_latest_news,
    get_news_detail,
    rag_summarize,
    search_news,
)
from .tools.middleware import log_before_model, monitor_tool, report_prompt_switch
from ..model.factory import chat_model
from ..utils.prompt_loader import load_system_prompts


class ReactAgent:
    def __init__(self):
        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompts(),
            tools=[
                rag_summarize,
                search_news,
                get_latest_news,
                get_category_news,
                get_news_detail,
                build_hot_news_brief,
                get_current_date,
                fill_context_for_report,
            ],
            middleware=[monitor_tool, log_before_model, report_prompt_switch],
        )

    def execute_stream(self, query: str):
        input_dict = {"messages": [{"role": "user", "content": query}]}
        last_content = ""

        try:
            stream = self.agent.stream(
                input_dict,
                stream_mode="values",
                context={"report": False},
            )
            for chunk in stream:
                latest_message = chunk["messages"][-1]
                if getattr(latest_message, "type", None) != "ai":
                    continue

                content = (latest_message.content or "").strip()
                if not content or content == last_content:
                    continue

                if content.startswith(last_content):
                    delta = content[len(last_content):]
                else:
                    delta = content

                last_content = content
                if delta.strip():
                    yield delta
        except Exception as exc:
            yield (
                "大模型调用失败，新闻数据库工具本身已可用。请确认网络能访问阿里云百炼，"
                f"并且 DASHSCOPE_API_KEY 已在当前终端环境中生效。\n\n错误信息：{exc}"
            )
