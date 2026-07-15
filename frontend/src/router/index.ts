import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/Home.vue'
import Favorites from '@/views/Favorites.vue'
import Learned from '@/views/Learned.vue'
import Mastered from '@/views/Mastered.vue'
import Search from '@/views/Search.vue'
import WordDetail from '@/views/WordDetail.vue'
import ArticleDetail from '@/views/ArticleDetail.vue'
import Login from '@/views/Login.vue'
import Settings from '@/views/Settings.vue'
import AdminLayout from '@/views/admin/AdminLayout.vue'
import AdminDashboard from '@/views/admin/AdminDashboard.vue'
import AdminUsers from '@/views/admin/AdminUsers.vue'
import AdminWords from '@/views/admin/AdminWords.vue'
import AdminArticles from '@/views/admin/AdminArticles.vue'

// Routes that don't require authentication
const publicRoutes = ['/login']

// Store auth module reference to avoid circular dependency
function getIsAdmin(): boolean {
  try {
    const raw = localStorage.getItem('ai_jp_user')
    if (!raw) return false
    const user = JSON.parse(raw)
    return user?.role === 'admin'
  } catch {
    return false
  }
}

const routes = [
  { path: '/login', name: 'Login', component: Login, meta: { title: '登录' } },
  { path: '/', name: 'Home', component: Home, meta: { title: '首页' } },
  { path: '/favorites', name: 'Favorites', component: Favorites, meta: { title: '收藏' } },
  { path: '/learned', name: 'Learned', component: Learned, meta: { title: '已学习' } },
  { path: '/mastered', name: 'Mastered', component: Mastered, meta: { title: '已熟练' } },
  { path: '/search', name: 'Search', component: Search, meta: { title: '搜索' } },
  { path: '/word/:id', name: 'WordDetail', component: WordDetail, meta: { title: '单词详情' } },
  { path: '/article/:id', name: 'ArticleDetail', component: ArticleDetail, meta: { title: '文章详情' } },
  { path: '/settings', name: 'Settings', component: Settings, meta: { title: '个人设置' } },
  {
    path: '/admin',
    component: AdminLayout,
    meta: { title: '管理后台', requiresAdmin: true },
    children: [
      {
        path: '',
        name: 'AdminDashboard',
        component: AdminDashboard,
        meta: { title: '管理后台', adminTitle: '概览' },
      },
      {
        path: 'users',
        name: 'AdminUsers',
        component: AdminUsers,
        meta: { title: '用户管理', adminTitle: '用户管理' },
      },
      {
        path: 'words',
        name: 'AdminWords',
        component: AdminWords,
        meta: { title: '单词管理', adminTitle: '单词管理' },
      },
      {
        path: 'articles',
        name: 'AdminArticles',
        component: AdminArticles,
        meta: { title: '文章管理', adminTitle: '文章管理' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  document.title = `${to.meta.title || 'AI 日本語学習'} — AI 日本語学習`

  // Auth guard: redirect to login if not authenticated
  if (!publicRoutes.includes(to.path)) {
    const token = localStorage.getItem('ai_jp_token')
    if (!token) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }

  // Admin guard: require admin role
  if (to.meta?.requiresAdmin && !getIsAdmin()) {
    return { path: '/' }
  }
})

export default router
