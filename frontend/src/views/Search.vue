<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { searchWords, searchWordsByImage, aiAddWord } from '@/api'
import { speakJapanese } from '@/utils/speech'
import { typeColor } from '@/utils/shared'
import { STORAGE_KEYS } from '@/utils/constants'
import type { SearchResultItem, ImageSearchResponse } from '@/types'

const router = useRouter()
const route = useRoute()

// ── Tab ───────────────────────────────────────────────────────
const mode = ref<'text' | 'image'>('text')

// ── Text search ───────────────────────────────────────────────
const query = ref((route.query.q as string) || '')
const results = ref<SearchResultItem[]>([])
const total = ref(0)
const loading = ref(false)
const searched = ref(false)

let debounceTimer: ReturnType<typeof setTimeout> | null = null

// ── Image search cache ────────────────────────────────────────
onMounted(() => {
  if (route.query.img === '1') {
    restoreImageSearch()
  } else if (query.value) {
    doTextSearch()
  }
})

watch(query, (newVal) => {
  aiAddMsg.value = ''
  aiAddedId.value = null
  aiAdding.value = false
  // Merge with existing URL params so image mode (img=1) isn't lost
  router.replace({ query: { ...route.query, q: newVal || undefined } })

  if (debounceTimer) clearTimeout(debounceTimer)
  if (!newVal.trim()) {
    results.value = []
    total.value = 0
    searched.value = false
    return
  }
  debounceTimer = setTimeout(doTextSearch, 300)
})

async function doTextSearch() {
  const q = query.value.trim()
  if (!q) return

  loading.value = true
  searched.value = true
  try {
    const data = await searchWords(q, 5)
    results.value = data.results
    total.value = data.total
  } catch {
    results.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

// ── AI 补词 ────────────────────────────────────────────────
const aiAdding = ref(false)
const aiAddMsg = ref('')
const aiAddedId = ref<number | null>(null)

const AI_ADD_RATE_LIMIT_SECONDS = 5  // 与后端 AI_ADD_RATE_LIMIT_SECONDS 一致
const aiCountdown = ref(0)
let aiCountdownTimer: ReturnType<typeof setInterval> | null = null

function startAiCountdown(seconds: number) {
  aiCountdown.value = seconds
  if (aiCountdownTimer) clearInterval(aiCountdownTimer)
  aiCountdownTimer = setInterval(() => {
    aiCountdown.value -= 1
    if (aiCountdown.value <= 0) {
      aiCountdown.value = 0
      if (aiCountdownTimer) clearInterval(aiCountdownTimer)
      aiCountdownTimer = null
    }
  }, 1000)
}

onUnmounted(() => {
  if (aiCountdownTimer) clearInterval(aiCountdownTimer)
})

function looksJapanese(text: string): boolean {
  // 平假名/片假名/CJK —— 过滤 ASCII/数字，最终判定交给后端 LLM
  return /[぀-ヿ一-鿿]/.test(text)
}

async function handleAiAdd() {
  const q = query.value.trim()
  const m = mode.value
  if (!q) return
  aiAdding.value = true
  aiAddMsg.value = ''
  try {
    const res = await aiAddWord(q)
    startAiCountdown(AI_ADD_RATE_LIMIT_SECONDS)
    if (q !== query.value.trim() || mode.value !== m) return  // 用户已改 query/切 tab，丢弃过期响应
    if (res.status === 'added' || res.status === 'found') {
      if (res.word) {
        const item: SearchResultItem = {
          id: res.word.id,
          name: res.word.name,
          kana: res.word.kana,
          translation: res.word.translation,
          description: res.word.description || '',
          type: res.word.type || '',
          score: 1.0,
        }
        results.value = [item]
        total.value = 1
        aiAddedId.value = res.new ? res.word.id : null
        aiAddMsg.value = res.status === 'added'
          ? `已把「${res.word.name}」加入词库 ✨`
          : `「${res.word.name}」已在词库中`
      }
    } else if (res.status === 'not_japanese') {
      aiAddMsg.value = res.reason || `「${q}」看起来不是日语单词，无法添加`
    }
  } catch (e: any) {
    if (e?.response?.status === 429) {
      startAiCountdown(AI_ADD_RATE_LIMIT_SECONDS)
      aiAddMsg.value = '操作太频繁，请稍后再试'
    } else {
      aiAddMsg.value = 'AI 补词失败，请稍后再试'
    }
  } finally {
    aiAdding.value = false
  }
}

// ── Image search ──────────────────────────────────────────────
const dropActive = ref(false)
const previewUrl = ref<string | null>(null)
const selectedFile = ref<File | null>(null)
const processing = ref(false)
const progressStage = ref<string>('')
const imageResult = ref<ImageSearchResponse | null>(null)
const imageError = ref<string | null>(null)
const showGalleryHint = ref(false)
const restored = ref(false)  // true when results restored from cache (no preview image)

const stageTextMap: Record<string, string> = {
  upload: '正在上传图片...',
  ocr: '🔍 OCR 识别日语文字...',
  llm: '🧠 大模型分析图片内容...',
  search: '📖 正在搜索相关单词...',
  saving: '💾 保存到图片图库...',
}

const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/bmp']
const MAX_SIZE = 10 * 1024 * 1024

function validateFile(file: File): string | null {
  if (!ALLOWED_TYPES.includes(file.type)) {
    return `不支持的图片格式: ${file.type || '未知'}。仅支持 JPEG/PNG/WebP/GIF/BMP`
  }
  if (file.size > MAX_SIZE) {
    return `图片太大（最大 10 MB）`
  }
  if (file.size === 0) {
    return '图片文件为空'
  }
  return null
}

function onFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  if (!input.files?.length) return
  const file = input.files[0]
  const err = validateFile(file)
  if (err) { imageError.value = err; return }
  setFile(file)
  doImageSearch(file)
}

function onDrop(event: DragEvent) {
  dropActive.value = false
  const file = event.dataTransfer?.files?.[0]
  if (!file) return
  const err = validateFile(file)
  if (err) { imageError.value = err; return }
  setFile(file)
  doImageSearch(file)
}

function setFile(file: File) {
  selectedFile.value = file
  imageError.value = null
  imageResult.value = null
  results.value = []
  total.value = 0
  searched.value = false
  showGalleryHint.value = false
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = URL.createObjectURL(file)
}

function resetUpload() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = null
  selectedFile.value = null
  imageResult.value = null
  results.value = []
  total.value = 0
  searched.value = false
  imageError.value = null
  showGalleryHint.value = false
  restored.value = false
  clearImageSearch()
}

async function doImageSearch(file: File) {
  processing.value = true
  progressStage.value = 'upload'
  imageError.value = null
  imageResult.value = null
  restored.value = false

  try {
    progressStage.value = 'ocr'
    await new Promise(r => setTimeout(r, 400))
    progressStage.value = 'llm'
    await new Promise(r => setTimeout(r, 400))
    progressStage.value = 'search'
    const data = await searchWordsByImage(file)
    imageResult.value = data

    if (data.saved_to_gallery) showGalleryHint.value = true
    results.value = data.results || []
    total.value = data.total || 0
    searched.value = true

    if (!data.usable && data.message) {
      imageError.value = data.message
    }

    saveImageSearch(data)
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.message || '图片搜索失败，请重试'
    imageError.value = msg
    results.value = []
    total.value = 0
    searched.value = true
  } finally {
    processing.value = false
    progressStage.value = ''
  }
}

// ── Image search cache (survives page navigation) ────────────
function saveImageSearch(data: ImageSearchResponse) {
  try {
    const cache = {
      imageResult: data,
      results: data.results || [],
      total: data.total || 0,
    }
    sessionStorage.setItem(STORAGE_KEYS.IMG_SEARCH, JSON.stringify(cache))
    const text = (data.ocr_texts?.join(' ') || data.query || '').slice(0, 100)
    router.replace({ query: { img: '1', q: text || undefined } })
  } catch { /* storage full */ }
}

function restoreImageSearch() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEYS.IMG_SEARCH)
    if (!raw) return
    const cache = JSON.parse(raw)
    if (!cache.imageResult) return

    mode.value = 'image'
    imageResult.value = cache.imageResult
    results.value = cache.results || []
    total.value = cache.total || 0
    searched.value = true
    restored.value = true
  } catch { /* ignore corrupt cache */ }
}

function clearImageSearch() {
  sessionStorage.removeItem(STORAGE_KEYS.IMG_SEARCH)
  router.replace({ query: { q: query.value || undefined } })
}

// ── Shared ────────────────────────────────────────────────────
function goToWord(id: number) {
  router.push(`/word/${id}`)
}

function handleSpeak(text: string) {
  speakJapanese(text)
}

function switchMode(m: 'text' | 'image') {
  aiAddMsg.value = ''
  aiAddedId.value = null
  aiAdding.value = false
  mode.value = m
  results.value = []
  total.value = 0
  searched.value = false
  imageError.value = null
  imageResult.value = null
  previewUrl.value = null
  restored.value = false
  if (m === 'image') restoreImageSearch()
}

/** Click an OCR tag → search that text */
function searchOcrText(text: string) {
  switchMode('text')
  query.value = text
  doTextSearch()
}
</script>

<template>
  <div class="search-page">
    <!-- ── Tab switch ─────────────────────────── -->
    <div class="search-tabs">
      <button
        class="tab-btn"
        :class="{ active: mode === 'text' }"
        @click="switchMode('text')"
      >🔤 文字搜索</button>
      <button
        class="tab-btn"
        :class="{ active: mode === 'image' }"
        @click="switchMode('image')"
      >📷 图片搜索</button>
    </div>

    <!-- ════════════ Text mode ════════════ -->
    <template v-if="mode === 'text'">
      <div class="search-bar">
        <span class="search-icon">🔍</span>
        <input
          v-model="query"
          type="text"
          class="search-input"
          placeholder="搜索单词 — 输入日语、假名或中文..."
          autofocus
        />
        <button v-if="query" class="clear-btn" @click="query = ''">✕</button>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="search-status">搜索中...</div>

      <!-- No query -->
      <div v-else-if="!searched" class="search-hint">
        输入关键词搜索单词。支持日语表记、假名读音、中文释义。
      </div>
    </template>

    <!-- ════════════ Image mode ════════════ -->
    <template v-if="mode === 'image'">
      <!-- Upload area (hidden when results restored from cache) -->
      <div
        v-if="!processing && !previewUrl && !restored"
        class="upload-area"
        :class="{ 'drop-active': dropActive }"
        @dragover.prevent="dropActive = true"
        @dragleave.prevent="dropActive = false"
        @drop.prevent="onDrop"
        @click="$refs.fileInput?.click()"
      >
        <input
          ref="fileInput"
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif,image/bmp"
          style="display:none"
          @change="onFileSelect"
        />
        <div class="upload-icon">📤</div>
        <div class="upload-text">
          <span class="upload-main">点击选择图片</span>
          <span class="upload-sub">或拖拽图片到这里</span>
        </div>
        <div class="upload-hint">支持 JPEG / PNG / WebP，最大 10 MB</div>
      </div>

      <!-- Processing -->
      <div v-if="processing" class="search-status processing-status">
        <div class="processing-icon">🔍</div>
        <div class="processing-text">{{ stageTextMap[progressStage] || '处理中...' }}</div>
        <div class="processing-bar">
          <div class="processing-bar-fill"></div>
        </div>
        <div class="processing-tip">正在同时使用 OCR 和大模型识别图片中的日语文字...</div>
      </div>

      <!-- Preview + OCR results (also shows when restored from cache) -->
      <div v-if="(previewUrl || restored) && !processing" class="image-preview-section">
        <div v-if="previewUrl" class="preview-row">
          <div class="preview-image-wrapper">
            <img :src="previewUrl" alt="上传的图片" class="preview-image" />
          </div>
          <button class="btn btn-outline btn-sm" @click="resetUpload">🔄 换一张</button>
        </div>

        <div v-if="imageResult" class="ocr-section card">
          <div class="ocr-header">
            <span class="ocr-title">📝 识别结果</span>
            <span v-if="imageResult.processing_time_ms" class="ocr-time">
              {{ (imageResult.processing_time_ms / 1000).toFixed(1) }}s
            </span>
          </div>

          <div v-if="imageResult.ocr_texts && imageResult.ocr_texts.length > 0" class="ocr-texts">
            <span
              v-for="(text, i) in imageResult.ocr_texts"
              :key="i"
              class="ocr-tag"
              @click="searchOcrText(text)"
              :title="'点击搜索: ' + text"
            >{{ text }}<button class="ocr-speak" @click.stop="handleSpeak(text)" title="朗读">🔊</button></span>
          </div>

          <div v-if="imageResult.scene" class="ocr-scene">🖼️ {{ imageResult.scene }}</div>

          <div v-if="imageResult.saved_to_gallery" class="gallery-badge">
            💾 已保存到图片图库，以后搜图更精准
          </div>

          <div v-if="!imageResult.usable && imageResult.message" class="ocr-warning">
            ⚠️ {{ imageResult.message }}
          </div>

          <!-- New search button when results restored from cache -->
          <div v-if="restored" style="text-align:center;margin-top:12px">
            <button class="btn btn-primary" @click="resetUpload">🔍 新图片搜索</button>
          </div>
        </div>

        <div v-if="imageError && !processing" class="image-error card">
          <div class="error-icon">⚠️</div>
          <div>{{ imageError }}</div>
        </div>
      </div>
    </template>

    <!-- ════════════ Search results (shared) ════════════ -->
    <div v-if="results.length > 0 && !processing" class="results-section">
      <div class="result-count">
        找到 <strong>{{ total }}</strong> 个相关单词
        <span v-if="imageResult" class="result-query">
          — 识别文字: 「{{ imageResult.query?.slice(0, 60) }}」
        </span>
      </div>

      <div class="results-list">
        <div
          v-for="item in results"
          :key="item.id"
          class="result-card card"
          @click="goToWord(item.id)"
        >
          <div class="card-stripe" :style="{ background: typeColor(item.type) }"></div>
          <div class="result-main">
            <div class="result-left">
              <span class="result-name">{{ item.name }}</span>
              <span v-if="aiAddedId === item.id" class="ai-badge">AI 添加</span>
              <span class="result-kana">{{ item.kana }}</span>
            </div>
            <div class="result-right">
              <span class="result-trans">{{ item.translation }}</span>
              <span v-if="item.type" class="result-type" :style="{ background: typeColor(item.type) }">
                {{ item.type }}
              </span>
            </div>
          </div>
          <div class="result-actions">
            <button class="speak-btn-sm" @click.stop="handleSpeak(item.name)">🔊</button>
            <span v-if="item.score" class="result-score" :title="`相似度: ${(item.score * 100).toFixed(0)}%`">
              {{ (item.score * 100).toFixed(0) }}%
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- ── No results ─────────────────────────── -->
    <div v-if="searched && results.length === 0 && !loading && !processing && !imageError" class="search-status no-results">
      <template v-if="mode === 'text'">
        <div>没有找到与「{{ query }}」相关的单词</div>
        <div v-if="looksJapanese(query)" class="ai-add-block">
          <button v-if="aiCountdown > 0" class="ai-add-btn ai-add-countdown" disabled>
            请等待 {{ aiCountdown }}s
          </button>
          <button v-else-if="!aiAdding" class="ai-add-btn" @click="handleAiAdd">
            没有这个词？让 AI 添加 ✨
          </button>
          <span v-else class="ai-adding">AI 正在判断并补充词条…</span>
        </div>
        <p v-if="aiAddMsg" class="ai-add-msg">{{ aiAddMsg }}</p>
      </template>
      <template v-else>
        <div class="no-results-icon">🔎</div>
        <div>未从图片中识别出可搜索的日语单词</div>
        <div class="no-results-hint">
          请尝试上传：<br/>• 包含清晰日语文字的截图<br/>• 日语书籍、菜单、招牌照片<br/>• 日语学习资料图片
        </div>
      </template>
    </div>

    <!-- Gallery toast -->
    <div v-if="showGalleryHint" class="gallery-toast">💾 已保存到图片图库</div>
  </div>
</template>

<style scoped>
.search-page {
  max-width: 720px;
  margin: 0 auto;
}

/* ── Tabs ──────────────────────────────── */
.search-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 16px;
  border: 4px solid var(--wood-dark);
  background: var(--cream);
  box-shadow: 3px 3px 0 var(--wood-dark);
}

.tab-btn {
  flex: 1;
  padding: 10px 16px;
  font-family: 'Press Start 2P', monospace;
  font-size: 0.55rem;
  border: none;
  background: var(--cream);
  color: var(--text-light);
  cursor: pointer;
  transition: all 0.05s step-start;
  letter-spacing: 1px;
}

.tab-btn:first-child {
  border-right: 3px solid var(--wood-light);
}

.tab-btn.active {
  background: var(--warm-brown);
  color: var(--cream);
  box-shadow: inset 0 -2px 0 var(--golden);
}

.tab-btn:hover:not(.active) {
  background: var(--wood-light);
}

/* ── Text search bar ──────────────────── */
.search-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
  border: 4px solid var(--wood-dark);
  background: var(--cream);
  padding: 8px 12px;
  box-shadow: 3px 3px 0 var(--wood-dark);
}
.search-icon {
  font-size: 1.2rem;
  flex-shrink: 0;
}
.search-input {
  flex: 1;
  font-family: inherit;
  font-size: 1.1rem;
  padding: 8px 4px;
  border: none;
  background: transparent;
  color: var(--text);
  outline: none;
}
.search-input::placeholder {
  color: var(--text-light);
  opacity: 0.6;
}
.clear-btn {
  background: none;
  border: 2px solid var(--wood-light);
  color: var(--text-light);
  cursor: pointer;
  font-size: 0.8rem;
  padding: 2px 8px;
  border-radius: 4px;
}
.clear-btn:hover {
  border-color: var(--wood-dark);
  color: var(--text);
}

/* ── Status / Hint ─────────────────────── */
.search-status {
  text-align: center;
  padding: 40px 0;
  color: var(--text-light);
  font-size: 0.9rem;
}
.search-status.no-results {
  color: var(--danger);
}
.search-hint {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-light);
  font-size: 0.9rem;
  line-height: 1.6;
}

/* ── Image upload area ─────────────────── */
.upload-area {
  border: 4px dashed var(--wood-mid);
  background: var(--cream);
  padding: 48px 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.1s step-start;
  box-shadow: 3px 3px 0 var(--wood-dark);
  margin-bottom: 20px;
}

.upload-area:hover {
  border-color: var(--golden);
  background: #FFF4D0;
  transform: translate(-1px, -1px);
}

.upload-area.drop-active {
  border-color: var(--golden);
  background: #FFF0C0;
  border-style: solid;
}

.upload-icon {
  font-size: 3rem;
  margin-bottom: 12px;
}

.upload-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
}

.upload-main {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text);
}

.upload-sub {
  font-size: 0.85rem;
  color: var(--text-light);
}

.upload-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
}

/* ── Processing ─────────────────────────────── */
.processing-status {
  padding: 32px 24px;
}

.processing-icon {
  font-size: 2.5rem;
  margin-bottom: 12px;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.15); }
}

.processing-text {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 16px;
}

.processing-bar {
  width: 240px;
  height: 10px;
  margin: 0 auto 12px;
  background: var(--wood-light);
  border: 3px solid var(--wood-dark);
  overflow: hidden;
}

.processing-bar-fill {
  height: 100%;
  width: 40%;
  background: linear-gradient(90deg, var(--grass), var(--golden));
  animation: progress-slide 1.2s ease-in-out infinite;
}

@keyframes progress-slide {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(350%); }
}

.processing-tip {
  font-size: 0.8rem;
  color: var(--text-light);
}

/* ── Image preview ──────────────────────────── */
.image-preview-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 20px;
}

.preview-row {
  text-align: center;
}

.preview-image-wrapper {
  display: inline-block;
  border: 4px solid var(--wood-dark);
  box-shadow: 3px 3px 0 var(--wood-dark);
  background: var(--cream);
  max-width: 100%;
  overflow: hidden;
  margin-bottom: 10px;
}

.preview-image {
  display: block;
  max-width: 100%;
  max-height: 360px;
  object-fit: contain;
}

/* ── OCR Section ────────────────────────────── */
.ocr-section {
  padding: 14px 16px;
}

.ocr-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.ocr-title {
  font-weight: 700;
  font-size: 0.9rem;
  color: var(--text);
}

.ocr-time {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.5rem;
  color: var(--text-muted);
}

.ocr-texts {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.ocr-tag {
  display: inline-block;
  padding: 4px 10px;
  background: var(--bg-hint);
  border: 2px solid var(--wood-light);
  font-size: 0.9rem;
  color: var(--text);
  cursor: pointer;
  transition: all 0.05s step-start;
  font-weight: 500;
}

.ocr-tag:hover {
  border-color: var(--golden);
  background: var(--golden-light);
}

.ocr-speak {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.7rem;
  padding: 0 2px;
  margin-left: 4px;
  opacity: 0.6;
  vertical-align: middle;
}
.ocr-speak:hover {
  opacity: 1;
}

.ocr-scene {
  font-size: 0.85rem;
  color: var(--text-light);
  padding: 8px 10px;
  background: var(--bg-hint);
  border: 2px solid var(--wood-light);
  margin-bottom: 10px;
  line-height: 1.5;
}

.gallery-badge {
  display: inline-block;
  font-size: 0.75rem;
  color: var(--success);
  padding: 4px 10px;
  border: 2px solid var(--success);
  background: #E8F8E0;
}

.ocr-warning {
  font-size: 0.85rem;
  color: var(--warning);
  padding: 8px;
  margin-top: 8px;
  border: 2px solid var(--warning);
  background: var(--bg-hint);
}

.image-error {
  text-align: center;
  padding: 16px;
  border-color: var(--danger);
  color: var(--text);
  font-size: 0.9rem;
}

/* ── Results (shared) ────────────────── */
.results-section {
  margin-top: 12px;
}

.result-count {
  font-size: 0.8rem;
  color: var(--text-light);
  margin-bottom: 10px;
}

.result-query {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.result-card {
  position: relative;
  overflow: hidden;
  padding: 14px 16px;
  cursor: pointer;
  transition: all 0.1s step-start;
}

.result-card:hover {
  transform: translate(-1px, -1px);
  box-shadow: 4px 4px 0 var(--wood-dark);
}

.card-stripe {
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 100%;
}

.result-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.result-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.result-name {
  font-size: 1.3rem;
  font-weight: 700;
  color: var(--text);
}

.result-kana {
  font-size: 0.85rem;
  color: var(--text-light);
}

.result-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.result-trans {
  font-size: 1rem;
  color: var(--warm-brown);
  font-weight: 600;
}

.result-type {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.4rem;
  padding: 3px 8px;
  color: #fff;
  border-radius: 4px;
}

.result-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}

.speak-btn-sm {
  background: var(--cream);
  border: 2px solid var(--wood-light);
  cursor: pointer;
  font-size: 0.8rem;
  padding: 2px 6px;
  transition: all 0.05s step-start;
}

.speak-btn-sm:hover {
  border-color: var(--golden);
}

.result-score {
  font-size: 0.7rem;
  color: var(--text-light);
  font-family: 'Press Start 2P', monospace;
}

/* ── No results ─────────────────────────────── */
.no-results-icon {
  font-size: 2.5rem;
  margin-bottom: 8px;
}

.no-results-hint {
  font-size: 0.85rem;
  color: var(--text-light);
  line-height: 1.7;
  margin-top: 8px;
}

/* ── Gallery toast ──────────────────────────── */
.gallery-toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  padding: 12px 20px;
  background: var(--grass-dark);
  color: #fff;
  font-size: 0.85rem;
  border: 3px solid var(--grass);
  box-shadow: 3px 3px 0 rgba(0,0,0,0.2);
  animation: toast-in 0.3s ease, toast-out 0.3s ease 3s forwards;
  z-index: 1000;
}

@keyframes toast-in {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

@keyframes toast-out {
  from { opacity: 1; }
  to { opacity: 0; }
}

/* ── AI 补词 ─────────────────────────────── */
.ai-add-block {
  margin-top: 12px;
  display: flex;
  justify-content: center;
}
.ai-add-btn {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.45rem;
  padding: 10px 16px;
  border: 3px solid var(--golden);
  background: var(--cream);
  color: var(--warm-brown);
  cursor: pointer;
  box-shadow: 2px 2px 0 var(--golden);
  transition: all 0.05s step-start;
}
.ai-add-btn:hover {
  background: var(--golden-light);
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 var(--golden);
}
.ai-add-countdown {
  opacity: 0.5;
  cursor: not-allowed;
}
.ai-adding {
  font-size: 0.8rem;
  color: var(--text-light);
}
.ai-add-msg {
  margin-top: 10px;
  font-size: 0.8rem;
  color: var(--grass-dark);
  text-align: center;
}
.ai-badge {
  margin-left: 6px;
  font-size: 0.55rem;
  padding: 2px 6px;
  border: 2px solid var(--golden);
  color: var(--warm-brown);
  vertical-align: middle;
}
</style>
