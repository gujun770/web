from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from .news_repository import NewsRepository, format_news_context, format_news_list
from .vector_store import VectorStore
from ..model.factory import chat_model
from ..utils.logger_handler import logger
from ..utils.prompt_loader import load_rag_prompts


class RagSummarizeService:
    def __init__(self):
        self.repository = NewsRepository()
        self.vector_store = VectorStore()
        self.prompt_text = load_rag_prompts()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self._init_chain()

    def _init_chain(self):
        return self.prompt_template | self.model | StrOutputParser()

    def rag_summarize(self, query: str) -> str:
        rows = []
        try:
            docs = self.vector_store.search(query, k=8) if self.vector_store.has_index() else []
            if docs:
                context = self.vector_store.format_documents(docs)
                return self.chain.invoke({"input": query, "context": context})
        except Exception as exc:
            logger.warning(f"[RagSummarizeService] vector search failed, fallback to DB search: {exc}")

        rows = self.repository.search(query=query, limit=8)
        if not rows:
            return "数据库中暂时没有找到与该问题相关的新闻。"

        context = format_news_context(rows, include_content=True)
        try:
            return self.chain.invoke(
                {
                    "input": query,
                    "context": context,
                }
            )
        except Exception as exc:
            logger.error(f"[RagSummarizeService] model summarize failed: {exc}", exc_info=True)
            return (
                "已检索到相关新闻，但调用大模型总结失败。下面是数据库中的原始检索结果：\n\n"
                + format_news_list(rows, include_content=True)
            )


if __name__ == "__main__":
    service = RagSummarizeService()
    print(service.rag_summarize("总结一下今天的科技新闻"))
