<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useWordStore } from '@/stores/word'
import WordCard from '@/components/WordCard.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import {
  refreshSessionId,
  getApiKey, setApiKey, hasApiKey,
  getPexelsKey, setPexelsKey,
} from '@/api'

const router = useRouter()
const store = useWordStore()

// ── Scene selector ─────────────────────────────────────────
const SCENES = [
  { key: '', label: '🌐 全部' },
  { key: '日常生活', label: '🏠 日常' },
  { key: '工作', label: '💼 工作' },
  { key: '商务', label: '🏢 商务' },
  { key: '影视剧', label: '🎬 影视' },
  { key: '动漫', label: '🎮 动漫' },
  { key: '旅游', label: '✈️ 旅游' },
]

function selectScene(scene: string) {
  if (store.selectedScene === scene) return
  store.setScene(scene)
  refreshSessionId()
  store.loadRandomWordsStreaming(5)
}

// ── API Key management ────────────────────────────────────
const showKeyInput = ref(false)
const editingLLMKey = ref(getApiKey())
const editingPexelsKey = ref(getPexelsKey())
const keySaved = ref('')

function openKeySettings() {
  showKeyInput.value = true
  editingLLMKey.value = getApiKey()
  editingPexelsKey.value = getPexelsKey()
  keySaved.value = ''
}

function saveAllKeys() {
  setApiKey(editingLLMKey.value.trim())
  setPexelsKey(editingPexelsKey.value.trim())
  keySaved.value = 'API Key 已保存'
  setTimeout(() => { keySaved.value = '' }, 3000)
}

function closeKeySettings() {
  showKeyInput.value = false
}

const hasWords = computed(() => store.currentWords.length > 0)

async function handleFavorite(wordId: number) {
  const word = store.currentWords.find(w => w.id === wordId)
  if (!word) return

  await store.toggleWordFavorite(
    wordId,
    {
      name: word.name,
      kana: word.kana,
      translation: word.translation,
      description: word.description,
      type: word.type,
      example_sentences: word.example_sentences,
    },
  )
}

function goToDetail(id: number) {
  const word = store.currentWords.find(w => w.id === id)
  if (word) {
    store.clickedWord = word
    store.clickedWordFavorited = store.isWordFavorited(id)
  }
  router.push(`/word/${id}`)
}

function refreshWords() {
  refreshSessionId()
  store.loadRandomWordsStreaming(5)
}
</script>

<template>
  <div class="home">
    <!-- ── API Key 设置 ──────────────────────────── -->
    <div v-if="showKeyInput" class="card api-key-card">
      <div class="card-stripe"></div>
      <div class="key-card-header">
        <h3 class="section-title">🔑 API Key 设置</h3>
        <button class="btn-close-sm" @click="closeKeySettings">✕</button>
      </div>
      <p class="api-key-desc">
        填写后仅保存在你的浏览器中，不会被服务器存储。
      </p>

      <div class="key-field">
        <label>① LLM API Key <span class="key-needed">（生成文章 / 换句子）</span></label>
        <input v-model="editingLLMKey" type="text"
          placeholder="sk-… 通义千问 DashScope API Key"
          class="api-key-input" />
        <a href="https://help.aliyun.com/zh/dashscope/developer-reference/activate-dashscope-and-create-an-api-key" target="_blank" class="key-guide-link">
          📖 如何获取？→ 阿里云 DashScope 控制台
        </a>
      </div>

      <div class="key-field">
        <label>② Pexels API Key <span class="key-needed">（文章自动配图）</span></label>
        <input v-model="editingPexelsKey" type="text"
          placeholder="Pexels API Key"
          class="api-key-input" />
        <span class="key-guide-text">
          📖 如何获取？<a href="https://www.pexels.com/api/" target="_blank">pexels.com/api</a> 免费注册
          （国内访问较慢，可尝试科学上网）
        </span>
      </div>

      <div class="key-actions">
        <button class="btn btn-outline btn-sm" @click="closeKeySettings">取消</button>
        <button class="btn btn-primary btn-sm" @click="saveAllKeys">保存全部</button>
      </div>
    </div>

    <div v-else class="api-key-badge-row">
      <span v-if="hasApiKey()" class="key-badge">✅ LLM</span>
      <span v-if="getPexelsKey()" class="key-badge">✅ Pexels</span>
      <span v-if="!hasApiKey() && !getPexelsKey()" class="key-badge dim">未配置 API Key</span>
      <button class="link-btn" @click="openKeySettings">⚙️ 配置</button>
    </div>

    <p v-if="keySaved" class="msg-success">{{ keySaved }}</p>

    <div class="page-header">
      <h1>📝 今日的单词</h1>
      <button v-if="hasWords || store.loading || store.error" class="btn btn-primary" @click="refreshWords" :disabled="store.loading">
        <template v-if="store.loading">⏳ 生成中...</template>
        <template v-else>🔄 换一批</template>
      </button>
    </div>

    <p class="subtitle">随机生成五个日语单词，点击收藏保存到你的单词本</p>

    <!-- 场景选择器 -->
    <div class="scene-selector">
      <button
        v-for="s in SCENES"
        :key="s.key"
        class="scene-chip"
        :class="{ active: store.selectedScene === s.key }"
        :disabled="store.loading"
        @click="selectScene(s.key)"
      >{{ s.label }}</button>
    </div>

    <!-- 欢迎页面 — 首次进入时展示 -->
    <div v-if="!hasWords && !store.loading && !store.error" class="welcome">
      <div class="welcome-icon">🌾</div>
      <h2 class="welcome-title">欢迎来到单词农场！</h2>
      <p class="welcome-desc">点击「生成新词」按钮，AI 将为你播下新的日语单词种子，开始你的学习之旅吧！</p>
      <button class="btn btn-primary btn-lg" @click="refreshWords" style="margin-top: 20px">
        🌱 播种新词
      </button>
    </div>

    <!-- 流式加载中 — 已收到的词即时展示 -->
    <div v-if="store.streaming">
      <div v-if="hasWords" class="word-grid">
        <WordCard
          v-for="word in store.currentWords"
          :key="word.id"
          :word="word"
          :is-favorited="store.isWordFavorited(word.id)"
          @favorite="handleFavorite"
          @click="goToDetail"
        />
      </div>
      <div class="streaming-bar">
        <span class="streaming-dot"></span>
        <span>正在播种...（{{ store.currentWords.length }}/5）</span>
      </div>
    </div>

    <div v-else-if="store.loading && !hasWords" class="loading">
      <p>正在播种...</p>
      <p class="hint">首次使用需要调用 AI 生成，请稍候</p>
    </div>

    <ErrorMessage v-else-if="store.error" :message="store.error" @retry="refreshWords" />

    <div v-else-if="hasWords" class="word-grid">
      <WordCard
        v-for="word in store.currentWords"
        :key="word.id"
        :word="word"
        :is-favorited="store.isWordFavorited(word.id)"
        @favorite="handleFavorite"
        @click="goToDetail"
      />
    </div>
  </div>
</template>

<style scoped>
.home { max-width: 900px; margin: 0 auto; }
.api-key-card {
  padding: 20px;
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
.section-title {
  font-size: 0.9rem;
  color: var(--text);
  margin: 0;
}
.key-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.btn-close-sm {
  background: none;
  border: 2px solid var(--wood-light);
  color: var(--text-light);
  width: 28px;
  height: 28px;
  cursor: pointer;
  font-size: 0.7rem;
  display: flex;
  align-items: center;
  justify-content: center;
}
.btn-close-sm:hover {
  border-color: var(--golden);
  color: var(--golden);
}
.api-key-desc {
  font-size: 0.75rem;
  color: var(--text-light);
  margin: 0 0 16px 0;
  line-height: 1.6;
}
.key-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 14px;
}
.key-field label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text);
}
.key-needed {
  font-weight: 400;
  color: var(--text-light);
  font-size: 0.65rem;
}
.api-key-input {
  width: 100%;
  font-family: inherit;
  font-size: 0.8rem;
  padding: 8px 10px;
  border: 3px solid var(--wood-light);
  background: var(--cream);
  color: var(--text);
  outline: none;
  box-sizing: border-box;
}
.api-key-input:focus {
  border-color: var(--golden);
}
.key-guide-link {
  font-size: 0.65rem;
  color: var(--golden);
  text-decoration: underline;
  margin-top: 2px;
}
.key-guide-link:hover {
  color: var(--warm-orange);
}
.key-guide-text {
  font-size: 0.65rem;
  color: var(--text-light);
  margin-top: 2px;
  line-height: 1.5;
}
.key-guide-text a {
  color: var(--golden);
  text-decoration: underline;
}
.key-guide-text a:hover {
  color: var(--warm-orange);
}
.key-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 8px;
}
.api-key-badge-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.key-badge {
  font-size: 0.65rem;
  font-family: 'Press Start 2P', monospace;
  padding: 4px 8px;
  border: 2px solid var(--grass-dark);
  color: var(--grass-dark);
}
.key-badge.dim {
  border-color: var(--wood-light);
  color: var(--text-muted);
}
.link-btn {
  background: none;
  border: none;
  color: var(--golden);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.75rem;
  text-decoration: underline;
  padding: 0;
  margin-left: auto;
}
.link-btn:hover {
  color: var(--warm-orange);
}
.msg-success {
  color: var(--grass-dark);
  font-size: 0.75rem;
  margin-bottom: 8px;
  padding: 6px 10px;
  background: rgba(74, 124, 89, 0.08);
  border: 2px solid var(--grass-dark);
}
.btn-sm {
  font-size: 0.75rem;
  padding: 8px 14px;
  white-space: nowrap;
}
.btn-outline {
  background: var(--cream);
  border: 3px solid var(--wood-dark);
  color: var(--text);
  cursor: pointer;
  font-family: inherit;
}
.subtitle {
  color: var(--cream);
  font-size: 1rem;
  margin-bottom: 24px;
  padding: 0 4px;
  text-shadow: 1px 1px 0 rgba(0,0,0,0.2);
}

.word-grid { display: flex; flex-direction: column; gap: 14px; }
.hint { font-size: 0.85rem; color: var(--cream); margin-top: 8px; opacity: 0.7; }

.welcome {
  text-align: center;
  padding: 60px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  background: var(--bg-card);
  border: 4px solid var(--wood-dark);
  box-shadow:
    inset -3px -3px 0 var(--wood-dark),
    inset 3px 3px 0 var(--wood-light),
    2px 3px 0 rgba(60,40,20,0.1);
  max-width: 500px;
  margin: 40px auto;
}
.welcome-icon { font-size: 4rem; filter: drop-shadow(0 4px 8px rgba(0,0,0,0.1)); }
.welcome-title {
  font-family: 'Press Start 2P', monospace;
  font-size: clamp(0.6rem, 2.5vw, 0.85rem);
  color: var(--text);
  letter-spacing: 2px;
}
.welcome-desc { font-size: 1.05rem; color: var(--text-light); max-width: 420px; line-height: 1.8; }
.btn-lg {
  padding: 16px 40px;
  font-size: 0.8rem;
}

.streaming-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: center;
  padding: 16px;
  color: var(--cream);
  font-size: 0.85rem;
  text-shadow: 1px 1px 0 rgba(0,0,0,0.15);
}
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

.scene-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 18px;
  justify-content: center;
}
.scene-chip {
  font-family: inherit;
  font-size: 0.75rem;
  padding: 6px 14px;
  border: 3px solid var(--wood-light);
  background: var(--cream);
  color: var(--text);
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.scene-chip:hover:not(:disabled) {
  border-color: var(--golden);
  color: var(--golden);
}
.scene-chip.active {
  border-color: var(--golden);
  background: var(--golden);
  color: #fff;
  font-weight: 700;
}
.scene-chip:disabled {
  opacity: 0.5;
  cursor: default;
}
</style>
