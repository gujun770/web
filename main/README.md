# 新闻项目 main Agent

这个目录保留了你原来 `pythonProject17/main` 的 Agent/RAG 分层习惯，但已经改为新闻项目使用。

现在它不是 Streamlit 前端，实际入口在：

- `backend/routers/ai.py`
- `/api/ai/chat`
- `/api/ai/chat/stream`

当前 RAG 方式：

- MySQL 的 `news` / `news_category` 表保存新闻原文。
- `main/rag/vector_store.py` 把新闻标题、摘要、正文切块写入 Chroma。
- `main/rag/rag_service.py` 优先从 Chroma 做语义检索，再把检索片段交给大模型总结。
- 如果 Chroma 检索或 embedding 失败，会兜底走数据库关键词检索。

新闻更新链路：

1. 前端点击“抓取今日热点”。
2. `backend/routers/news.py` 抓取 9 个分类新闻。
3. ORM 写入 MySQL。
4. 提交事务后清理 Redis 新闻缓存。
5. 同步重建 Chroma 向量库。

默认数据库连接环境变量：

- `NEWS_DB_HOST=127.0.0.1`
- `NEWS_DB_PORT=3306`
- `NEWS_DB_USER=root`
- `NEWS_DB_PASSWORD=123456`
- `NEWS_DB_NAME=news_app`
