<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchAdminUsers, adminDeleteUser, adminRestoreUser } from '@/api'
import type { AdminUserItem, AdminUserListResponse } from '@/api'

const PAGE_SIZE = 20

const data = ref<AdminUserListResponse | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const page = ref(1)
const showDeleted = ref(false)
const actionMsg = ref('')

async function load() {
  loading.value = true
  error.value = null
  try {
    data.value = await fetchAdminUsers(page.value, PAGE_SIZE, showDeleted.value)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function goPage(p: number) {
  page.value = p
  load()
}

function toggleDeleted() {
  showDeleted.value = !showDeleted.value
  page.value = 1
  load()
}

async function handleDelete(u: AdminUserItem) {
  if (!confirm(`确定要删除用户「${u.username}」吗？`)) return
  actionMsg.value = ''
  try {
    const r = await adminDeleteUser(u.id)
    actionMsg.value = r.message
    load()
  } catch (e: any) {
    actionMsg.value = e?.response?.data?.detail || '删除失败'
  }
}

async function handleRestore(u: AdminUserItem) {
  actionMsg.value = ''
  try {
    const r = await adminRestoreUser(u.id)
    actionMsg.value = r.message
    load()
  } catch (e: any) {
    actionMsg.value = e?.response?.data?.detail || '恢复失败'
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1>👥 用户管理</h1>
    </div>

    <div v-if="actionMsg" class="action-msg">{{ actionMsg }}</div>

    <div class="toolbar">
      <label class="toggle-label">
        <input type="checkbox" :checked="showDeleted" @change="toggleDeleted" />
        <span>显示已删除用户</span>
      </label>
    </div>

    <div v-if="loading && !data" class="loading">加载中</div>
    <div v-else-if="error" class="error-msg">⚠ {{ error }}</div>

    <template v-else-if="data">
      <div class="table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th class="col-id">ID</th>
              <th>用户名</th>
              <th>邮箱</th>
              <th class="col-role">角色</th>
              <th class="col-verify">验证</th>
              <th class="col-status">状态</th>
              <th class="col-num">收藏</th>
              <th class="col-num">已学</th>
              <th class="col-date">注册时间</th>
              <th class="col-action">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in data.users" :key="u.id" :class="{ deleted: u.deleted }">
              <td class="col-id">{{ u.id }}</td>
              <td>
                <span class="user-name">{{ u.username }}</span>
              </td>
              <td class="col-email">{{ u.email || '-' }}</td>
              <td class="col-role">
                <span class="role-badge" :class="{ admin: u.role === 'admin' }">
                  {{ u.role }}
                </span>
              </td>
              <td class="col-verify">
                <span v-if="u.is_verified" class="verified-badge">✓</span>
                <span v-else class="unverified-badge">—</span>
              </td>
              <td class="col-status">
                <span v-if="u.deleted" class="status-deleted">已注销</span>
                <span v-else class="status-active">正常</span>
              </td>
              <td class="col-num">{{ u.favorite_count }}</td>
              <td class="col-num">{{ u.learned_count }}</td>
              <td class="col-date">{{ u.created_at ? new Date(u.created_at).toLocaleDateString('zh-CN') : '-' }}</td>
              <td class="col-action">
                <button v-if="!u.deleted && u.role !== 'admin'" class="btn-action btn-delete"
                  @click="handleDelete(u)">删除</button>
                <button v-if="u.deleted" class="btn-action btn-restore"
                  @click="handleRestore(u)">恢复</button>
              </td>
            </tr>
            <tr v-if="data.users.length === 0">
              <td colspan="10" class="empty-row">暂无用户</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div v-if="data.total_pages > 1" class="pagination">
        <button :disabled="page <= 1" @click="goPage(page - 1)">← 上一页</button>
        <template v-for="p in data.total_pages" :key="p">
          <button
            v-if="p === 1 || p === data.total_pages || Math.abs(p - page) <= 2"
            :class="{ active: p === page }"
            @click="goPage(p)"
          >
            {{ p }}
          </button>
          <span v-else-if="p === page - 3 || p === page + 3" class="page-dots">...</span>
        </template>
        <button :disabled="page >= data.total_pages" @click="goPage(page + 1)">下一页 →</button>
      </div>

      <div class="table-info">
        共 {{ data.total }} 个用户，第 {{ data.page }}/{{ data.total_pages }} 页
      </div>
    </template>
  </div>
</template>

<style scoped>
.page { max-width: 1020px; }
.page-header { margin-bottom: 16px; }
.page-header h1 {
  font-family: 'Press Start 2P', monospace;
  font-size: clamp(0.6rem, 2vw, 0.8rem);
  color: var(--cream);
  text-shadow: 2px 2px 0 var(--warm-brown-dark);
  letter-spacing: 2px;
}
.action-msg {
  text-align: center;
  padding: 6px 12px;
  margin-bottom: 8px;
  background: var(--bg-hint);
  border: 2px solid var(--golden);
  color: var(--text);
  font-size: 0.8rem;
}
.toolbar {
  margin-bottom: 12px;
  display: flex;
  align-items: center;
}
.toggle-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8rem;
  color: var(--cream);
  cursor: pointer;
  text-shadow: 1px 1px 0 rgba(0,0,0,0.15);
}
.toggle-label input {
  accent-color: var(--golden);
}

.table-wrap {
  overflow-x: auto;
  border: 4px solid var(--wood-dark);
  box-shadow: inset -3px -3px 0 var(--wood-dark), inset 3px 3px 0 var(--wood-light);
}
.admin-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--bg-card);
  font-size: 0.85rem;
}
.admin-table th {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.5rem;
  letter-spacing: 1px;
  padding: 10px 12px;
  text-align: left;
  background: var(--wood-mid);
  color: var(--cream);
  border-bottom: 3px solid var(--wood-dark);
  text-shadow: 1px 1px 0 rgba(0,0,0,0.3);
  white-space: nowrap;
}
.admin-table td {
  padding: 10px 12px;
  border-bottom: 2px solid var(--wood-light);
  color: var(--text);
}
.admin-table tr:last-child td { border-bottom: none; }
.admin-table tr:hover td { background: var(--bg-hint); }
.admin-table tr.deleted td {
  opacity: 0.5;
  text-decoration: line-through;
}
.admin-table tr.deleted:hover td { opacity: 0.7; }

.col-id { width: 40px; text-align: center; color: var(--text-muted); font-size: 0.8rem; }
.col-role { width: 60px; text-align: center; }
.col-num { width: 50px; text-align: center; font-family: 'Press Start 2P', monospace; font-size: 0.5rem; }
.col-date { width: 90px; white-space: nowrap; font-size: 0.8rem; color: var(--text-light); }
.col-verify { width: 40px; text-align: center; }
.col-status { width: 60px; text-align: center; }
.col-action { width: 70px; text-align: center; }

.user-name { font-weight: 600; }

.role-badge {
  display: inline-block;
  font-family: 'Press Start 2P', monospace;
  font-size: 0.45rem;
  padding: 3px 8px;
  background: var(--grass-light);
  color: var(--text);
  border: 2px solid var(--grass-dark);
  letter-spacing: 1px;
}
.role-badge.admin {
  background: var(--golden);
  border-color: var(--warm-brown-dark);
}
.verified-badge { font-size: 0.8rem; color: var(--grass-dark); font-weight: bold; }
.unverified-badge { font-size: 0.7rem; color: var(--text-muted); }
.col-email {
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.8rem;
  color: var(--text-light);
}

.status-active { color: var(--grass-dark); font-size: 0.75rem; }
.status-deleted { color: var(--danger); font-size: 0.75rem; }

.btn-action {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.4rem;
  padding: 4px 8px;
  border: 2px solid;
  cursor: pointer;
  letter-spacing: 1px;
  transition: all 0.05s step-start;
}
.btn-delete {
  background: var(--cream);
  color: var(--danger);
  border-color: var(--danger);
}
.btn-delete:hover {
  background: var(--danger);
  color: #fff;
}
.btn-restore {
  background: var(--cream);
  color: var(--grass-dark);
  border-color: var(--grass-dark);
}
.btn-restore:hover {
  background: var(--grass-dark);
  color: #fff;
}

.empty-row {
  text-align: center;
  padding: 32px 12px !important;
  color: var(--text-muted);
}
.table-info {
  margin-top: 12px;
  text-align: right;
  font-size: 0.75rem;
  color: var(--cream);
  text-shadow: 1px 1px 0 rgba(0,0,0,0.15);
}
</style>
