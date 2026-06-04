<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { fetchLearned, fetchLearnedTypeCounts } from '@/api'
import { speakJapanese } from '@/utils/speech'
import type { WordResponse, LearnedTypeCounts } from '@/types'

const router = useRouter()

const words = ref<WordResponse[]>([])
const total = ref(0)
const page = ref(1)
const totalPages = ref(1)
const pageSize = 30
const loading = ref(false)
const error = ref<string | null>(null)
const activeType = ref<string | null>(null)
const typeCounts = ref<LearnedTypeCounts>({ N5: 0, N4: 0, N3: 0, N2: 0, N1: 0 })

const typeTabs = [
  { key: null, label: 'All' },
  { key: 'N5', label: 'N5' },
  { key: 'N4', label: 'N4' },
  { key: 'N3', label: 'N3' },
  { key: 'N2', label: 'N2' },
  { key: 'N1', label: 'N1' },
]

onMounted(async () => {
  await loadTypeCounts()
  await loadWords()
})

watch(activeType, () => { page.value = 1; loadWords() })
watch(page, () => loadWords())

async function loadTypeCounts() {
  try {
    typeCounts.value = await fetchLearnedTypeCounts()
  } catch { /* silent */ }
}

async function loadWords() {
  loading.value = true
  error.value = null
  try {
    const data = await fetchLearned(activeType.value || undefined, page.value, pageSize)
    words.value = data.words
    total.value = data.total
    totalPages.value = data.total_pages
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '加载失败'
    words.value = []
  } finally {
    loading.value = false
  }
}

function goToDetail(id: number) {
  router.push(`/word/${id}`)
}

function tabCount(key: string | null): string {
  if (!key) return String(Object.values(typeCounts.value).reduce((a, b) => a + b, 0))
  return String(typeCounts.value[key as string] || 0)
}
</script>

<template>
  <div class="learned">
    <div class="page-header">
      <h1>✅ 已学习</h1>
    </div>

    <!-- Type tabs -->
    <div class="type-tabs">
      <button
        v-for="tab in typeTabs"
        :key="tab.key || 'all'"
        class="type-tab"
        :class="{ active: activeType === tab.key }"
        @click="activeType = tab.key"
      >
        {{ tab.label }}
        <span class="tab-count">{{ tabCount(tab.key) }}</span>
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading && words.length === 0" class="loading">加载中</div>

    <!-- Error -->
    <div v-else-if="error" class="error-msg">
      <p>⚠ {{ error }}</p>
      <button class="btn btn-primary btn-sm" style="margin-top: 12px" @click="loadWords">重试</button>
    </div>

    <!-- Empty -->
    <div v-else-if="words.length === 0" class="empty-state">
      <p>还没有已学习的单词</p>
      <p class="hint">在收藏页中将单词标记为"已学习"后，它们会出现在这里</p>
      <router-link to="/favorites" class="btn btn-accent btn-sm" style="margin-top: 12px; text-decoration: none">
        去收藏页
      </router-link>
    </div>

    <!-- Word Grid -->
    <div v-else class="word-grid">
      <div
        v-for="word in words"
        :key="word.id"
        class="word-card card"
        @click="goToDetail(word.id)"
      >
        <div class="card-header">
          <h3 class="jp-text">{{ word.name }}</h3>
          <span class="kana">{{ word.kana }}</span>
        </div>
        <p class="translation">{{ word.translation }}</p>
        <div class="card-footer">
          <span v-if="word.type" class="type-badge">{{ word.type }}</span>
          <button class="speak-btn-sm" title="朗读" @click.stop="speakJapanese(word.name)">🔊</button>
        </div>
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="pagination">
      <button :disabled="page <= 1" @click="page--">上一页</button>
      <span class="page-info">{{ page }} / {{ totalPages }}</span>
      <button :disabled="page >= totalPages" @click="page++">下一页</button>
    </div>
  </div>
</template>

<style scoped>
.learned { max-width: 1000px; margin: 0 auto; }

.type-tabs {
  display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap;
}
.type-tab {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 16px; border: 2px solid var(--border);
  border-radius: 20px; background: white; cursor: pointer;
  font-weight: 600; font-size: 0.9rem; transition: all 0.2s;
}
.type-tab:hover { border-color: var(--accent); color: var(--accent); }
.type-tab.active { border-color: var(--primary); background: var(--primary); color: white; }
.tab-count {
  font-size: 0.7rem; font-weight: 400;
  background: rgba(255,255,255,0.2); padding: 1px 7px;
  border-radius: 10px;
}
.type-tab:not(.active) .tab-count { background: var(--bg); color: var(--text-light); }

.word-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}
@media (min-width: 800px) {
  .word-grid { grid-template-columns: repeat(6, 1fr); }
}
@media (max-width: 600px) {
  .word-grid { grid-template-columns: repeat(2, 1fr); }
}

.word-card { cursor: pointer; transition: all 0.2s; }
.word-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-hover); }

.card-header { margin-bottom: 4px; }
.jp-text { font-size: 1.1rem; font-weight: 700; margin-bottom: 1px; }
.kana { font-size: 0.8rem; color: var(--text-light); }
.translation { font-size: 0.85rem; color: var(--accent); margin-bottom: 8px; }

.card-footer {
  display: flex; justify-content: space-between; align-items: center;
}
.type-badge {
  font-size: 0.65rem; font-weight: 600; padding: 2px 8px;
  border-radius: 10px; background: var(--accent-light); color: var(--accent);
}
.speak-btn-sm {
  background: none; border: 1px solid var(--border); border-radius: 50%;
  width: 28px; height: 28px; cursor: pointer; font-size: 0.8rem;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
}
.speak-btn-sm:hover { background: var(--accent-light); border-color: var(--accent); }

.empty-state { text-align: center; padding: 60px; color: var(--text-light); }
.hint { font-size: 0.85rem; margin-top: 8px; }

.page-info { padding: 8px 12px; color: var(--text-light); font-size: 0.9rem; }
</style>
