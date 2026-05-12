<template>
  <div class="library-page">
    <tab-bar />

    <main class="library-shell">
      <section class="library-head">
        <div>
          <p class="eyebrow">Reading Trail</p>
          <h1>浏览历史</h1>
          <p>登录后历史记录按当前账号保存；未登录时会保存在当前浏览器。</p>
        </div>
        <button class="danger-action" :disabled="!historyStore.getHistory.length" @click="onClickClear">
          清空历史
        </button>
      </section>

      <section v-if="historyStore.getHistory.length" class="library-list">
        <article
          v-for="item in historyStore.getHistory"
          :key="item.historyId || item.id"
          class="library-item"
        >
          <div class="thumb" @click="goToNewsDetail(item.id)">
            <smart-image :src="item.image" :alt="item.title" />
          </div>
          <div class="item-body" @click="goToNewsDetail(item.id)">
            <div class="item-meta">
              <span>{{ item.author || '未知作者' }}</span>
              <span>{{ formatDate(item.publishTime) }}</span>
              <span>浏览时间：{{ formatDate(item.viewTime) }}</span>
            </div>
            <h2>{{ item.title }}</h2>
            <p>{{ item.description || '暂无简介' }}</p>
          </div>
          <button class="icon-action" @click="confirmDelete(item.historyId || item.id)">
            <van-icon name="delete-o" />
          </button>
        </article>
      </section>

      <van-empty v-else description="暂无浏览历史" />
    </main>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showDialog, showToast } from 'vant'
import SmartImage from '../components/SmartImage.vue'
import TabBar from '../components/TabBar.vue'
import { useHistoryStore } from '../store/modules/history'

const router = useRouter()
const historyStore = useHistoryStore()

const goToNewsDetail = (id) => {
  router.push(`/news/detail/${id}`)
}

const formatDate = (value) => {
  if (!value) return ''
  return String(value).replace('T', ' ').slice(0, 16)
}

const removeHistory = async (id) => {
  const result = await historyStore.removeHistoryApi(id)
  showToast({
    message: result?.success ? '已删除历史记录' : (result?.message || '删除失败'),
    position: 'bottom'
  })
}

const confirmDelete = (id) => {
  showDialog({
    title: '提示',
    message: '确定要删除这条浏览记录吗？',
    showCancelButton: true,
  }).then((action) => {
    if (action === 'confirm') removeHistory(id)
  })
}

const onClickClear = async () => {
  showDialog({
    title: '提示',
    message: '确定要清空所有浏览历史吗？',
    showCancelButton: true,
  }).then(async (action) => {
    if (action === 'confirm') {
      const result = await historyStore.clearHistoryApi()
      showToast({
        message: result?.success ? '已清空历史' : '清空失败',
        position: 'bottom'
      })
    }
  })
}

onMounted(async () => {
  await historyStore.getHistoryListApi()
})
</script>

<style scoped>
.library-page {
  min-height: 100vh;
  background: #f4f7fb;
}

.library-shell {
  width: min(980px, calc(100% - 48px));
  margin: 0 auto;
  padding: 28px 0 48px;
}

.library-head,
.library-item {
  border: 1px solid #dde3ee;
  border-radius: 8px;
  background: #fff;
}

.library-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 26px;
  margin-bottom: 18px;
}

.eyebrow {
  margin: 0 0 8px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.library-head h1 {
  margin: 0;
  color: #172033;
  font-size: 32px;
}

.library-head p {
  margin: 10px 0 0;
  color: #5b6475;
}

.danger-action {
  height: 40px;
  padding: 0 16px;
  border: 1px solid #fecaca;
  border-radius: 8px;
  background: #fff1f2;
  color: #be123c;
  font-weight: 800;
  cursor: pointer;
}

.library-list {
  display: grid;
  gap: 12px;
}

.library-item {
  display: grid;
  grid-template-columns: 168px minmax(0, 1fr) 44px;
  gap: 16px;
  align-items: center;
  padding: 16px;
}

.thumb :deep(.smart-image) {
  aspect-ratio: 4 / 3;
  border-radius: 8px;
  overflow: hidden;
}

.item-body {
  cursor: pointer;
}

.item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: #8a94a6;
  font-size: 13px;
}

.item-body h2 {
  margin: 8px 0;
  color: #172033;
  font-size: 20px;
  line-height: 1.35;
}

.item-body p {
  margin: 0;
  color: #5b6475;
  line-height: 1.6;
}

.icon-action {
  width: 38px;
  height: 38px;
  border: 1px solid #dde3ee;
  border-radius: 8px;
  background: #fff;
  color: #be123c;
  cursor: pointer;
}

@media (max-width: 760px) {
  .library-shell {
    width: calc(100% - 24px);
  }

  .library-head,
  .library-item {
    grid-template-columns: 1fr;
  }

  .library-head {
    display: grid;
  }
}
</style>
