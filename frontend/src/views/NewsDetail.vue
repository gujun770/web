<template>
  <div class="detail-page">
    <tab-bar />

    <main class="detail-shell">
      <button class="back-button" @click="onClickLeft">
        <van-icon name="arrow-left" />
        返回资讯列表
      </button>

      <div v-if="newsStore.newsDetail.id" class="detail-grid">
        <article class="article-card">
          <div class="article-head">
            <p class="eyebrow">新闻详情</p>
            <h1>{{ newsStore.newsDetail.title }}</h1>
            <div class="article-meta">
              <span>{{ newsStore.newsDetail.author || '未知作者' }}</span>
              <span>{{ formatDate(newsStore.newsDetail.publishTime) }}</span>
              <span>{{ newsStore.newsDetail.views }} 阅读</span>
            </div>
          </div>

          <smart-image
            class="cover"
            :src="newsStore.newsDetail.image"
            :alt="newsStore.newsDetail.title"
          />

          <div class="content">
            <p v-for="(paragraph, index) in contentParagraphs" :key="index">
              {{ paragraph }}
            </p>
          </div>
        </article>

        <aside class="side-column">
          <div class="action-card">
            <button
              class="favorite-button"
              :class="{ active: isFavorite }"
              @click="toggleFavorite"
            >
              <van-icon :name="isFavorite ? 'star' : 'star-o'" />
              {{ isFavorite ? '已收藏' : '收藏新闻' }}
            </button>
            <button class="ai-button" @click="router.push('/aichat')">
              <van-icon name="chat-o" />
              让 AI 分析这篇新闻
            </button>
            <button class="summary-button" :disabled="summaryLoading" @click="generateSummary">
              <van-icon name="notes-o" />
              {{ summaryLoading ? '生成中...' : '生成摘要' }}
            </button>
          </div>

          <div class="panel">
            <div class="panel-title">AI 摘要</div>
            <p v-if="summaryText">{{ summaryText }}</p>
            <p v-else>点击“生成摘要”，先通过当前学习版 AI 接口完成新闻摘要入口，后续可替换成专门的摘要模型链路。</p>
          </div>

          <div class="panel" v-if="newsStore.newsDetail.relatedNews?.length">
            <div class="panel-title">相关推荐</div>
            <div
              v-for="item in newsStore.newsDetail.relatedNews"
              :key="item.id"
              class="related-item"
              @click="goToRelatedNews(item.id)"
            >
              <smart-image :src="item.image" :alt="item.title" />
              <span>{{ item.title }}</span>
            </div>
          </div>
        </aside>
      </div>

      <van-empty
        v-else
        :description="newsStore.errorMessage || '加载中...'"
      />
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import { apiConfig } from '../config/api'
import SmartImage from '../components/SmartImage.vue'
import TabBar from '../components/TabBar.vue'
import { useFavoriteStore } from '../store/modules/favorite'
import { useHistoryStore } from '../store/modules/history'
import { useNewsStore } from '../store/modules/news'
import { useUserStore } from '../store/user'

const route = useRoute()
const router = useRouter()
const newsStore = useNewsStore()
const historyStore = useHistoryStore()
const favoriteStore = useFavoriteStore()
const userStore = useUserStore()
const summaryText = ref('')
const summaryLoading = ref(false)

const newsId = computed(() => Number(route.params.id))

const contentParagraphs = computed(() => {
  if (!newsStore.newsDetail.content) return []
  return newsStore.newsDetail.content.split('\n\n').filter((p) => p.trim())
})

const isFavorite = computed(() => {
  return favoriteStore.isFavorite(newsId.value)
})

const onClickLeft = () => {
  router.back()
}

const goToRelatedNews = (id) => {
  router.push(`/news/detail/${id}`)
}

const formatDate = (value) => {
  if (!value) return ''
  return String(value).replace('T', ' ').slice(0, 16)
}

const toggleFavorite = async () => {
  if (!userStore.getLoginStatus) {
    showToast({
      message: '请先登录后再收藏',
      position: 'bottom',
    })
    router.push('/login')
    return
  }

  const status = await favoriteStore.toggleFavorite(newsStore.newsDetail)

  if (status === true) {
    showToast({ message: '已添加到收藏', position: 'bottom' })
  } else if (status === false) {
    showToast({ message: '已取消收藏', position: 'bottom' })
  } else {
    showToast({ message: '操作失败，请稍后重试', position: 'bottom' })
  }
}

const generateSummary = async () => {
  if (!newsStore.newsDetail.id || summaryLoading.value) return
  summaryLoading.value = true
  try {
    const response = await axios.post(`${apiConfig.baseURL}/api/ai/chat`, {
      message: `请用三句话总结这篇新闻，并给出一个可能影响：${newsStore.newsDetail.title}\n\n${newsStore.newsDetail.content || ''}`,
      history: []
    })
    summaryText.value = response.data?.data?.reply || '暂时没有生成摘要。'
  } catch (error) {
    console.error(error)
    showToast({ message: 'AI 摘要生成失败', position: 'bottom' })
  } finally {
    summaryLoading.value = false
  }
}

onMounted(async () => {
  await newsStore.getNewsDetail(newsId.value)

  if (newsStore.newsDetail.id) {
    if (userStore.getLoginStatus) {
      try {
        await historyStore.addHistoryApi(newsStore.newsDetail.id)
      } catch (error) {
        console.error('记录浏览历史API失败:', error)
      }
    } else {
      historyStore.addHistory(newsStore.newsDetail)
    }
  }

  favoriteStore.loadFavorites()

  if (userStore.getLoginStatus && newsStore.newsDetail.id) {
    const result = await favoriteStore.checkFavoriteStatusApi(newsStore.newsDetail.id)
    if (result.success && !result.isLocal) {
      if (result.isFavorite && !favoriteStore.isFavorite(newsStore.newsDetail.id)) {
        favoriteStore.addFavorite(newsStore.newsDetail)
      } else if (!result.isFavorite && favoriteStore.isFavorite(newsStore.newsDetail.id)) {
        favoriteStore.removeFavorite(newsStore.newsDetail.id)
      }
    }
  }
})
</script>

<style scoped>
.detail-page {
  min-height: 100vh;
  background: #f4f7fb;
}

.detail-shell {
  width: min(1080px, calc(100% - 48px));
  margin: 0 auto;
  padding: 24px 0 48px;
}

.back-button {
  height: 38px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 16px;
  padding: 0 12px;
  border: 1px solid #dde3ee;
  border-radius: 8px;
  background: #fff;
  color: #172033;
  font-weight: 700;
  cursor: pointer;
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 22px;
  align-items: start;
}

.article-card,
.panel,
.action-card {
  border: 1px solid #dde3ee;
  border-radius: 8px;
  background: #fff;
}

.article-card {
  padding: 30px;
}

.article-head {
  margin-bottom: 22px;
}

.eyebrow {
  margin: 0 0 10px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
  text-transform: uppercase;
}

.article-head h1 {
  margin: 0;
  color: #172033;
  font-size: 34px;
  line-height: 1.28;
  letter-spacing: 0;
}

.article-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 16px;
  color: #8a94a6;
}

.cover {
  width: 100%;
  aspect-ratio: 16 / 7;
  max-height: 420px;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 26px;
  background: #e6ebf2;
}

.content {
  color: #273247;
  font-size: 17px;
  line-height: 1.95;
}

.content p {
  margin: 0 0 18px;
  text-align: justify;
}

.side-column {
  display: grid;
  gap: 16px;
  position: sticky;
  top: 88px;
}

.action-card,
.panel {
  padding: 16px;
}

.favorite-button,
.ai-button,
.summary-button {
  width: 100%;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border-radius: 8px;
  font-weight: 800;
  cursor: pointer;
}

.favorite-button {
  border: 1px solid #dde3ee;
  background: #fff;
  color: #172033;
}

.favorite-button.active {
  border-color: #f2c36b;
  background: #fff7e8;
  color: #d97706;
}

.ai-button {
  margin-top: 10px;
  border: 1px solid #2563eb;
  background: #2563eb;
  color: #fff;
}

.summary-button {
  margin-top: 10px;
  border: 1px solid #dde3ee;
  background: #f6f8fc;
  color: #172033;
}

.panel-title {
  margin-bottom: 12px;
  font-size: 15px;
  font-weight: 800;
  color: #172033;
}

.panel p {
  margin: 0;
  color: #5b6475;
  line-height: 1.7;
}

.related-item {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid #eef2f7;
  cursor: pointer;
}

.related-item:last-child {
  border-bottom: 0;
}

.related-item :deep(.smart-image) {
  width: 72px;
  aspect-ratio: 4 / 3;
  border-radius: 8px;
  overflow: hidden;
  background: #e6ebf2;
}

.related-item span {
  color: #172033;
  line-height: 1.45;
}

@media (max-width: 900px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .side-column {
    position: static;
  }
}

@media (max-width: 680px) {
  .detail-shell {
    width: calc(100% - 24px);
  }

  .article-card {
    padding: 20px;
  }

  .article-head h1 {
    font-size: 26px;
  }
}
</style>
