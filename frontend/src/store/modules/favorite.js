import { defineStore } from 'pinia';
import axios from 'axios';
import { apiConfig } from '../../config/api';
import { useUserStore } from '../user';

const STORAGE_KEY = 'news-favorites';

const getStorageKey = () => {
  const userStore = useUserStore();
  const userKey = userStore.userInfo?.id || userStore.userInfo?.username || 'guest';
  return `${STORAGE_KEY}-${userKey}`;
};

const normalizeFavorite = (item) => {
  if (!item || typeof item !== 'object') return item;
  return {
    ...item,
    publishTime: item.publishTime || item.publishedTime || item.publish_time,
    categoryId: item.categoryId || item.category_id,
    favoriteId: item.favoriteId || item.favorite_id,
    favoriteTime: item.favoriteTime || item.favorite_time
  };
};

export const useFavoriteStore = defineStore('favorite', {
  state: () => ({
    favorites: []
  }),

  getters: {
    getFavorites: (state) => state.favorites
  },

  actions: {
    loadFavorites() {
      try {
        const raw = localStorage.getItem(getStorageKey());
        const list = raw ? JSON.parse(raw) : [];
        this.favorites = Array.isArray(list) ? list.map(normalizeFavorite) : [];
      } catch (error) {
        this.favorites = [];
      }
    },

    saveFavorites() {
      localStorage.setItem(getStorageKey(), JSON.stringify(this.favorites));
    },

    isFavorite(newsId) {
      return this.favorites.some((x) => Number(x.id) === Number(newsId));
    },

    addFavorite(news) {
      const item = {
        ...news,
        favoriteTime: new Date().toLocaleString()
      };
      this.favorites = [item, ...this.favorites.filter((x) => x.id !== news.id)];
      this.saveFavorites();
    },

    removeFavorite(newsId) {
      this.favorites = this.favorites.filter((x) => Number(x.id) !== Number(newsId));
      this.saveFavorites();
    },

    clearFavorites() {
      this.favorites = [];
      this.saveFavorites();
    },

    async toggleFavorite(news) {
      if (!news || !news.id) return null;
      const exists = this.isFavorite(news.id);
      if (exists) {
        const result = await this.removeFavoriteApi(news.id);
        return result?.success ? false : null;
      }
      const result = await this.addFavoriteApi(news);
      return result?.success ? true : null;
    },

    async addFavoriteApi(news) {
      const userStore = useUserStore();
      if (userStore.getLoginStatus) {
        try {
          const resp = await axios.post(
            `${apiConfig.baseURL}/api/favorite/add`,
            { newsId: news.id },
            { headers: { Authorization: userStore.token } }
          );
          if (resp?.data?.code !== 200) {
            return { success: false, isLocal: false, message: resp?.data?.message || '添加收藏失败' };
          }
        } catch (error) {
          return { success: false, isLocal: false, message: error.response?.data?.detail || '添加收藏接口失败' };
        }
      } else {
        this.addFavorite(news);
        return { success: true, isLocal: true };
      }
      this.addFavorite(news);
      return { success: true };
    },

    async removeFavoriteApi(newsId) {
      const userStore = useUserStore();
      if (userStore.getLoginStatus) {
        try {
          const resp = await axios.delete(`${apiConfig.baseURL}/api/favorite/remove`, {
            params: { newsId },
            headers: { Authorization: userStore.token }
          });
          if (resp?.data?.code !== 200) {
            return { success: false, isLocal: false, message: resp?.data?.message || '取消收藏失败' };
          }
        } catch (error) {
          return { success: false, isLocal: false, message: error.response?.data?.detail || '取消收藏接口失败' };
        }
      } else {
        this.removeFavorite(newsId);
        return { success: true, isLocal: true };
      }
      this.removeFavorite(newsId);
      return { success: true };
    },

    async getFavoriteListApi() {
      const userStore = useUserStore();
      if (!userStore.getLoginStatus) {
        this.loadFavorites();
        return { success: false, isLocal: true, message: '未登录，使用本地收藏' };
      }
      try {
        const resp = await axios.get(`${apiConfig.baseURL}/api/favorite/list`, {
          params: { page: 1, pageSize: 100 },
          headers: { Authorization: userStore.token }
        });
        const list = resp?.data?.data?.list || [];
        if (Array.isArray(list)) {
          this.favorites = list.map(normalizeFavorite);
          this.saveFavorites();
        }
        return { success: true, data: this.favorites };
      } catch (error) {
        this.loadFavorites();
        return { success: false, isLocal: true, message: '接口调用失败，已回退本地收藏' };
      }
    },

    async clearFavoritesApi() {
      const userStore = useUserStore();
      if (!userStore.getLoginStatus) return this.clearFavorites(), { success: true, isLocal: true };
      try {
        const resp = await axios.delete(`${apiConfig.baseURL}/api/favorite/clear`, {
          headers: { Authorization: userStore.token }
        });
        if (resp?.data?.code === 200) {
          this.clearFavorites();
          return { success: true };
        }
      } catch (error) {
        // fallback below
      }
      this.clearFavorites();
      return { success: false, isLocal: true };
    },

    async checkFavoriteStatusApi(newsId) {
      const userStore = useUserStore();
      if (!userStore.getLoginStatus) {
        return { success: true, isFavorite: this.isFavorite(newsId), isLocal: true };
      }
      try {
        const resp = await axios.get(`${apiConfig.baseURL}/api/favorite/check`, {
          params: { newsId },
          headers: { Authorization: userStore.token }
        });
        const isFavorite =
          resp?.data?.data?.isFavorite ?? resp?.data?.data?.is_favorite ?? this.isFavorite(newsId);
        return { success: true, isFavorite: Boolean(isFavorite), isLocal: false };
      } catch (error) {
        return { success: true, isFavorite: this.isFavorite(newsId), isLocal: true };
      }
    }
  }
});
