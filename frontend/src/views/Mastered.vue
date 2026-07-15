<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { fetchMastered, fetchMasteredTypeCounts } from '@/api'
import { speakJapanese, stopSpeech } from '@/utils/speech'
import type { WordResponse, LearnedTypeCounts } from '@/types'
import ErrorMessage from '@/components/ErrorMessage.vue'

const router = useRouter()

const words = ref<WordResponse[]>([])
const total = ref(0)
const page = ref(1)
const totalPages = ref(1)
const pageSize = 30
const loading = ref(false)
const error = ref<string | null>(null)
const actionMsg = ref<string | null>(null)
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

onUnmounted(() => { stopSpeech() })

async function loadTypeCounts() {
  try { typeCounts.value = await fetchMasteredTypeCounts() } catch { /* silent */ }
}

async function loadWords() {
  loading.value = true
  error.value = null
  try {
    const data = await fetchMastered(activeType.value || undefined, page.value, pageSize)
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
  <div class="mastered">
    <div class="page-header">
      <h1>🎯 已熟练</h1>
    </div>

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

    <p v-if="actionMsg" class="msg-success">{{ actionMsg }}</p>

    <div v-if="loading && words.length === 0" class="loading">加载中</div>
    <div v-if="loading && words.length > 0" class="loading-overlay">
      <span class="loading-spinner"></span>
    </div>

    <ErrorMessage v-else-if="error" :message="error" @retry="loadWords" />

    <div v-else-if="words.length === 0 && !loading" class="empty-state">
      <p>🏆 还没有已熟练的单词</p>
      <p class="hint">
        AI 生成的单词会自动标记为"已熟练"<br>
        你也可以在已学习页中将单词标记为"已熟练"
      </p>
      <router-link to="/" class="btn btn-primary btn-sm" style="margin-top: 12px">
        去首页生成新词
      </router-link>
    </div>

    <div v-else class="word-grid">
      <div
        v-for="word in words"
        :key="word.id"
        class="word-card card"
        @click="goToDetail(word.id)"
      >
        <div class="card-stripe"></div>
        <div class="card-header">
          <div class="card-header-left">
            <h3 class="jp-text">{{ word.name }}</h3>
            <span class="kana">{{ word.kana }}</span>
          </div>
          <button class="speak-btn-sm" title="朗读" @click.stop="speakJapanese(word.name)">🔊</button>
        </div>
        <p class="translation">{{ word.translation }}</p>
        <div v-if="word.example_sentences && word.example_sentences.length > 0" class="sentences">
          <div v-for="(sent, si) in word.example_sentences.slice(0, 1)" :key="si" class="sentence">
            <span class="sent-jp">{{ sent.japanese }}</span>
            <span class="sent-cn">{{ sent.chinese }}</span>
          </div>
        </div>
        <div class="card-footer">
          <span v-if="word.type" class="type-badge">{{ word.type }}</span>
        </div>
      </div>
    </div>

    <div v-if="totalPages > 1" class="pagination">
      <button :disabled="page <= 1" @click="page--">上一页</button>
      <span class="page-info">{{ page }} / {{ totalPages }}</span>
      <button :disabled="page >= totalPages" @click="page++">下一页</button>
    </div>
  </div>
</template>

<style scoped>
.mastered { max-width: 1000px; margin: 0 auto; }

.type-tabs {
  display: flex; gap: 6px; margin-bottom: 20px; flex-wrap: wrap;
}
.type-tab {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 14px;
  font-family: 'Press Start 2P', monospace;
  font-size: 0.4rem;
  border: 3px solid var(--wood-dark);
  background: var(--cream);
  cursor: pointer;
  font-weight: 400;
  transition: all 0.05s step-start;
  color: var(--text);
  box-shadow: 2px 2px 0 var(--wood-dark);
}
.type-tab:hover { background: var(--wood-light); }
.type-tab.active {
  background: var(--golden);
  color: var(--text);
  border-color: #C8A030;
  box-shadow: 2px 2px 0 #C8A030;
}
.tab-count {
  font-size: 0.35rem;
  font-weight: 400;
  background: rgba(0,0,0,0.08);
  padding: 2px 6px;
  border: 1px solid currentColor;
}
.loading-overlay {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.loading-spinner {
  width: 16px;
  height: 16px;
  border: 3px solid var(--wood-light);
  border-top-color: var(--golden);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.msg-success {
  color: var(--grass-dark);
  font-size: 0.8rem;
  text-align: center;
  padding: 8px;
  background: rgba(74, 124, 89, 0.08);
  border: 2px solid var(--grass-dark);
  margin-bottom: 12px;
}
.sentences {
  margin: 6px 0 10px;
  padding: 6px 8px;
  background: var(--cream);
  border: 2px solid var(--wood-light);
  font-size: 0.75rem;
}
.sentence {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.sent-jp { color: var(--text); font-weight: 500; }
.sent-cn { color: var(--text-light); font-size: 0.7rem; }
.type-tab.active .tab-count {
  background: rgba(0,0,0,0.1);
}

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

.word-card {
  cursor: pointer;
  transition: all 0.15s step-start;
  position: relative;
  overflow: hidden;
}
.word-card:hover {
  transform: translateY(-2px);
  box-shadow:
    inset -3px -3px 0 var(--wood-dark),
    inset 3px 3px 0 var(--wood-light),
    3px 4px 0 rgba(60,40,20,0.15);
}

.card-stripe {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--golden), var(--pink));
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 4px;
  gap: 8px;
}
.card-header-left { flex: 1; min-width: 0; }
.jp-text { font-size: 1.3rem; font-weight: 700; margin-bottom: 2px; }
.kana { font-size: 0.9rem; color: var(--text-light); }
.translation { font-size: 0.95rem; color: var(--warm-brown); font-weight: 600; margin-bottom: 8px; }

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.speak-btn-sm {
  background: var(--cream);
  border: 3px solid var(--wood-dark);
  width: 30px;
  height: 30px;
  cursor: pointer;
  font-size: 0.8rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.05s step-start;
  box-shadow: 2px 2px 0 var(--wood-dark);
}
.speak-btn-sm:hover {
  background: var(--golden-light);
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 var(--wood-dark);
}

.empty-state {
  text-align: center;
  padding: 60px;
  color: var(--text-light);
  background: var(--bg-card);
  border: 4px solid var(--wood-dark);
  box-shadow:
    inset -3px -3px 0 var(--wood-dark),
    inset 3px 3px 0 var(--wood-light);
  max-width: 450px;
  margin: 40px auto;
}
.hint { font-size: 0.85rem; margin-top: 8px; }

.page-info {
  padding: 8px 12px;
  color: var(--cream);
  font-size: 0.75rem;
  font-family: 'Press Start 2P', monospace;
}
</style>
