<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchWordDetail, toggleFavorite, refreshWordSentences, generateWordImage, smartWordImage, getApiKey, getPexelsKey } from '@/api'
import { speakJapanese, stopSpeech } from '@/utils/speech'
import { highlightWords } from '@/utils/highlight'
import { useWordStore } from '@/stores/word'
import type { WordDetailResponse } from '@/types'
import ErrorMessage from '@/components/ErrorMessage.vue'

const route = useRoute()
const router = useRouter()
const store = useWordStore()

const word = ref<WordDetailResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const favorited = ref(false)
const isCachedWord = ref(false)
const refreshingSentences = ref(false)
const sentContentType = ref('')
const generatingImage = ref(false)
const generatingSmartImage = ref(false)
const sentStyle = ref('')
const sentSource = ref('')
const showSentOptions = ref(false)

onMounted(() => { loadWord() })
watch(() => route.params.id, () => { loadWord() })

onUnmounted(() => { stopSpeech() })

async function loadWord() {
  const id = Number(route.params.id)
  if (!id) return

  const cachedData = store.clickedWord
  const wasFavorited = store.clickedWordFavorited
  store.clickedWord = null
  store.clickedWordFavorited = false
  if (cachedData && cachedData.name) {
    word.value = {
      id: cachedData.id,
      name: cachedData.name,
      kana: cachedData.kana,
      translation: cachedData.translation,
      description: cachedData.description || null,
      type: cachedData.type || null,
      example_sentences: cachedData.example_sentences || [],
      ext: null,
      created_at: null,
      is_favorited: wasFavorited,
      favorited_at: null,
      articles: [],
    }
    favorited.value = wasFavorited
    isCachedWord.value = true
    loading.value = false
    return
  }

  isCachedWord.value = false
  loading.value = true
  error.value = null
  try {
    const data = await fetchWordDetail(id)
    word.value = data
    favorited.value = data.is_favorited
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '加载失败'
    word.value = null
  } finally {
    loading.value = false
  }
}

async function handleFavorite() {
  if (!word.value) return
  try {
    const result = await toggleFavorite(word.value.id, {
      name: word.value.name,
      kana: word.value.kana,
      translation: word.value.translation,
      description: word.value.description,
      type: word.value.type,
      example_sentences: word.value.example_sentences,
    })
    favorited.value = result.is_favorited
    store.setWordFavorited(store.clickedWord?.id ?? word.value.id, result.is_favorited)
  } catch { /* silent */ }
}

async function handleRefreshSentences() {
  if (!word.value || refreshingSentences.value) return
  if (!getApiKey()) {
    alert('请先在首页设置 API Key 后才能使用此功能')
    return
  }
  refreshingSentences.value = true
  showSentOptions.value = false
  try {
    const result = await refreshWordSentences(word.value.id, getApiKey(), {
      content_type: sentContentType.value || undefined,
      style: sentStyle.value || undefined,
      source: sentSource.value || undefined,
      pexels_key: getPexelsKey() || undefined,
    })
    if (result.success && result.example_sentences) {
      word.value.example_sentences = result.example_sentences
    }
    // 配图由后台异步获取，刷新页面后可见
  } catch { /* silent */ }
  refreshingSentences.value = false
}

async function handleGenerateImage() {
  if (!word.value || generatingImage.value) return
  generatingImage.value = true
  try {
    const result = await generateWordImage(word.value.id, getPexelsKey() || undefined)
    if (result.success && result.image_url && word.value) {
      word.value.image_url = result.image_url
    }
  } catch { /* ignore */ }
  generatingImage.value = false
}

async function handleSmartImage() {
  if (!word.value || generatingSmartImage.value) return
  generatingSmartImage.value = true
  try {
    const result = await smartWordImage(word.value.id, getPexelsKey() || undefined)
    if (result.success && result.image_url && word.value) {
      word.value.image_url = result.image_url
    }
  } catch { /* ignore */ }
  generatingSmartImage.value = false
}

function goToArticle(id: number) {
  router.push(`/article/${id}`)
}

/** 高亮例句中的目标单词 */
function highlightSentence(text: string): string {
  if (!word.value) return text
  return highlightWords(text, [word.value.name])
}
</script>

<template>
  <div class="word-detail">
    <button class="back-btn" @click="router.back()">← 返回</button>

    <div v-if="loading" class="loading">加载中</div>

    <ErrorMessage v-else-if="error" :message="error" @retry="loadWord" />

    <template v-else-if="word">
      <div class="detail-card card">
        <!-- Top golden stripe -->
        <div class="card-stripe"></div>

        <div class="word-header">
          <div>
            <h1 class="jp-text">{{ word.name }}</h1>
            <p class="kana">{{ word.kana }}</p>
          </div>
          <div class="word-actions">
            <button class="speak-btn" title="朗读" @click="speakJapanese(word.name)">🔊</button>
            <button class="fav-btn" :class="{ favorited }" @click="handleFavorite">
              {{ favorited ? '★' : '☆' }}
            </button>
          </div>
        </div>

        <div class="info-row">
          <span class="translation">{{ word.translation }}</span>
          <span v-if="word.type" class="type-badge">{{ word.type }}</span>
        </div>
        <p v-if="word.description" class="description">{{ word.description }}</p>

        <div class="sentences-section">
          <!-- Word image -->
          <div v-if="word.image_url" class="word-image">
            <img :src="word.image_url" :alt="word.name" loading="lazy" />
            <div class="image-actions">
              <button class="btn-change-image" :disabled="generatingImage" @click="handleGenerateImage">
                {{ generatingImage ? '更换中...' : '🔄 换一张' }}
              </button>
              <button class="btn-smart-image" :disabled="generatingSmartImage" @click="handleSmartImage">
                {{ generatingSmartImage ? '匹配中...' : '🧠 智能配图' }}
              </button>
            </div>
          </div>
          <div v-else class="word-image-placeholder">
            <button class="btn-change-image" :disabled="generatingImage" @click="handleGenerateImage">
              {{ generatingImage ? '加载中...' : '🖼️ 生成配图' }}
            </button>
            <button class="btn-smart-image" :disabled="generatingSmartImage" @click="handleSmartImage">
              {{ generatingSmartImage ? '匹配中...' : '🧠 智能配图' }}
            </button>
          </div>

          <div class="sentences-header">
            <h3>📖 例句</h3>
            <div class="sent-actions">
              <button
                v-if="!isCachedWord"
                class="refresh-sentences-btn"
                :disabled="refreshingSentences"
                @click="showSentOptions = !showSentOptions"
              >
                {{ refreshingSentences ? '生成中...' : '✨ 句子换新' }}
              </button>
            </div>
          </div>
          <div v-if="showSentOptions && !isCachedWord" class="sent-options">
            <div class="chip-group">
              <span class="opt-label">类型</span>
              <button v-for="ct in [{v:'',l:'不限'},{v:'anime',l:'动漫'},{v:'drama',l:'日剧'},{v:'music',l:'歌曲'}]"
                :key="ct.v" class="chip-btn-sm"
                :class="{ active: sentContentType === ct.v }"
                @click="sentContentType = ct.v">{{ ct.l }}</button>
            </div>
            <div class="chip-group">
              <span class="opt-label">风格</span>
              <button v-for="st in [{v:'',l:'不限'},{v:'emotional',l:'感情'},{v:'funny',l:'搞笑'},{v:'plain',l:'朴素'}]"
                :key="st.v" class="chip-btn-sm"
                :class="{ active: sentStyle === st.v }"
                @click="sentStyle = st.v">{{ st.l }}</button>
            </div>
            <input v-model="sentSource" type="text" placeholder="参考来源（可选）" class="sent-source-input" maxlength="100" />
            <button class="btn btn-primary btn-sm" @click="handleRefreshSentences" :disabled="refreshingSentences">确认生成</button>
          </div>

          <div v-if="word.example_sentences && word.example_sentences.length > 0" class="sentence-list">
            <div v-for="(sent, i) in word.example_sentences" :key="i" class="sentence-item">
              <div class="sentence-header">
                <span class="sentence-num">#{{ i + 1 }}</span>
                <button class="speak-btn" @click="speakJapanese(sent.japanese)">🔊</button>
              </div>
              <p class="sent-jp" v-html="highlightSentence(sent.japanese)"></p>
              <p class="sent-cn">{{ sent.chinese }}</p>
            </div>
          </div>
          <p v-else class="no-data">暂无例句</p>
        </div>
      </div>

      <div v-if="word.articles && word.articles.length > 0" class="articles-section card">
        <div class="card-stripe"></div>
        <h3>📄 相关文章</h3>
        <div class="article-list">
          <div
            v-for="article in word.articles"
            :key="article.id"
            class="article-item"
            @click="goToArticle(article.id)"
          >
            <span class="article-title">{{ article.title }}</span>
            <span class="article-level">{{ article.level }}</span>
          </div>
        </div>
      </div>
    </template>

    <div v-else class="error-msg"><p>单词未找到</p></div>
  </div>
</template>

<style scoped>
.word-detail { max-width: 800px; margin: 0 auto; }

.detail-card {
  margin-bottom: 20px;
  position: relative;
  overflow: hidden;
}
.card-stripe {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--golden), var(--grass-light), var(--pink), var(--golden));
}

.word-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.jp-text { font-size: 2.4rem; font-weight: 700; margin-bottom: 6px; color: var(--text); }
.kana { font-size: 1.3rem; color: var(--text-light); }

.word-actions { display: flex; gap: 10px; align-items: center; }
.fav-btn {
  background: var(--cream);
  border: 3px solid var(--wood-dark);
  font-size: 1.8rem;
  width: 44px;
  height: 44px;
  cursor: pointer;
  transition: all 0.05s step-start;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 2px 2px 0 var(--wood-dark);
}
.fav-btn:hover {
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 var(--wood-dark);
}
.fav-btn.favorited {
  color: var(--golden);
  border-color: var(--golden);
  background: #FFF8E0;
  box-shadow: 2px 2px 0 var(--golden);
}

.info-row { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; }
.translation { font-size: 1.4rem; color: var(--warm-brown); font-weight: 700; }

.description {
  font-size: 1.05rem;
  color: var(--text-light);
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 2px solid var(--wood-light);
  line-height: 1.8;
}

.sentences-section { margin-top: 16px; }
.sentences-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.refresh-sentences-btn {
  background: var(--cream);
  border: 3px solid var(--wood-dark);
  padding: 6px 14px;
  font-size: 0.7rem;
  font-family: 'Press Start 2P', monospace;
  cursor: pointer;
  transition: all 0.05s step-start;
  box-shadow: 2px 2px 0 var(--wood-dark);
  color: var(--warm-brown);
  white-space: nowrap;
}
.refresh-sentences-btn:hover:not(:disabled) {
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 var(--wood-dark);
}
.refresh-sentences-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.sent-actions {
  display: flex;
  gap: 6px;
}
.sent-options {
  margin-bottom: 14px;
  padding: 12px;
  background: var(--cream);
  border: 3px solid var(--wood-light);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.chip-group {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.opt-label {
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-light);
  min-width: 36px;
}
.chip-btn-sm {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.4rem;
  padding: 4px 10px;
  border: 2px solid var(--wood-dark);
  background: var(--cream);
  color: var(--wood-dark);
  cursor: pointer;
  transition: all 0.05s step-start;
}
.chip-btn-sm:hover { background: var(--bg-hover); }
.chip-btn-sm.active {
  background: var(--golden);
  color: var(--text);
  border-color: #C8A030;
}
.sent-source-input {
  font-family: inherit;
  font-size: 0.8rem;
  padding: 8px 10px;
  border: 2px solid var(--wood-light);
  background: #fff;
  color: var(--text);
  outline: none;
}
.sent-source-input:focus { border-color: var(--golden); }
.word-image {
  margin-bottom: 16px;
  border: 4px solid var(--wood-dark);
  overflow: hidden;
  background: var(--cream);
}
.word-image img {
  width: 100%;
  height: auto;
  max-height: 300px;
  object-fit: cover;
  display: block;
}
.word-image-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100px;
  margin-bottom: 16px;
  border: 3px dashed var(--wood-light);
  background: var(--cream);
}
.btn-change-image {
  display: block;
  width: 100%;
  font-family: 'Press Start 2P', monospace;
  font-size: 0.5rem;
  padding: 6px;
  border: 3px solid var(--wood-dark);
  background: var(--cream);
  color: var(--warm-brown);
  cursor: pointer;
  transition: all 0.05s step-start;
  box-shadow: 2px 2px 0 var(--wood-dark);
  margin-top: 4px;
}
.image-actions {
  display: flex;
  gap: 4px;
}
.image-actions .btn-change-image,
.image-actions .btn-smart-image {
  flex: 1;
}
.btn-smart-image {
  display: block;
  width: 100%;
  font-family: 'Press Start 2P', monospace;
  font-size: 0.5rem;
  padding: 6px;
  border: 3px solid #6B4F9E;
  background: #F3EEFA;
  color: #6B4F9E;
  cursor: pointer;
  transition: all 0.05s step-start;
  box-shadow: 2px 2px 0 #6B4F9E;
  margin-top: 4px;
}
.btn-smart-image:hover:not(:disabled) {
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 #6B4F9E;
}
.btn-smart-image:active:not(:disabled) {
  transform: translate(1px, 1px);
  box-shadow: 0px 0px 0 #6B4F9E;
}
.btn-smart-image:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.btn-change-image:hover:not(:disabled) {
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 var(--wood-dark);
}
.btn-change-image:disabled { opacity: 0.6; cursor: not-allowed; }
.sentences-section h3, .articles-section h3 {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.6rem;
  color: var(--text);
  margin-bottom: 14px;
  letter-spacing: 1px;
}

.sentence-list { display: flex; flex-direction: column; gap: 12px; }
.sentence-item {
  padding: 14px;
  background: var(--cream);
  border: 3px solid var(--wood-light);
  box-shadow: inset -2px -2px 0 rgba(0,0,0,0.03);
}
.sentence-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.sentence-num {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.4rem;
  color: var(--warm-brown);
}
.sent-jp { font-size: 1.15rem; margin-bottom: 4px; font-weight: 500; }
.sent-cn { font-size: 0.95rem; color: var(--text-light); }
.no-data { color: var(--text-muted); font-style: italic; }

.articles-section { margin-top: 0; position: relative; overflow: hidden; }
.article-list { display: flex; flex-direction: column; gap: 6px; }
.article-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: var(--cream);
  border: 3px solid var(--wood-light);
  cursor: pointer;
  transition: all 0.05s step-start;
}
.article-item:hover {
  background: var(--golden-light);
  border-color: var(--golden);
}
.article-title { font-weight: 500; }
.article-level {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.4rem;
  padding: 3px 10px;
  background: var(--golden);
  color: var(--text);
  border: 2px solid var(--warm-brown-dark);
  box-shadow: 1px 1px 0 var(--warm-brown-dark);
}

/* ── 单词高亮（例句中） ──────────────── */
:deep(.highlight-word) {
  color: var(--golden);
  font-weight: 700;
  text-shadow: 0 0 4px rgba(232, 184, 48, 0.3);
}
</style>
