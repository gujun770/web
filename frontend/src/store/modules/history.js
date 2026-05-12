import { defineStore } from 'pinia';
import axios from 'axios';
import { apiConfig } from '../../config/api';
import { useUserStore } from '../user';

const STORAGE_KEY = 'news-history';

const getStorageKey = () => {
  const userStore = useUserStore();
  const userKey = userStore.userInfo?.id || userStore.userInfo?.username || 'guest';
  return `${STORAGE_KEY}-${userKey}`;
};

const normalizeHistory = (item) => {
  if (!item || typeof item !== 'object') return item;
  return {
    ...item,
    publishTime: item.publishTime || item.publishedTime || item.publish_time,
    categoryId: item.categoryId || item.category_id,
    historyId: item.historyId || item.history_id,
    viewTime: item.viewTime || item.view_time
  };
};

export const useHistoryStore = defineStore('history', {
  state: () => ({
    historyList: []
  }),

  getters: {
    getHistory: (state) => state.historyList
  },

  actions: {
    loadHistory() {
      try {
        const raw = localStorage.getItem(getStorageKey());
        const list = raw ? JSON.parse(raw) : [];
        this.historyList = Array.isArray(list) ? list.map(normalizeHistory) : [];
      } catch (error) {
        this.historyList = [];
      }
    },

    saveHistory() {
      localStorage.setItem(getStorageKey(), JSON.stringify(this.historyList));
    },

    addHistory(news) {
      if (!news || !news.id) return;
      const item = {
        ...news,
        viewTime: new Date().toLocaleString()
      };
      this.historyList = [item, ...this.historyList.filter((x) => x.id !== news.id)].slice(0, 200);
      this.saveHistory();
    },

    removeHistory(id) {
      this.historyList = this.historyList.filter((x) => {
        const recordId = x.historyId || x.id;
        return Number(recordId) !== Number(id);
      });
      this.saveHistory();
      return { success: true, isLocal: true };
    },

    clearHistory() {
      this.historyList = [];
      this.saveHistory();
      return { success: true, isLocal: true };
    },

    async addHistoryApi(newsId) {
      const userStore = useUserStore();
      if (!userStore.getLoginStatus) return { success: false, isLocal: true, message: '未登录' };
      try {
          const resp = await axios.post(
            `${apiConfig.baseURL}/api/history/add`,
          { newsId },
          { headers: { Authorization: userStore.token } }
        );
        return { success: resp?.data?.code === 200, data: resp?.data };
      } catch (error) {
        return { success: false, isLocal: true, message: '接口调用失败，已使用本地记录' };
      }
    },

    async getHistoryListApi() {
      const userStore = useUserStore();
      if (!userStore.getLoginStatus) {
        this.loadHistory();
        return { success: false, isLocal: true, message: '未登录，使用本地历史' };
      }
      try {
        const resp = await axios.get(`${apiConfig.baseURL}/api/history/list`, {
          params: { page: 1, pageSize: 100 },
          headers: { Authorization: userStore.token }
        });
        const list = resp?.data?.data?.list || [];
        if (Array.isArray(list)) {
          this.historyList = list.map(normalizeHistory);
          this.saveHistory();
        }
        return { success: true, data: this.historyList };
      } catch (error) {
        this.loadHistory();
        return { success: false, isLocal: true, message: '接口调用失败，已回退本地历史' };
      }
    },

    async removeHistoryApi(id) {
      const userStore = useUserStore();
      if (!userStore.getLoginStatus) return this.removeHistory(id);
      try {
        const resp = await axios.delete(`${apiConfig.baseURL}/api/history/delete/${id}`, {
          headers: { Authorization: userStore.token }
        });
        if (resp?.data?.code === 200) {
          this.removeHistory(id);
          return { success: true };
        }
      } catch (error) {
        // fallback below
      }
      return this.removeHistory(id);
    },

    async clearHistoryApi() {
      const userStore = useUserStore();
      if (!userStore.getLoginStatus) return this.clearHistory();
      try {
        const resp = await axios.delete(`${apiConfig.baseURL}/api/history/clear`, {
          headers: { Authorization: userStore.token }
        });
        if (resp?.data?.code === 200) {
          this.clearHistory();
          return { success: true };
        }
      } catch (error) {
        // fallback below
      }
      return this.clearHistory();
    }
  }
});
