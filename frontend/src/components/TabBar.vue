<template>
  <header class="site-header">
    <div class="header-inner">
      <router-link to="/home" class="brand">
        <span class="brand-mark">AI</span>
        <span>
          <strong>智能资讯平台</strong>
          <small>News Agent Lab</small>
        </span>
      </router-link>

      <nav class="nav-links">
        <router-link to="/home" :class="{ active: route.path.includes('/home') }">首页</router-link>
        <router-link to="/aichat" :class="{ active: route.path.includes('/aichat') || route.path.includes('/research') }">AI Agent</router-link>
        <router-link to="/favorite" :class="{ active: route.path.includes('/favorite') }">收藏</router-link>
        <router-link to="/history" :class="{ active: route.path.includes('/history') }">历史</router-link>
        <router-link to="/my" :class="{ active: route.path.includes('/my') }">我的</router-link>
      </nav>

      <router-link class="header-action" to="/aichat">
        <van-icon name="guide-o" />
        打开 Agent
      </router-link>
    </div>
  </header>
</template>

<script setup>
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<style scoped>
.site-header {
  position: sticky;
  top: 0;
  z-index: 1000;
  border-bottom: 1px solid rgba(221, 227, 238, 0.9);
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(14px);
}

.header-inner {
  width: min(1180px, calc(100% - 48px));
  height: 68px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 220px;
}

.brand-mark {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: #172033;
  color: #fff;
  font-weight: 800;
}

.brand strong,
.brand small {
  display: block;
}

.brand strong {
  font-size: 17px;
  letter-spacing: 0;
}

.brand small {
  margin-top: 2px;
  color: #8a94a6;
  font-size: 12px;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav-links a {
  padding: 9px 12px;
  border-radius: 8px;
  color: #5b6475;
  font-weight: 600;
}

.nav-links a.active,
.nav-links a:hover {
  background: #edf4ff;
  color: #2563eb;
}

.header-action {
  height: 38px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 14px;
  border-radius: 8px;
  background: #2563eb;
  color: #fff;
  font-weight: 700;
}

@media (max-width: 760px) {
  .header-inner {
    width: calc(100% - 24px);
    height: auto;
    padding: 12px 0;
    flex-wrap: wrap;
  }

  .brand {
    min-width: 0;
  }

  .nav-links {
    width: 100%;
    overflow-x: auto;
    padding-bottom: 2px;
  }

  .header-action {
    display: none;
  }
}
</style>
