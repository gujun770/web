import { defineStore } from 'pinia';
import axios from 'axios';
import { apiConfig } from '../../config/api';

const DEFAULT_CATEGORIES = [
  { id: 1, name: '头条' },
  { id: 2, name: '社会' },
  { id: 3, name: '国内' },
  { id: 4, name: '国际' },
  { id: 5, name: '娱乐' },
  { id: 6, name: '体育' },
  { id: 7, name: '军事' },
  { id: 8, name: '科技' },
  { id: 9, name: '财经' },
  { id: 10, name: '更多' }
];

const normalizeNews = (item) => {
  if (!item || typeof item !== 'object') return item;
  const image = item.image && /^https?:\/\//.test(item.image)
    ? `${apiConfig.baseURL}/api/news/image?url=${encodeURIComponent(item.image)}`
    : item.image;
  return {
    ...item,
    image,
    publishTime: item.publishTime || item.publish_time,
    categoryId: item.categoryId || item.category_id,
    relatedNews: Array.isArray(item.relatedNews)
      ? item.relatedNews.map(normalizeNews)
      : []
  };
};

export const useNewsStore = defineStore('news', {
  state: () => ({
    categories: [],
    currentCategory: 1,
    newsList: [],
    newsDetail: {},
    loading: false,
    refreshing: false,
    requesting: false,
    finished: false,
    errorMessage: '',
    autoFetched: false,
    page: 1,
    pageSize: 10
  }),

  actions: {
    async getCategories() {
      try {
        const resp = await axios.get(`${apiConfig.baseURL}/api/news/categories`);
        const list = resp?.data?.data || resp?.data || [];
        this.categories = Array.isArray(list) && list.length ? list : DEFAULT_CATEGORIES;
      } catch (error) {
        this.categories = DEFAULT_CATEGORIES;
      }
      return this.categories;
    },

    changeCategory(categoryId) {
      this.currentCategory = categoryId;
      this.page = 1;
      this.newsList = [];
      this.finished = false;
    },

    async getNewsList(refresh = false) {
      if (this.requesting) return;
      if (refresh) {
        this.page = 1;
        this.finished = false;
        this.newsList = [];
      }
      if (this.finished) return;

      this.requesting = true;
      this.loading = true;
      this.refreshing = refresh;
      this.errorMessage = '';
      try {
        const resp = await axios.get(`${apiConfig.baseURL}/api/news/list`, {
          params: {
            categoryId: this.currentCategory,
            page: this.page,
            pageSize: this.pageSize
          }
        });
        const list = resp?.data?.data?.list || resp?.data?.data || [];
        const normalized = Array.isArray(list) ? list.map(normalizeNews) : [];
        this.newsList = this.page === 1 ? normalized : [...this.newsList, ...normalized];
        if (resp?.data?.data?.hasMore === false || normalized.length < this.pageSize) {
          this.finished = true;
        } else {
          this.page += 1;
        }
      } catch (error) {
        console.error('获取新闻列表失败:', error);
        this.errorMessage = '获取新闻列表失败，请确认后端和数据库已经启动';
        this.finished = true;
      } finally {
        this.loading = false;
        this.refreshing = false;
        this.requesting = false;
      }
    },

    async fetchHotNews(options = {}) {
      this.loading = true;
      this.errorMessage = '';
      try {
        const resp = await axios.post(`${apiConfig.baseURL}/api/news/fetch-hot`, null, {
          params: {
            categoryId: options.all ? 0 : (this.currentCategory || 1),
            limit: options.limit || 10,
            replace: Boolean(options.replace),
            useAi: Boolean(options.useAi)
          }
        });
        await this.getNewsList(true);
        return resp?.data?.data;
      } catch (error) {
        console.error('抓取热点新闻失败:', error);
        this.errorMessage = '抓取热点新闻失败，请确认后端可以访问新闻源';
        throw error;
      } finally {
        this.loading = false;
      }
    },

    async autoRefreshHotNews() {
      if (this.autoFetched) {
        await this.getNewsList(true);
        return null;
      }

      this.autoFetched = true;
      await this.getNewsList(true);
      return null;
    },

    async getNewsDetail(newsId) {
      this.newsDetail = {};
      this.errorMessage = '';
      try {
        const resp = await axios.get(`${apiConfig.baseURL}/api/news/detail`, {
          params: { id: newsId }
        });
        const detail = resp?.data?.data || resp?.data;
        if (detail && typeof detail === 'object') {
          this.newsDetail = normalizeNews(detail);
          return this.newsDetail;
        }
      } catch (error) {
        console.error('获取新闻详情失败:', error);
      }

      this.errorMessage = '获取新闻详情失败，请确认后端和数据库已经启动';
      return this.newsDetail;
    }
  }
});
