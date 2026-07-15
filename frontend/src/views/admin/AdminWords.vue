<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchAdminWords } from '@/api'
import type { AdminWordListResponse } from '@/api'

const PAGE_SIZE = 20

const data = ref<AdminWordListResponse | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const page = ref(1)
const typeFilter = ref<string | undefined>(undefined)

const levels = ['', 'N5', 'N4', 'N3', 'N2', 'N1']
const levelLabels: Record<string, string> = {
  '': '全部',
  N5: 'N5 入门',
  N4: 'N4 基础',
  N3: 'N3 中级',
  N2: 'N2 进阶',
  N1: 'N1 精通',
}

async function load() {
  loading.value = true
  error.value = null
  try {
    data.value = await fetchAdminWords(page.value, PAGE_SIZE, typeFilter.value || undefined)
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

function setType(t: string) {
  typeFilter.value = t || undefined
  page.value = 1
  load()
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1>📖 单词管理</h1>
    </div>

    <!-- Level filter pills -->
    <div class="level-selector">
      <button
        v-for="lvl in levels"
        :key="lvl"
        class="level-btn"
        :class="{ selected: (typeFilter || '') === lvl }"
        @click="setType(lvl)"
      >
        {{ levelLabels[lvl] || lvl }}
      </button>
    </div>

    <div v-if="loading && !data" class="loading">加载中</div>
    <div v-else-if="error" class="error-msg">⚠ {{ error }}</div>

    <template v-else-if="data">
      <div class="table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th class="col-id">ID</th>
              <th>日语</th>
              <th>假名</th>
              <th>释义</th>
              <th class="col-level">级别</th>
              <th class="col-num">收藏</th>
              <th class="col-date">创建时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="w in data.words" :key="w.id">
              <td class="col-id">{{ w.id }}</td>
              <td class="col-jp">
                <span class="jp-text">{{ w.name }}</span>
              </td>
              <td class="col-kana">{{ w.kana }}</td>
              <td class="col-trans">{{ w.translation }}</td>
              <td class="col-level">
                <span v-if="w.type" class="type-badge">{{ w.type }}</span>
                <span v-else class="no-type">-</span>
              </td>
              <td class="col-num">{{ w.favorite_count }}</td>
              <td class="col-date">{{ w.created_at ? new Date(w.created_at).toLocaleDateString('zh-CN') : '-' }}</td>
            </tr>
            <tr v-if="data.words.length === 0">
              <td colspan="7" class="empty-row">暂无单词</td>
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
        共 {{ data.total }} 个单词，第 {{ data.page }}/{{ data.total_pages }} 页
      </div>
    </template>
  </div>
</template>

<style scoped>
.page { max-width: 960px; }
.page-header { margin-bottom: 16px; }
.page-header h1 {
  font-family: 'Press Start 2P', monospace;
  font-size: clamp(0.6rem, 2vw, 0.8rem);
  color: var(--cream);
  text-shadow: 2px 2px 0 var(--warm-brown-dark);
  letter-spacing: 2px;
}

.table-wrap {
  overflow-x: auto;
  border: 4px solid var(--wood-dark);
  box-shadow:
    inset -3px -3px 0 var(--wood-dark),
    inset 3px 3px 0 var(--wood-light);
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

.admin-table tr:last-child td {
  border-bottom: none;
}

.admin-table tr:hover td {
  background: var(--bg-hint);
}

.col-id { width: 50px; text-align: center; color: var(--text-muted); font-size: 0.8rem; }
.col-jp { min-width: 100px; }
.col-kana { min-width: 100px; color: var(--text-light); }
.col-trans { min-width: 120px; }
.col-level { width: 70px; text-align: center; }
.col-num { width: 60px; text-align: center; font-family: 'Press Start 2P', monospace; font-size: 0.5rem; }
.col-date { width: 100px; white-space: nowrap; font-size: 0.8rem; color: var(--text-light); }

.jp-text {
  font-weight: 700;
  font-size: 1rem;
}

.no-type {
  color: var(--text-muted);
  font-size: 0.8rem;
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
