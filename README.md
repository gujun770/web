# DeepResearch Agent Platform

这是从 PDF 中复刻的 `DeepResearch 多 Agent 行业深度研究助手` 独立项目。

项目入口：

```text
DeepResearch-Agent-Platform/
  backend/   FastAPI 后端，包含 /api/research/stream SSE 调研接口
  frontend/  Vue3 前端，包含 /research 深度研究页面
```

## 启动后端

```powershell
cd "D:\BaiduNetdiskDownload\Python Web开发：FastAPI从入门到实战\DeepResearch-Agent-Platform\backend"
conda run -n gujun uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## 启动前端

```powershell
cd "D:\BaiduNetdiskDownload\Python Web开发：FastAPI从入门到实战\DeepResearch-Agent-Platform\frontend"
npm.cmd run dev
```

## 访问页面

```text
http://127.0.0.1:5173/research
```

## 已实现能力

- Intent Router：识别行业研究任务
- Planner：拆解研究步骤
- Web Scout：模拟线上检索
- Local Scout：本地知识库召回
- Evidence Judge：证据过滤、去重和来源标注
- Analyst：提炼趋势、机会和风险
- Writer：生成带来源编号的 Markdown 调研报告
- FastAPI + SSE：前端实时展示每个节点状态
