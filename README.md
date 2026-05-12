DeepResearch 智能资讯挖掘与分析 Web 系统
一个面向新闻资讯场景的全栈 AI 应用项目，融合热点新闻抓取、新闻分类浏览、新闻详情、收藏历史、新闻 RAG 问答和多 Agent 深度研究报告生成能力。系统后端基于 FastAPI 构建，前端基于 Vue3 实现交互页面，并接入 DashScope/Qwen、LangChain、LangGraph、Chroma、MySQL 和 Redis，支持围绕新闻数据进行检索问答、证据分析和结构化报告生成。

项目亮点
基于 FastAPI 设计新闻、用户、收藏、历史、AI 问答和 DeepResearch 调研接口。
支持 9 个新闻分类热点抓取，抓取后写入 MySQL，并同步更新 Redis 缓存和 Chroma 向量库。
构建新闻 RAG 链路，将 MySQL 中的新闻标题、摘要、正文切块后写入 Chroma，用于语义检索和事实增强问答。
基于 ReAct Agent 封装新闻搜索、分类新闻、新闻详情、热点简报、RAG 总结、日期查询等工具。
基于 LangGraph 编排多 Agent 深度研究流程，实现意图识别、任务规划、新闻召回、证据筛选、分析和报告生成。
使用 SSE 实现 AI 助手流式输出，前端可实时展示模型回答和 Agent 阶段状态。
前端使用 Vue3 + Vite + Pinia + Vant 实现新闻首页、详情页、收藏历史、AI Agent 问答与深度研究页面。
技术栈
后端：

FastAPI
SQLAlchemy Async ORM
MySQL
Redis
Chroma
LangChain
LangGraph
DashScope / Qwen
SSE StreamingResponse
前端：

Vue3
Vite
Pinia
Vue Router
Vant
Axios
Fetch Stream / SSE
项目结构
DeepResearch-Agent-Platform/
  backend/                 FastAPI 后端服务
    routers/               API 路由
    crud/                  数据库访问逻辑
    models/                ORM 模型
    schemas/               Pydantic 数据模型
    services/              新闻抓取、LLM、Agent 加载等服务
    cache/                 Redis 缓存封装
    config/                数据库和缓存配置

  frontend/                Vue3 前端项目
    src/views/             页面视图
    src/components/        通用组件
    src/store/             Pinia 状态管理
    src/router/            前端路由

  main/                    新闻 Agent / RAG / LangGraph 核心模块
    agent/                 ReAct Agent 与 DeepResearch 工作流
    rag/                   MySQL 检索、Chroma 向量库、RAG 总结
    model/                 大模型与 Embedding 初始化
    prompts/               场景化提示词
    config/                Agent、RAG、Chroma 配置
核心功能
新闻资讯
新闻分类浏览
新闻列表分页
新闻详情查看
新闻图片代理与质量过滤
收藏新闻
浏览历史
今日热点抓取
抓取后替换数据库旧新闻
抓取后同步 Redis 缓存和 Chroma 向量库
AI 新闻助手
普通新闻问答
基于新闻数据库的 RAG 总结
按分类查询新闻
查询最新热点
查询新闻详情
生成热点简报
支持 SSE 流式输出
DeepResearch 多 Agent 研究
DeepResearch 工作流使用 LangGraph 编排，主要节点包括：

Intent Router
  -> Planner Agent
  -> Retriever Agent
  -> Evidence Judge Agent
  -> Analyst Agent
  -> Writer Agent
执行流程：

用户输入研究主题
-> 判断任务意图
-> 拆解研究步骤
-> 从 Chroma / MySQL 召回相关新闻
-> 对证据去重、评分和筛选
-> 提炼趋势、机会和风险
-> 生成 Markdown 深度研究报告
-> 通过 SSE 推送阶段状态和最终报告
核心接口
新闻接口
GET  /api/news/categories
GET  /api/news/list?categoryId=1&page=1&pageSize=10
GET  /api/news/detail?id=1
GET  /api/news/hot?limit=10
GET  /api/news/image?url=...
POST /api/news/fetch-hot?categoryId=0&limit=10&replace=true&useAi=false
AI 助手接口
GET  /api/ai/status
POST /api/ai/chat
POST /api/ai/chat/stream
POST /api/ai/rag/rebuild?limit=200
/api/ai/chat/stream 使用 SSE 返回：

data: {"event":"start","agent":"main-react-news-rag"}
data: {"event":"delta","content":"模型生成内容"}
data: {"event":"done","usedFallback":false}
DeepResearch 接口
POST /api/research/stream
POST /api/research/run
请求示例：

{
  "topic": "人工智能相关新闻的行业影响分析",
  "depth": "standard",
  "user_id": "demo-user"
}
用户、收藏、历史接口
POST   /api/user/register
POST   /api/user/login
GET    /api/user/info
PUT    /api/user/update
PUT    /api/user/password

GET    /api/favorite/check?newsId=1
POST   /api/favorite/add
DELETE /api/favorite/remove?newsId=1
GET    /api/favorite/list?page=1&pageSize=10
DELETE /api/favorite/clear

POST   /api/history/add
GET    /api/history/list?page=1&pageSize=10
DELETE /api/history/delete/{historyId}
DELETE /api/history/clear
本地运行
1. 后端启动
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
后端默认地址：

http://127.0.0.1:8000
2. 前端启动
cd frontend
npm install
npm run dev
前端默认地址：

http://127.0.0.1:5173
环境配置
项目需要本地 MySQL、Redis，以及可用的大模型 API Key。

常用环境变量示例：

DASHSCOPE_API_KEY=your_dashscope_api_key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_MODEL=qwen3-max

NEWS_DB_HOST=127.0.0.1
NEWS_DB_PORT=3306
NEWS_DB_USER=root
NEWS_DB_PASSWORD=your_mysql_password
NEWS_DB_NAME=news_app

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
说明：

真实 API Key 和数据库密码请放在本地环境变量或 .env 文件中。
.env、日志、依赖目录、Chroma 本地数据库不应提交到 GitHub。
如果使用本地 MySQL，需要提前创建 news_app 数据库。
前端交互链路
普通新闻数据使用 Axios 调用 REST API：

页面加载
-> 请求新闻分类
-> 请求新闻列表
-> 更新 Pinia 状态
-> Vue 自动渲染页面
AI 助手使用 Fetch 建立 SSE 流式连接：

用户发送问题
-> 前端 POST /api/ai/chat/stream
-> 后端持续推送 start / delta / done 事件
-> 前端按 data: 解析事件
-> 将 delta 内容追加到响应式变量
-> 页面实时显示打字机式回答
DeepResearch 页面会实时展示每个 Agent 节点的执行状态、召回证据和最终 Markdown 报告。

项目定位
该项目主要展示一个后端主导的 AI 应用系统如何从传统新闻资讯业务扩展到 RAG 问答和多 Agent 深度分析场景。核心难点不在单纯页面展示，而在新闻数据抓取与清洗、数据库与向量库同步、Agent 工具封装、LangGraph 工作流编排和 SSE 流式交互。
