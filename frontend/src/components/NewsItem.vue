<template>
  <div class="news-item" @click="goToDetail">
    <div class="news-image">
      <smart-image :src="news.image" :alt="news.title" />
    </div>
    <div class="news-content">
      <div class="news-kicker">
        <span>资讯</span>
        <span>{{ formatDate(news.publishTime) }}</span>
      </div>
      <h3 class="news-title">{{ news.title }}</h3>
      <p class="news-desc">{{ news.description }}</p>
      <div class="news-info">
        <span>{{ news.author || '未知作者' }}</span>
        <span>{{ news.views }} 阅读</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import SmartImage from './SmartImage.vue'

const props = defineProps({
  news: {
    type: Object,
    required: true
  }
})

const router = useRouter()

const goToDetail = () => {
  router.push(`/news/detail/${props.news.id}`)
}

const formatDate = (value) => {
  if (!value) return ''
  return String(value).replace('T', ' ').slice(0, 16)
}
</script>

<style scoped>
.news-item {
  display: grid;
  grid-template-columns: 168px minmax(0, 1fr);
  gap: 18px;
  padding: 16px;
  border: 1px solid #dde3ee;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.2s, transform 0.2s, box-shadow 0.2s;
}

.news-item:hover {
  border-color: #9ec1ff;
  transform: translateY(-2px);
  box-shadow: 0 12px 28px rgba(23, 32, 51, 0.07);
}

.news-image {
  width: 100%;
  min-width: 0;
}

.news-image :deep(.smart-image) {
  aspect-ratio: 4 / 3;
  border-radius: 8px;
  overflow: hidden;
  background: #e6ebf2;
}

.news-content {
  overflow: hidden;
}

.news-kicker {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 8px;
  color: #8a94a6;
  font-size: 12px;
  font-weight: 700;
}

.news-kicker span:first-child {
  color: #2563eb;
}

.news-title {
  margin: 0 0 10px;
  color: #172033;
  font-size: 19px;
  font-weight: 800;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.news-desc {
  margin: 0 0 12px;
  color: #5b6475;
  font-size: 14px;
  line-height: 1.65;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.news-info {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: #8a94a6;
  font-size: 13px;
}

.news-info span {
  margin-right: 0;
}

@media (max-width: 620px) {
  .news-item {
    grid-template-columns: 1fr;
  }
}
</style>
