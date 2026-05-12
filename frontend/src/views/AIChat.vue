<template>
  <div class="agent-page">
    <tab-bar />

    <main class="agent-shell">
      <section class="agent-intro">
        <div>
          <p class="eyebrow">News Agent Assistant</p>
          <h1>新闻 RAG 问答与多 Agent 深度研究助手</h1>
          <p>同一个入口支持新闻问答、热点总结、证据分析和结构化研究报告生成。</p>
        </div>
        <div class="mode-switch" aria-label="Agent 模式">
          <button :class="{ active: activeMode === 'chat' }" @click="activeMode = 'chat'">新闻问答</button>
          <button :class="{ active: activeMode === 'research' }" @click="activeMode = 'research'">深度研究</button>
        </div>
      </section>

      <section v-if="activeMode === 'chat'" class="chat-layout">
        <div class="chat-card">
          <div ref="messagesContainer" class="messages-container">
            <div
              v-for="(message, index) in messages"
              :key="index"
              :class="['message', message.role === 'user' ? 'user-message' : 'ai-message']"
            >
              <div class="message-content">
                <div v-html="formatMarkdown(message.content)"></div>
              </div>
            </div>
            <div v-if="isLoading && !isStreaming" class="message ai-message">
              <div class="message-content">正在分析新闻库...</div>
            </div>
          </div>

          <div class="input-container">
            <van-field
              v-model="userInput"
              rows="1"
              autosize
              type="textarea"
              placeholder="问我新闻摘要、热点分析、分类新闻或事件影响..."
              class="chat-input"
              @keypress.enter.prevent="sendMessage"
            />
            <van-button
              type="primary"
              class="send-button"
              :disabled="isLoading || !userInput.trim()"
              @click="sendMessage"
            >
              发送
            </van-button>
          </div>
        </div>

        <aside class="prompt-panel">
          <div class="panel-title">可尝试的问题</div>
          <button @click="fillPrompt('帮我总结今天的科技新闻重点')">总结科技新闻</button>
          <button @click="fillPrompt('分析今天财经新闻可能带来的影响')">财经影响分析</button>
          <button @click="fillPrompt('生成一份今日资讯简报')">今日资讯简报</button>
          <button @click="switchToResearch('人工智能相关新闻的行业影响分析')">进入深度研究</button>
        </aside>
      </section>

      <section v-else class="research-area">
        <div class="research-control">
          <van-field
            v-model="topic"
            class="topic-input"
            rows="2"
            autosize
            type="textarea"
            placeholder="输入研究主题，例如：人工智能相关新闻的行业影响分析"
          />
          <div class="depth-control" aria-label="研究深度">
            <button
              v-for="option in depthOptions"
              :key="option.value"
              :class="{ active: depth === option.value }"
              @click="depth = option.value"
            >
              {{ option.label }}
            </button>
          </div>
          <van-button
            type="primary"
            class="run-button"
            :loading="isRunning"
            :disabled="!topic.trim() || isRunning"
            @click="startResearch"
          >
            开始研究
          </van-button>
        </div>

        <div class="research-grid">
          <aside class="stage-panel">
            <div class="section-heading">
              <span>执行链路</span>
              <small>{{ currentMessage }}</small>
            </div>
            <div class="stage-list">
              <article
                v-for="stage in stages"
                :key="stage.key"
                :class="['stage-item', stage.status]"
              >
                <div class="stage-dot"></div>
                <div>
                  <h3>{{ stage.title }}</h3>
                  <p>{{ stage.message || stage.description }}</p>
                  <ul v-if="stage.items?.length">
                    <li v-for="item in stage.items" :key="item">{{ item }}</li>
                  </ul>
                </div>
              </article>
            </div>
          </aside>

          <section class="report-panel">
            <div class="section-heading">
              <span>研究报告</span>
              <small v-if="taskId">任务 {{ taskId.slice(0, 8) }}</small>
            </div>
            <div v-if="report" class="report-content" v-html="formatMarkdown(report)"></div>
            <div v-else class="empty-state">输入主题后开始研究，报告会在 Writer Agent 节点完成后生成。</div>
          </section>

          <aside class="evidence-panel">
            <div class="section-heading">
              <span>证据来源</span>
              <small>{{ evidence.length }} 条</small>
            </div>
            <article v-for="item in evidence" :key="item.id" class="evidence-item">
              <div class="evidence-id">{{ item.id }}</div>
              <div>
                <h3>{{ item.title }}</h3>
                <p>{{ item.content }}</p>
                <span>{{ item.source }} · score {{ item.score }}</span>
              </div>
            </article>
            <div v-if="!evidence.length" class="empty-state compact">
              证据会随 Retriever Agent 和 Evidence Judge 阶段逐步出现。
            </div>
          </aside>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { showToast } from 'vant'
import TabBar from '../components/TabBar.vue'
import { apiConfig } from '../config/api'

const activeMode = ref('chat')

const messages = ref([
  {
    role: 'assistant',
    content: '你好，我是新闻 Agent 助手。你可以让我做新闻问答、热点总结，也可以切换到深度研究生成带证据来源的报告。'
  }
])
const userInput = ref('')
const isLoading = ref(false)
const isStreaming = ref(false)
const messagesContainer = ref(null)

const defaultStages = [
  { key: 'intent', title: 'Intent Router', description: '识别用户意图和研究任务类型', status: 'idle' },
  { key: 'planner', title: 'Planner Agent', description: '拆解研究问题和执行步骤', status: 'idle' },
  { key: 'retriever', title: 'Retriever Agent', description: '从 Chroma 向量库和 MySQL 新闻库召回证据', status: 'idle' },
  { key: 'evidence_judge', title: 'Evidence Judge Agent', description: '过滤、去重、评分并标注证据', status: 'idle' },
  { key: 'analyst', title: 'Analyst Agent', description: '提炼趋势、机会和风险', status: 'idle' },
  { key: 'writer', title: 'Writer Agent', description: '生成带来源编号的 Markdown 报告', status: 'idle' },
]

const depthOptions = [
  { label: '快速', value: 'quick' },
  { label: '标准', value: 'standard' },
  { label: '深入', value: 'deep' },
]

const topic = ref('人工智能相关新闻的行业影响分析')
const depth = ref('standard')
const stages = ref(defaultStages.map((stage) => ({ ...stage })))
const evidence = ref([])
const report = ref('')
const taskId = ref('')
const currentMessage = ref('等待任务')
const isRunning = ref(false)

const formatMarkdown = (content) => {
  if (!content) return ''
  return DOMPurify.sanitize(marked.parse(content))
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const parseSseEvents = (buffer, onEvent) => {
  const parts = buffer.split('\n\n')
  const rest = parts.pop() || ''
  parts.forEach((part) => {
    const line = part.split('\n').find((item) => item.startsWith('data: '))
    if (!line) return
    try {
      onEvent(JSON.parse(line.slice(6)))
    } catch (error) {
      console.error(error)
    }
  })
  return rest
}

const sendMessage = async () => {
  const text = userInput.value.trim()
  if (!text || isLoading.value) return

  messages.value.push({ role: 'user', content: text })
  const assistantMessage = { role: 'assistant', content: '' }
  messages.value.push(assistantMessage)
  userInput.value = ''
  isLoading.value = true
  isStreaming.value = true
  await scrollToBottom()

  try {
    const response = await fetch(`${apiConfig.baseURL}/api/ai/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        history: messages.value.filter((message) => message.content)
      })
    })

    if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`)

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let done = false

    while (!done) {
      const result = await reader.read()
      done = result.done
      buffer += decoder.decode(result.value || new Uint8Array(), { stream: !done })
      buffer = parseSseEvents(buffer, async (payload) => {
        if (payload.event === 'delta') assistantMessage.content += payload.content || ''
        if (payload.event === 'fallback') {
          assistantMessage.content += payload.content || ''
          showToast(payload.message || 'AI 调用失败，已使用兜底回复')
        }
        await scrollToBottom()
      })
    }

    if (buffer.trim()) {
      parseSseEvents(`${buffer}\n\n`, (payload) => {
        if (payload.content) assistantMessage.content += payload.content
      })
    }
    if (!assistantMessage.content) assistantMessage.content = '后端没有返回内容。'
  } catch (error) {
    console.error(error)
    showToast('AI 接口请求失败')
    assistantMessage.content = '请求后端 AI 接口失败，请确认 FastAPI 服务已经启动。'
  } finally {
    isLoading.value = false
    isStreaming.value = false
    await scrollToBottom()
  }
}

const fillPrompt = (text) => {
  userInput.value = text
}

const switchToResearch = (text) => {
  topic.value = text
  activeMode.value = 'research'
}

const resetResearchState = () => {
  stages.value = defaultStages.map((stage) => ({ ...stage }))
  evidence.value = []
  report.value = ''
  taskId.value = ''
  currentMessage.value = '任务启动中'
}

const updateStage = (payload) => {
  const key = payload.key === 'reflect' ? 'evidence_judge' : payload.key
  const index = stages.value.findIndex((stage) => stage.key === key)
  if (index >= 0) {
    stages.value[index] = {
      ...stages.value[index],
      status: payload.status || 'done',
      message: payload.message,
      items: payload.items,
    }
  }

  if (payload.evidence?.length) {
    const merged = new Map(evidence.value.map((item) => [item.id, item]))
    payload.evidence.forEach((item) => merged.set(item.id, item))
    evidence.value = Array.from(merged.values())
  }

  if (payload.report) {
    report.value = payload.report
    const writerIndex = stages.value.findIndex((stage) => stage.key === 'writer')
    if (writerIndex >= 0) {
      stages.value[writerIndex] = {
        ...stages.value[writerIndex],
        status: 'done',
        message: payload.message,
      }
    }
  }

  currentMessage.value = payload.message || currentMessage.value
}

const startResearch = async () => {
  if (!topic.value.trim() || isRunning.value) return

  resetResearchState()
  isRunning.value = true

  try {
    const response = await fetch(`${apiConfig.baseURL}/api/research/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic: topic.value.trim(),
        depth: depth.value,
        user_id: 'demo-user',
      }),
    })

    if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`)

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let finished = false

    while (!finished) {
      const { value, done } = await reader.read()
      finished = done
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
      buffer = parseSseEvents(buffer, (payload) => {
        if (payload.taskId) taskId.value = payload.taskId
        updateStage(payload)
      })
    }

    if (buffer.trim()) parseSseEvents(`${buffer}\n\n`, updateStage)
  } catch (error) {
    console.error(error)
    showToast('DeepResearch 接口请求失败')
    currentMessage.value = '请求失败，请确认后端服务已启动'
  } finally {
    isRunning.value = false
  }
}

onMounted(scrollToBottom)
</script>

<style scoped>
.agent-page {
  min-height: 100vh;
  background: #f7f8fa;
}

.agent-shell {
  width: min(1180px, calc(100% - 48px));
  margin: 0 auto;
  padding: 28px 0 48px;
}

.agent-intro {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  padding: 24px;
  margin-bottom: 18px;
  border: 1px solid #dde3ee;
  border-radius: 8px;
  background: #fff;
}

.eyebrow {
  margin: 0 0 10px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
  text-transform: uppercase;
}

.agent-intro h1 {
  max-width: 760px;
  margin: 0;
  color: #172033;
  font-size: 32px;
  line-height: 1.25;
}

.agent-intro p:last-child {
  max-width: 760px;
  margin: 14px 0 0;
  color: #5b6475;
  line-height: 1.7;
}

.mode-switch,
.depth-control {
  display: inline-grid;
  gap: 4px;
  padding: 4px;
  border: 1px solid #d9e2ef;
  border-radius: 8px;
  background: #f7f9fc;
}

.mode-switch {
  grid-template-columns: repeat(2, 88px);
}

.depth-control {
  grid-template-columns: repeat(3, 64px);
}

.mode-switch button,
.depth-control button {
  height: 36px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #596579;
  font-weight: 700;
  cursor: pointer;
}

.mode-switch button.active,
.depth-control button.active {
  background: #172033;
  color: #fff;
}

.chat-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 18px;
  align-items: start;
}

.chat-card,
.prompt-panel,
.stage-panel,
.report-panel,
.evidence-panel {
  border: 1px solid #dde3ee;
  border-radius: 8px;
  background: #fff;
}

.chat-card {
  min-height: 620px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 18px;
}

.message {
  margin-bottom: 12px;
  max-width: 82%;
}

.user-message {
  margin-left: auto;
}

.ai-message {
  margin-right: auto;
}

.message-content {
  padding: 10px 12px;
  border-radius: 8px;
  line-height: 1.6;
  word-break: break-word;
}

.user-message .message-content {
  background: #1989fa;
  color: #fff;
}

.ai-message .message-content {
  background: #fff;
  color: #323233;
}

.input-container {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 10px;
  border-top: 1px solid #ebedf0;
  background: #fff;
}

.chat-input {
  flex: 1;
}

.send-button {
  flex-shrink: 0;
}

.prompt-panel {
  padding: 16px;
  position: sticky;
  top: 88px;
}

.panel-title,
.section-heading {
  color: #172033;
  font-weight: 800;
}

.panel-title {
  margin-bottom: 12px;
}

.prompt-panel button {
  width: 100%;
  min-height: 40px;
  margin-bottom: 10px;
  padding: 8px 10px;
  border: 1px solid #dde3ee;
  border-radius: 8px;
  background: #f6f8fc;
  color: #172033;
  text-align: left;
  font-weight: 700;
  cursor: pointer;
}

.prompt-panel button:hover {
  border-color: #9ec1ff;
  background: #edf4ff;
  color: #2563eb;
}

.research-control {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 12px;
  align-items: center;
  padding: 14px;
  border: 1px solid #d9e2ef;
  border-radius: 8px;
  background: #fff;
}

.topic-input {
  border-radius: 8px;
  background: #f7f9fc;
}

.run-button {
  min-width: 108px;
}

.research-grid {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 18px;
  margin-top: 18px;
  align-items: start;
}

.stage-panel {
  position: sticky;
  top: 88px;
  padding: 16px;
}

.report-panel {
  min-height: 620px;
  padding: 18px;
}

.evidence-panel {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding: 16px;
}

.section-heading {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.section-heading small {
  color: #738096;
  font-weight: 600;
}

.stage-list {
  display: grid;
  gap: 12px;
}

.stage-item {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr);
  gap: 10px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.stage-dot {
  width: 10px;
  height: 10px;
  margin-top: 5px;
  border-radius: 50%;
  background: #cbd5e1;
}

.stage-item.done {
  border-color: #b8e1d5;
  background: #f2fbf8;
}

.stage-item.done .stage-dot {
  background: #0f766e;
}

.stage-item h3,
.evidence-item h3 {
  margin: 0;
  color: #172033;
  font-size: 15px;
}

.stage-item p,
.evidence-item p {
  margin: 6px 0 0;
  color: #596579;
  line-height: 1.55;
}

.stage-item ul {
  margin: 8px 0 0;
  padding-left: 18px;
  color: #42526a;
  line-height: 1.55;
}

.report-content {
  color: #243044;
  line-height: 1.8;
}

.report-content :deep(h1) {
  margin: 0 0 18px;
  color: #172033;
  font-size: 28px;
  line-height: 1.25;
}

.report-content :deep(h2) {
  margin: 22px 0 10px;
  color: #172033;
  font-size: 18px;
}

.evidence-panel .section-heading,
.evidence-panel .empty-state {
  grid-column: 1 / -1;
}

.evidence-item {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  gap: 12px;
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fbfcfe;
}

.evidence-id {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: #eaf8f4;
  color: #0f766e;
  font-weight: 800;
}

.evidence-item span {
  display: inline-block;
  margin-top: 8px;
  color: #8a6d1f;
  font-size: 12px;
  font-weight: 700;
}

.empty-state {
  min-height: 260px;
  display: grid;
  place-items: center;
  padding: 24px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  color: #738096;
  text-align: center;
}

.empty-state.compact {
  min-height: 90px;
}

:deep(p) {
  margin: 0 0 8px;
}

:deep(p:last-child) {
  margin-bottom: 0;
}

:deep(ul),
:deep(ol) {
  padding-left: 20px;
}

:deep(code) {
  padding: 2px 4px;
  border-radius: 4px;
  background: #f2f3f5;
}

@media (max-width: 960px) {
  .agent-intro,
  .chat-layout,
  .research-control,
  .research-grid,
  .evidence-panel {
    grid-template-columns: 1fr;
  }

  .agent-intro {
    align-items: stretch;
  }

  .prompt-panel,
  .stage-panel {
    position: static;
  }
}

@media (max-width: 680px) {
  .agent-shell {
    width: calc(100% - 24px);
  }

  .agent-intro h1 {
    font-size: 26px;
  }

  .mode-switch,
  .depth-control {
    width: 100%;
    grid-template-columns: repeat(2, 1fr);
  }

  .depth-control {
    grid-template-columns: repeat(3, 1fr);
  }
}
</style>
