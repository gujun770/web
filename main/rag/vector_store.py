from __future__ import annotations

import os
import shutil
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..model.factory import embed_model
from ..utils.config_handler import chroma_conf
from ..utils.logger_handler import logger
from ..utils.path_tool import get_abs_path
from .news_repository import NewsRepository


class VectorStore:
    def __init__(self):
        self.collection_name = chroma_conf["collection_name"]
        self.persist_directory = get_abs_path(chroma_conf["persist_directory"])
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf["chunk_size"],
            chunk_overlap=chroma_conf["chunk_overlap"],
            separators=chroma_conf["separators"],
            length_function=len,
        )

    def _store(self) -> Chroma:
        os.makedirs(self.persist_directory, exist_ok=True)
        return Chroma(
            collection_name=self.collection_name,
            embedding_function=embed_model,
            persist_directory=self.persist_directory,
        )

    def search(self, query: str, k: int = 8) -> list[Document]:
        store = self._store()
        return store.similarity_search(query, k=k)

    def has_index(self) -> bool:
        try:
            return self._store()._collection.count() > 0
        except Exception:
            return False

    def rebuild_from_database(self, limit: int = 200) -> dict[str, int]:
        repository = NewsRepository()
        return self.rebuild_from_rows(repository.all_news(limit=limit))

    def rebuild_from_rows(self, rows: list[Any]) -> dict[str, int]:
        if os.path.exists(self.persist_directory):
            shutil.rmtree(self.persist_directory, ignore_errors=True)

        documents = self._rows_to_documents(rows)
        if not documents:
            return {"news": 0, "chunks": 0}

        chunks = self.text_splitter.split_documents(documents)
        ids = [
            f"news-{chunk.metadata.get('news_id')}-chunk-{index}"
            for index, chunk in enumerate(chunks)
        ]
        store = self._store()
        store.add_documents(chunks, ids=ids)
        logger.info(f"[VectorStore] synced {len(documents)} news rows into {len(chunks)} chunks")
        return {"news": len(documents), "chunks": len(chunks)}

    def format_documents(self, docs: list[Document]) -> str:
        blocks: list[str] = []
        for index, doc in enumerate(docs, start=1):
            metadata = doc.metadata
            blocks.append(
                "\n".join(
                    [
                        f"【参考新闻{index}】",
                        f"新闻ID：{metadata.get('news_id')}",
                        f"标题：{metadata.get('title')}",
                        f"分类：{metadata.get('category_name') or metadata.get('category_id')}",
                        f"来源：{metadata.get('author')}",
                        f"发布时间：{metadata.get('publish_time')}",
                        f"原文链接：{metadata.get('source_url')}",
                        f"内容片段：{doc.page_content}",
                    ]
                )
            )
        return "\n\n".join(blocks)

    def _rows_to_documents(self, rows: list[Any]) -> list[Document]:
        documents: list[Document] = []
        for row in rows:
            data = _as_dict(row)
            news_id = data.get("id")
            title = data.get("title") or ""
            description = data.get("description") or ""
            content = data.get("content") or ""
            if not news_id or not (title or description or content):
                continue

            page_content = "\n".join(
                [
                    f"标题：{title}",
                    f"摘要：{description}",
                    f"正文：{content}",
                ]
            ).strip()
            published = data.get("publish_time")
            if hasattr(published, "strftime"):
                published = published.strftime("%Y-%m-%d %H:%M:%S")

            documents.append(
                Document(
                    page_content=page_content,
                    metadata={
                        "news_id": str(news_id),
                        "title": title[:200],
                        "category_id": str(data.get("category_id") or ""),
                        "category_name": data.get("category_name") or "",
                        "author": data.get("author") or "",
                        "publish_time": str(published or ""),
                        "source_url": data.get("source_url") or "",
                        "image": data.get("image") or "",
                    },
                )
            )
        return documents


def rebuild_news_vector_store(limit: int = 200) -> dict[str, int]:
    return VectorStore().rebuild_from_database(limit=limit)


def _as_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    return {
        "id": getattr(row, "id", None),
        "title": getattr(row, "title", None),
        "description": getattr(row, "description", None),
        "content": getattr(row, "content", None),
        "image": getattr(row, "image", None),
        "source_url": getattr(row, "source_url", None),
        "author": getattr(row, "author", None),
        "category_id": getattr(row, "category_id", None),
        "category_name": getattr(row, "category_name", None),
        "publish_time": getattr(row, "publish_time", None),
    }
