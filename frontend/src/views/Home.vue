<template>
  <div class="home-page">
    <tab-bar />

    <main class="page-shell">
      <section class="hero">
        <div class="hero-copy">
          <p class="eyebrow">智能新闻助手平台</p>
          <h1>面向热点追踪、摘要生成和个性化推荐的智能资讯平台</h1>
          <p class="hero-text">
            基于 FastAPI、Vue3 和后续 RAG Agent 能力，构建一个能浏览新闻、沉淀用户行为、辅助分析资讯内容的 AI 应用项目。
          </p>
          <div class="search-box">
            <van-icon name="search" />
            <input
              v-model="keyword"
              type="text"
              placeholder="搜索标题、简介、作者..."
            />
          </div>

          <div class="hero-actions">
            <button class="primary-action" @click="router.push('/aichat')">打开 AI 助手</button>
            <button class="secondary-action" @click="router.push('/favorite')">查看我的收藏</button>
          </div>
        </div>

        <div class="hero-panel">
          <div class="metric">
            <strong>{{ newsStore.newsList.length }}</strong>
            <span>当前加载新闻</span>
          </div>
          <div class="metric">
            <strong>{{ displayCategories.length }}</strong>
            <span>内容分类</span>
          </div>
          <div class="metric">
            <strong>AI</strong>
            <span>摘要 / 问答 / 推荐</span>
          </div>
        </div>
      </section>

      <section class="content-grid">
        <aside class="left-panel">
          <div class="panel">
            <div class="panel-title">频道分类</div>
            <button
              v-for="(category, index) in displayCategories"
              :key="category.id"
              class="category-button"
              :class="{ active: activeTab === index }"
              @click="selectCategory(category.id, index)"
            >
              <span>{{ getCategoryTranslation(category.name) }}</span>
              <van-icon name="arrow" />
            </button>
          </div>

          <div class="panel capability-panel">
            <div class="panel-title">项目能力</div>
            <div class="capability-item">
              <span class="dot blue"></span>
              <p>新闻列表、详情、收藏、浏览历史</p>
            </div>
            <div class="capability-item">
              <span class="dot green"></span>
              <p>AI 聊天入口已接入 FastAPI</p>
            </div>
            <div class="capability-item">
              <span class="dot orange"></span>
              <p>下一步接入 RAG 知识库和 Agent 工具调用</p>
            </div>
          </div>
        </aside>

        <section class="main-feed">
          <div class="section-head">
            <div>
              <p class="eyebrow">今日热点</p>
              <h2>{{ currentCategoryName }}资讯</h2>
            </div>
            <button class="refresh-button" :disabled="newsStore.loading" @click="onRefresh">
              <van-icon name="replay" />
              刷新
            </button>
            <button class="fetch-button" :disabled="newsStore.loading || fetchingHot" @click="onFetchHotNews">
              <van-icon :name="fetchingHot ? 'replay' : 'fire-o'" />
              {{ fetchingHot ? '正在抓取 9 个频道...' : '抓取今日热点' }}
            </button>
          </div>

          <article v-if="featuredNews" class="featured-card" @click="goToDetail(featuredNews.id)">
            <smart-image :src="featuredNews.image" :alt="featuredNews.title" />
            <div class="featured-content">
              <span class="tag">重点推荐</span>
              <h3>{{ featuredNews.title }}</h3>
              <p>{{ featuredNews.description }}</p>
              <div class="meta-line">
                <span>{{ featuredNews.author || '未知作者' }}</span>
                <span>{{ formatDate(featuredNews.publishTime) }}</span>
                <span>{{ featuredNews.views }} 阅读</span>
              </div>
            </div>
          </article>

          <van-empty
            v-if="emptyDescription"
            :description="emptyDescription"
          />

          <div class="news-list">
            <news-item
              v-for="item in normalNews"
              :key="item.id"
              :news="item"
            />
          </div>

          <button
            v-if="!newsStore.finished && newsStore.newsList.length"
            class="load-more"
            :disabled="newsStore.loading"
            @click="onLoad"
          >
            {{ newsStore.loading ? '加载中...' : '加载更多' }}
          </button>
        </section>

        <aside class="right-panel">
          <div class="ai-card">
            <p class="eyebrow">智能助手</p>
            <h3>让新闻不只停留在阅读</h3>
            <p>进入 AI 助手后，可以继续扩展为新闻摘要、热点分析、舆情判断和个性化推荐。</p>
            <button @click="router.push('/aichat')">开始对话</button>
          </div>

          <div class="panel">
            <div class="panel-title">热点榜</div>
            <div
              v-for="(item, index) in rankingNews"
              :key="item.id"
              class="rank-item"
              @click="goToDetail(item.id)"
            >
              <strong>{{ index + 1 }}</strong>
              <span>{{ item.title }}</span>
            </div>
          </div>

          <div class="panel">
            <div class="panel-title">学习提示</div>
            <p class="study-note">
              这个首页仍然使用原来的新闻接口。你看到的只是展示层改变，数据流仍然是 Vue 调 Pinia，Pinia 用 Axios 请求 FastAPI。
            </p>
          </div>
        </aside>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import NewsItem from '../components/NewsItem.vue'
import SmartImage from '../components/SmartImage.vue'
import TabBar from '../components/TabBar.vue'
import { useNewsStore } from '../store/modules/news'
import { closeToast, showLoadingToast, showToast } from 'vant'

const newsStore = useNewsStore()
const router = useRouter()
const route = useRoute()
const { t } = useI18n()
const activeTab = ref(0)
const keyword = ref('')
const fetchingHot = ref(false)

const displayCategories = computed(() => {
  return newsStore.categories.filter((category) => category.name !== '更多')
})

const filteredNews = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  if (!text) return newsStore.newsList
  return newsStore.newsList.filter((item) => {
    return [item.title, item.description, item.author]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(text))
  })
})
const featuredNews = computed(() => filteredNews.value[0])
const normalNews = computed(() => filteredNews.value.slice(1))
const rankingNews = computed(() => {
  return [...newsStore.newsList]
    .sort((a, b) => Number(b.views || 0) - Number(a.views || 0))
    .slice(0, 5)
})
const emptyDescription = computed(() => {
  if (newsStore.errorMessage && !newsStore.newsList.length) return newsStore.errorMessage
  if (keyword.value.trim() && !filteredNews.value.length) return '没有找到匹配的新闻'
  if (!newsStore.loading && newsStore.finished && !newsStore.newsList.length) return '数据库暂无新闻，请点击“抓取今日热点”更新'
  return ''
})

const currentCategoryName = computed(() => {
  const category = displayCategories.value[activeTab.value]
  return category ? getCategoryTranslation(category.name) : '头条'
})

const getCategoryTranslation = (categoryName) => {
  const categoryMap = {
    '头条': 'headline',
    '社会': 'society',
    '国内': 'domestic',
    '国际': 'international',
    '娱乐': 'entertainment',
    '体育': 'sports',
    '军事': 'military',
    '科技': 'technology',
    '财经': 'finance',
    '更多': 'more'
  }
  const key = categoryMap[categoryName]
  return key ? t(`home.categories.${key}`) : categoryName
}

const selectCategory = (categoryId, index) => {
  activeTab.value = index
  newsStore.changeCategory(categoryId)
  newsStore.getNewsList(true)
}

const onRefresh = () => {
  return newsStore.getNewsList(true)
}

const onFetchHotNews = async () => {
  if (fetchingHot.value) return
  fetchingHot.value = true
  showLoadingToast({
    message: '正在抓取 9 个频道，每个频道 10 条...',
    forbidClick: true,
    duration: 0
  })
  try {
    const result = await newsStore.fetchHotNews({ all: true, replace: true, limit: 10, useAi: false })
    closeToast()
    const counts = result?.categoryCounts || {}
    const missing = Object.entries(counts).filter(([, count]) => Number(count) === 0).map(([id]) => id)
    showToast(missing.length ? `已抓取 ${result?.fetched || 0} 条，部分频道无数据` : `已替换为 ${result?.fetched || 0} 条热点新闻`)
  } catch (error) {
    closeToast()
    showToast('抓取热点失败')
  } finally {
    fetchingHot.value = false
  }
}

const onLoad = () => {
  return newsStore.getNewsList()
}

const goToDetail = (id) => {
  router.push(`/news/detail/${id}`)
}

const formatDate = (value) => {
  if (!value) return ''
  return String(value).replace('T', ' ').slice(0, 16)
}

watch(
  () => route.query.categoryId,
  (newCategoryId) => {
    if (!newCategoryId || !displayCategories.value.length) return
    const categoryId = Number(newCategoryId)
    const index = displayCategories.value.findIndex((item) => item.id === categoryId)
    if (index === -1) return
    selectCategory(categoryId, index)
  }
)

onMounted(async () => {
  await newsStore.getCategories()
  const first = displayCategories.value[activeTab.value]
  if (first) {
    newsStore.changeCategory(first.id)
    await newsStore.autoRefreshHotNews()
  }
})
</script>

<style scoped>
.home-page {
  min-height: 100vh;
  background: #f4f7fb;
}

.page-shell {
  width: min(1180px, calc(100% - 48px));
  margin: 0 auto;
  padding: 28px 0 48px;
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 24px;
  align-items: stretch;
  margin-bottom: 24px;
}

.hero-copy,
.hero-panel,
.panel,
.ai-card,
.featured-card {
  border: 1px solid #dde3ee;
  border-radius: 8px;
  background: #fff;
}

.hero-copy {
  padding: 34px;
}

.eyebrow {
  margin: 0 0 10px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
  text-transform: uppercase;
}

.hero h1 {
  max-width: 760px;
  margin: 0;
  font-size: 38px;
  line-height: 1.18;
  letter-spacing: 0;
  color: #172033;
}

.hero-text {
  max-width: 720px;
  margin: 18px 0 0;
  color: #5b6475;
  font-size: 16px;
  line-height: 1.8;
}

.hero-actions {
  display: flex;
  gap: 12px;
  margin-top: 26px;
}

.search-box {
  max-width: 520px;
  height: 44px;
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 24px;
  padding: 0 14px;
  border: 1px solid #dde3ee;
  border-radius: 8px;
  background: #f6f8fc;
  color: #8a94a6;
}

.search-box input {
  width: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: #172033;
  font-size: 15px;
}

.primary-action,
.secondary-action,
.refresh-button,
.fetch-button,
.load-more,
.ai-card button {
  height: 40px;
  padding: 0 16px;
  border: 1px solid transparent;
  border-radius: 8px;
  font-weight: 700;
  cursor: pointer;
}

.primary-action,
.ai-card button {
  background: #2563eb;
  color: #fff;
}

.secondary-action,
.refresh-button,
.fetch-button,
.load-more {
  background: #fff;
  border-color: #dde3ee;
  color: #172033;
}

.hero-panel {
  display: grid;
  gap: 1px;
  overflow: hidden;
  background: #dde3ee;
}

.metric {
  padding: 24px;
  background: #fff;
}

.metric strong,
.metric span {
  display: block;
}

.metric strong {
  font-size: 30px;
  color: #172033;
}

.metric span {
  margin-top: 4px;
  color: #5b6475;
}

.content-grid {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr) 280px;
  gap: 20px;
  align-items: start;
}

.left-panel,
.right-panel {
  display: grid;
  gap: 16px;
  position: sticky;
  top: 88px;
}

.panel {
  padding: 16px;
}

.panel-title {
  margin-bottom: 12px;
  font-size: 15px;
  font-weight: 800;
  color: #172033;
}

.category-button {
  width: 100%;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  padding: 0 10px 0 12px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: #f6f8fc;
  color: #5b6475;
  font-weight: 700;
  cursor: pointer;
}

.category-button.active {
  border-color: #bcd4ff;
  background: #edf4ff;
  color: #2563eb;
}

.capability-panel {
  color: #5b6475;
}

.capability-item {
  display: flex;
  gap: 10px;
  margin-top: 12px;
  line-height: 1.55;
}

.capability-item p {
  margin: 0;
}

.dot {
  width: 8px;
  height: 8px;
  flex-shrink: 0;
  margin-top: 7px;
  border-radius: 50%;
}

.dot.blue {
  background: #2563eb;
}

.dot.green {
  background: #0f766e;
}

.dot.orange {
  background: #d97706;
}

.main-feed {
  min-width: 0;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.section-head h2 {
  margin: 0;
  font-size: 26px;
  color: #172033;
}

.refresh-button,
.fetch-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.fetch-button {
  background: #172033;
  color: #fff;
}

.refresh-button:disabled,
.fetch-button:disabled {
  opacity: 0.65;
  cursor: wait;
}

.featured-card {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 22px;
  padding: 18px;
  margin-bottom: 14px;
  cursor: pointer;
  transition: border-color 0.2s, transform 0.2s, box-shadow 0.2s;
}

.featured-card:hover {
  border-color: #9ec1ff;
  transform: translateY(-2px);
  box-shadow: 0 14px 30px rgba(23, 32, 51, 0.08);
}

.featured-card :deep(.smart-image) {
  width: 100%;
  aspect-ratio: 4 / 3;
  border-radius: 8px;
  overflow: hidden;
  background: #e6ebf2;
}

.tag {
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 10px;
  border-radius: 8px;
  background: #edf4ff;
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
}

.featured-content h3 {
  margin: 14px 0 10px;
  font-size: 24px;
  line-height: 1.35;
  color: #172033;
}

.featured-content p {
  margin: 0;
  color: #5b6475;
  line-height: 1.7;
}

.meta-line {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 16px;
  color: #8a94a6;
  font-size: 13px;
}

.news-list {
  display: grid;
  gap: 12px;
}

.load-more {
  width: 100%;
  margin-top: 16px;
}

.ai-card {
  padding: 18px;
  background: #172033;
  color: #fff;
}

.ai-card .eyebrow {
  color: #93c5fd;
}

.ai-card h3 {
  margin: 0 0 10px;
  font-size: 22px;
  line-height: 1.35;
}

.ai-card p {
  margin: 0;
  color: #d8dee9;
  line-height: 1.7;
}

.ai-card button {
  width: 100%;
  margin-top: 16px;
  background: #fff;
  color: #172033;
}

.rank-item {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid #eef2f7;
  cursor: pointer;
}

.rank-item:last-child {
  border-bottom: 0;
}

.rank-item strong {
  color: #2563eb;
}

.rank-item span {
  color: #172033;
  line-height: 1.45;
}

.study-note {
  margin: 0;
  color: #5b6475;
  line-height: 1.7;
}

@media (max-width: 1040px) {
  .hero,
  .content-grid {
    grid-template-columns: 1fr;
  }

  .left-panel,
  .right-panel {
    position: static;
  }

  .left-panel {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 720px) {
  .page-shell {
    width: calc(100% - 24px);
    padding-top: 18px;
  }

  .hero-copy {
    padding: 22px;
  }

  .hero h1 {
    font-size: 28px;
  }

  .hero-actions,
  .left-panel {
    grid-template-columns: 1fr;
    flex-direction: column;
  }

  .featured-card {
    grid-template-columns: 1fr;
  }
}
</style>
