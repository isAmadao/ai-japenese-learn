import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/Home.vue'
import Favorites from '@/views/Favorites.vue'
import Learned from '@/views/Learned.vue'
import WordDetail from '@/views/WordDetail.vue'
import ArticleDetail from '@/views/ArticleDetail.vue'

const routes = [
  { path: '/', name: 'Home', component: Home, meta: { title: '首页' } },
  { path: '/favorites', name: 'Favorites', component: Favorites, meta: { title: '收藏' } },
  { path: '/learned', name: 'Learned', component: Learned, meta: { title: '已学习' } },
  { path: '/word/:id', name: 'WordDetail', component: WordDetail, meta: { title: '单词详情' } },
  { path: '/article/:id', name: 'ArticleDetail', component: ArticleDetail, meta: { title: '文章详情' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  document.title = `${to.meta.title || 'AI 日本語学習'} — AI 日本語学習`
})

export default router
