<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { fetchFavorites, generateArticleStream, markAsLearned, getApiKey, getPexelsKey } from '@/api'
import type { WordResponse } from '@/types'
import WordCard from '@/components/WordCard.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import { TYPE_TABS } from '@/utils/constants'

const router = useRouter()

const words = ref<WordResponse[]>([])
const total = ref(0)
const page = ref(1)
const totalPages = ref(1)
const pageSize = 30
const loading = ref(false)
const error = ref<string | null>(null)

const selecting = ref(false)
const selectedIds = ref<Set<number>>(new Set())
const showLevelModal = ref(false)
const articleLevel = ref('')
const contentType = ref('')
const articleStyle = ref('')
const articleSource = ref('')
const generating = ref(false)
const genError = ref<string | null>(null)
const streamingContent = ref('')
const showStreaming = ref(false)
const activeType = ref<string | null>(null)

onMounted(() => { loadFavorites() })

watch(activeType, () => { page.value = 1; loadFavorites() })

async function loadFavorites() {
  loading.value = true
  error.value = null
  try {
    const data = await fetchFavorites(page.value, pageSize, activeType.value || undefined)
    words.value = data.words
    total.value = data.total
    totalPages.value = data.total_pages
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '加载收藏失败'
    words.value = []
  } finally {
    loading.value = false
  }
}

function goToPage(p: number) {
  page.value = p
  loadFavorites()
}

async function handleMarkLearned(wordId: number) {
  try {
    await markAsLearned(wordId)
    loadFavorites()
  } catch { /* silent */ }
}

function goToDetail(id: number) {
  if (!selecting.value) {
    router.push(`/word/${id}`)
  }
}

function startSelecting() {
  selecting.value = true
  selectedIds.value = new Set()
}

function cancelSelecting() {
  selecting.value = false
  selectedIds.value = new Set()
}

function toggleSelect(id: number) {
  const s = new Set(selectedIds.value)
  if (s.has(id)) { s.delete(id) } else { s.add(id) }
  selectedIds.value = s
}

function confirmSelection() {
  if (selectedIds.value.size === 0) return
  showLevelModal.value = true
  articleLevel.value = ''
  contentType.value = ''
  articleStyle.value = ''
  articleSource.value = ''
  genError.value = null
}

function selectLevel(level: string) {
  articleLevel.value = level
}

async function confirmGenerate() {
  if (!articleLevel.value) return

  // Check API key before attempting LLM call
  if (!getApiKey()) {
    genError.value = '请先在首页设置 API Key 后才能使用 AI 生成功能'
    showStreaming.value = true
    generating.value = false
    return
  }

  showLevelModal.value = false
  showStreaming.value = true
  generating.value = true
  genError.value = null
  streamingContent.value = ''

  await generateArticleStream(
    [...selectedIds.value],
    articleLevel.value,
    getApiKey(),
    (text) => { streamingContent.value += text },
    (articleId) => {
      generating.value = false
      showStreaming.value = false
      selecting.value = false
      selectedIds.value = new Set()
      router.push(`/article/${articleId}`)
    },
    (message) => {
      generating.value = false
      genError.value = message
    },
    {
      content_type: contentType.value || undefined,
      style: articleStyle.value || undefined,
      source: articleSource.value || undefined,
      pexels_key: getPexelsKey() || undefined,
    },
  )
}

function cancelStreaming() {
  showStreaming.value = false
  generating.value = false
}
</script>

<template>
  <div class="favorites">
    <div class="page-header">
      <h1>⭐ 我的收藏</h1>
      <div class="header-actions">
        <button
          v-if="!selecting"
          class="btn btn-accent"
          @click="startSelecting"
          :disabled="words.length === 0"
        >
          📝 生成文章
        </button>
        <template v-else>
          <button class="btn btn-outline" @click="cancelSelecting">取消</button>
          <button
            class="btn btn-primary"
            :disabled="selectedIds.size === 0"
            @click="confirmSelection"
          >
            确认（已选 {{ selectedIds.size }} 个）
          </button>
        </template>
      </div>
    </div>

    <p v-if="selecting" class="select-hint">
      🌾 请勾选要用于生成文章的单词，然后点击"确认"
    </p>

    <div class="type-tabs">
      <button
        v-for="tab in TYPE_TABS"
        :key="tab.key || 'all'"
        class="type-tab"
        :class="{ active: activeType === tab.key }"
        :disabled="selecting"
        @click="activeType = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <div v-if="loading && words.length === 0" class="loading">加载中</div>

    <!-- Pagination loading overlay -->
    <div v-if="loading && words.length > 0" class="loading-overlay">
      <span class="loading-spinner"></span>
      <span>加载中...</span>
    </div>

    <ErrorMessage v-else-if="error" :message="error" @retry="loadFavorites" />

    <div v-else-if="words.length === 0 && !loading" class="empty-state">
      <p>📭 还没有收藏的单词</p>
      <p class="hint">去首页发现并收藏你的第一个单词吧！</p>
      <router-link to="/" class="btn btn-primary btn-sm" style="margin-top: 12px">
        去首页
      </router-link>
    </div>

    <div v-else class="word-grid">
      <div v-for="word in words" :key="word.id" class="grid-item">
        <WordCard
          :word="word"
          :show-favorite="false"
          :selectable="selecting"
          :selected="selectedIds.has(word.id)"
          @select="toggleSelect"
          @click="goToDetail"
        />
        <button
          v-if="!selecting"
          class="btn-learned"
          @click.stop="handleMarkLearned(word.id)"
          title="标记为已学习"
        >
          ✅ 已学习
        </button>
      </div>
    </div>

    <div v-if="totalPages > 1" class="pagination">
      <button :disabled="page <= 1" @click="goToPage(page - 1)">上一页</button>
      <button
        v-for="p in totalPages"
        :key="p"
        :class="{ active: p === page }"
        @click="goToPage(p)"
      >{{ p }}</button>
      <button :disabled="page >= totalPages" @click="goToPage(page + 1)">下一页</button>
    </div>

    <!-- Level Selection Modal -->
    <div v-if="showLevelModal" class="modal-overlay" @click.self="showLevelModal = false">
      <div class="modal gen-modal">
        <h2>选择文章级别</h2>
        <p style="color:var(--wood-light);margin-bottom:12px;font-size:0.85rem;">
          已选 {{ selectedIds.size }} 个单词
        </p>
        <div class="level-selector">
          <button
            v-for="level in ['N5', 'N4', 'N3', 'N2', 'N1']"
            :key="level"
            class="level-btn"
            :class="{ selected: articleLevel === level }"
            @click="selectLevel(level)"
          >
            {{ level }}
            <span style="display:block;font-size:0.35rem;font-weight:400;margin-top:3px;letter-spacing:0">
              {{ { N5: '最简单', N4: '简单', N3: '中等', N2: '较难', N1: '困难' }[level] }}
            </span>
          </button>
        </div>

        <h2 style="margin-top:20px;">内容类型</h2>
        <div class="chip-group">
          <button v-for="ct in [{v:'',l:'不限定'},{v:'anime',l:'动漫'},{v:'drama',l:'日剧'},{v:'music',l:'歌曲'},{v:'daily',l:'日常生活'}]"
            :key="ct.v" class="chip-btn"
            :class="{ active: contentType === ct.v }"
            @click="contentType = ct.v">{{ ct.l }}</button>
        </div>

        <h2 style="margin-top:16px;">文章风格</h2>
        <div class="chip-group">
          <button v-for="st in [{v:'',l:'不限'},{v:'emotional',l:'感情'},{v:'funny',l:'搞笑'},{v:'adventure',l:'冒险'},{v:'epic',l:'史诗'},{v:'plain',l:'朴素'},{v:'suspense',l:'悬疑'},{v:'fantasy',l:'奇幻'}]"
            :key="st.v" class="chip-btn"
            :class="{ active: articleStyle === st.v }"
            @click="articleStyle = st.v">{{ st.l }}</button>
        </div>

        <h2 style="margin-top:16px;">参考来源（动漫/日剧/歌曲名）</h2>
        <p style="font-size:0.75rem;color:var(--text-light);margin-bottom:8px;">
          可选。如果不确定则按你选择的内容类型自由创作。
        </p>
        <input v-model="articleSource" type="text"
          placeholder="例如：进击的巨人、东京爱情故事、Lemon…"
          class="gen-input" maxlength="100" />

        <div class="modal-actions">
          <button class="btn btn-outline" @click="showLevelModal = false">取消</button>
          <button class="btn btn-primary" :disabled="!articleLevel" @click="confirmGenerate">确认生成</button>
        </div>
      </div>
    </div>

    <!-- Streaming Modal -->
    <div v-if="showStreaming" class="modal-overlay" @click.self="cancelStreaming">
      <div class="modal streaming-modal">
        <div class="streaming-header">
          <h2>{{ generating ? '🔄 正在生成文章...' : '✅ 生成完成' }}</h2>
          <span v-if="generating" class="streaming-dot"></span>
        </div>

        <div v-if="genError" class="gen-error">
          ⚠ {{ genError }}
          <div style="margin-top:10px;display:flex;gap:8px;justify-content:center;">
            <router-link to="/" class="btn btn-accent btn-sm" @click="cancelStreaming">去首页设置</router-link>
            <button class="btn btn-primary btn-sm" @click="confirmGenerate">重试</button>
          </div>
        </div>

        <div v-else class="streaming-content">
          <pre class="stream-text">{{ streamingContent }}<span v-if="generating" class="cursor">▌</span></pre>
          <p v-if="!generating && streamingContent" class="stream-done-msg">文章已生成，即将跳转...</p>
          <p v-if="!streamingContent && generating" class="stream-waiting">正在请求 AI ...</p>
        </div>

        <div class="modal-actions">
          <button class="btn btn-outline" @click="cancelStreaming" :disabled="generating">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.favorites { max-width: 1000px; margin: 0 auto; }

.header-actions { display: flex; gap: 8px; }

.select-hint {
  color: var(--text);
  font-size: 0.85rem;
  margin-bottom: 16px;
  padding: 8px 14px;
  background: var(--bg-hint);
  border: 3px solid var(--golden);
  box-shadow: 2px 2px 0 rgba(200,160,48,0.2);
}

.type-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.type-tab {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.5rem;
  padding: 8px 14px;
  border: 3px solid var(--wood-dark);
  background: var(--cream);
  color: var(--wood-dark);
  cursor: pointer;
  transition: all 0.05s step-start;
  box-shadow: 2px 2px 0 var(--wood-dark);
}
.type-tab:hover { background: var(--bg-hover); }
.type-tab.active {
  background: var(--wood-dark);
  color: var(--cream);
  box-shadow: 3px 3px 0 var(--wood-darker);
  transform: translate(-1px, -1px);
}
.type-tab:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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

.grid-item { display: flex; flex-direction: column; gap: 4px; }

.btn-learned {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.6rem;
  padding: 8px 0;
  width: 100%;
  border: 3px solid var(--grass-dark);
  background: var(--cream);
  color: var(--grass-dark);
  cursor: pointer;
  transition: all 0.05s step-start;
  font-weight: 400;
  letter-spacing: 1px;
  box-shadow: 2px 2px 0 var(--grass-dark);
}
.btn-learned:hover {
  background: var(--grass);
  color: var(--cream);
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 var(--grass-dark);
}

.loading-overlay {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 24px;
  color: var(--text-light);
  font-size: 0.85rem;
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

/* Generation modal — content type & style */
.gen-modal { max-width: 520px; }
.chip-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.chip-btn {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.45rem;
  padding: 6px 12px;
  border: 3px solid var(--wood-dark);
  background: var(--cream);
  color: var(--wood-dark);
  cursor: pointer;
  transition: all 0.05s step-start;
  box-shadow: 2px 2px 0 var(--wood-dark);
}
.chip-btn:hover { background: var(--bg-hover); }
.chip-btn.active {
  background: var(--golden);
  color: var(--text);
  border-color: #C8A030;
  box-shadow: 2px 2px 0 #C8A030;
}
.gen-input {
  width: 100%;
  font-family: inherit;
  font-size: 0.85rem;
  padding: 10px 12px;
  border: 3px solid var(--wood-light);
  background: var(--cream);
  color: var(--text);
  outline: none;
  box-sizing: border-box;
}
.gen-input:focus { border-color: var(--golden); }

/* Streaming Modal */
.streaming-modal { min-width: 600px; max-width: 700px; }
.streaming-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}
.streaming-header h2 { margin-bottom: 0; }
.streaming-dot {
  width: 10px;
  height: 10px;
  background: var(--golden);
  box-shadow: 0 0 6px var(--golden);
  animation: pulse 1.2s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
.streaming-content {
  background: #2A2018;
  color: #D0C0A0;
  border: 3px solid var(--wood-dark);
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
  font-family: 'Noto Sans SC', 'Hiragino Sans', 'Yu Gothic', monospace;
  line-height: 1.8;
  min-height: 150px;
}
.stream-text {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.9rem;
  margin: 0;
  font-family: inherit;
}
.cursor { animation: blink 0.8s infinite; color: var(--golden); }
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
.stream-done-msg { color: var(--success); margin-top: 12px; font-size: 0.85rem; }
.stream-waiting { color: var(--text-muted); font-style: italic; font-size: 0.85rem; }
.gen-error { color: var(--danger); padding: 16px; text-align: center; }
</style>
