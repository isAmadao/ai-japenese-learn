<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const navItems = [
  { path: '/admin', label: '📊 概览', icon: '📊' },
  { path: '/admin/users', label: '👥 用户', icon: '👥' },
  { path: '/admin/words', label: '📖 单词', icon: '📖' },
  { path: '/admin/articles', label: '📄 文章', icon: '📄' },
]

function handleLogout() {
  auth.logout()
  router.push('/login')
}

function goHome() {
  router.push('/')
}
</script>

<template>
  <div class="admin-shell">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-header" @click="goHome">
        <span class="sidebar-logo">🌾</span>
        <span class="sidebar-title">管理</span>
      </div>

      <nav class="sidebar-nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="sidebar-link"
          :class="{ active: $route.path === item.path }"
        >
          <span class="sidebar-icon">{{ item.icon }}</span>
          <span class="sidebar-label">{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
        <div class="sidebar-user">
          <span class="sidebar-user-icon">👤</span>
          <span class="sidebar-user-name">{{ auth.user?.username }}</span>
          <span class="sidebar-user-badge">admin</span>
        </div>
      </div>
    </aside>

    <!-- Main area -->
    <div class="main-area">
      <!-- Top bar -->
      <header class="topbar">
        <div class="topbar-left">
          <span class="topbar-breadcrumb">管理后台</span>
          <span class="topbar-sep">/</span>
          <span class="topbar-current">{{ $route.meta?.adminTitle || '概览' }}</span>
        </div>
        <div class="topbar-right">
          <button class="topbar-btn" @click="goHome" title="返回主站">
            🏠 主站
          </button>
          <button class="topbar-btn topbar-logout" @click="handleLogout">
            🚪 登出
          </button>
        </div>
      </header>

      <!-- Content -->
      <main class="admin-content">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<style scoped>
.admin-shell {
  display: flex;
  min-height: calc(100vh - 40px);
  gap: 0;
}

/* ===== Sidebar ===== */
.sidebar {
  width: 200px;
  flex-shrink: 0;
  background: var(--wood-mid);
  border: 4px solid var(--wood-dark);
  border-right-width: 4px;
  box-shadow:
    inset -3px -3px 0 var(--wood-dark),
    inset 3px 3px 0 var(--wood-light);
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 20px;
  align-self: flex-start;
  max-height: calc(100vh - 40px);
}

.sidebar-header {
  padding: 16px 14px;
  border-bottom: 3px solid var(--wood-dark);
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: background 0.05s step-start;
}
.sidebar-header:hover {
  background: var(--warm-brown-dark);
}
.sidebar-logo {
  font-size: 1.5rem;
}
.sidebar-title {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.7rem;
  color: var(--cream);
  text-shadow: 2px 2px 0 var(--warm-brown-dark);
  letter-spacing: 2px;
}

.sidebar-nav {
  flex: 1;
  padding: 8px 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sidebar-link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  color: var(--cream);
  text-decoration: none;
  font-weight: 700;
  font-size: 0.9rem;
  border: 2px solid transparent;
  border-left: 4px solid transparent;
  transition: all 0.05s step-start;
  text-shadow: 1px 1px 0 rgba(0,0,0,0.3);
}
.sidebar-link:hover {
  background: var(--warm-brown-dark);
  border-color: var(--warm-brown-dark);
}
.sidebar-link.active,
.sidebar-link.router-link-active {
  background: var(--warm-brown-dark);
  border-left-color: var(--golden);
  border-top-color: var(--warm-brown-dark);
  border-right-color: var(--warm-brown-dark);
  border-bottom-color: var(--warm-brown-dark);
  box-shadow: inset -2px -2px 0 rgba(0,0,0,0.2);
}

.sidebar-icon {
  font-size: 1rem;
  width: 24px;
  text-align: center;
}
.sidebar-label {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.55rem;
  letter-spacing: 1px;
}

.sidebar-footer {
  padding: 12px 14px;
  border-top: 3px solid var(--wood-dark);
}
.sidebar-user {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.sidebar-user-icon {
  font-size: 0.9rem;
}
.sidebar-user-name {
  font-size: 0.75rem;
  color: var(--cream);
  font-weight: 600;
  text-shadow: 1px 1px 0 rgba(0,0,0,0.2);
}
.sidebar-user-badge {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.4rem;
  padding: 2px 6px;
  background: var(--golden);
  color: var(--text);
  border: 2px solid var(--warm-brown-dark);
  letter-spacing: 1px;
}

/* ===== Main area ===== */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: var(--bg-card);
  border: 4px solid var(--wood-dark);
  box-shadow:
    inset -3px -3px 0 var(--wood-dark),
    inset 3px 3px 0 var(--wood-light);
  margin-bottom: 16px;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.topbar-breadcrumb {
  color: var(--text-light);
  font-size: 0.8rem;
}
.topbar-sep {
  color: var(--text-muted);
  font-size: 0.8rem;
}
.topbar-current {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.55rem;
  color: var(--text);
  letter-spacing: 1px;
}

.topbar-right {
  display: flex;
  gap: 8px;
}
.topbar-btn {
  padding: 8px 14px;
  font-family: 'Press Start 2P', monospace;
  font-size: 0.5rem;
  border: 3px solid var(--wood-dark);
  background: var(--cream);
  color: var(--warm-brown);
  cursor: pointer;
  transition: all 0.05s step-start;
  box-shadow: 2px 2px 0 var(--wood-dark);
}
.topbar-btn:hover {
  background: var(--golden-light);
  border-color: var(--golden);
}
.topbar-logout:hover {
  background: #F0D0D0;
  border-color: var(--danger);
  color: var(--danger);
}

.admin-content {
  flex: 1;
  padding: 0 4px;
}
</style>
