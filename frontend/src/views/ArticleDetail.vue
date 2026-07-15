<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchArticle, generateArticleImage, getPexelsKey } from '@/api'
import { speakJapanese, stopSpeech } from '@/utils/speech'
import { highlightWords } from '@/utils/highlight'
import type { Article } from '@/types'
import ErrorMessage from '@/components/ErrorMessage.vue'

const route = useRoute()
const router = useRouter()

const article = ref<Article | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const changingImage = ref(false)

onMounted(() => {
  loadArticle()
})

onUnmounted(() => {
  stopSpeech()
})

watch(() => route.params.id, () => {
  loadArticle()
})

async function loadArticle() {
  const id = Number(route.params.id)
  if (!id) return

  loading.value = true
  error.value = null
  try {
    article.value = await fetchArticle(id)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '加载文章失败'
    article.value = null
  } finally {
    loading.value = false
  }
}

async function handleChangeImage() {
  if (!article.value || changingImage.value) return
  changingImage.value = true
  try {
    const result = await generateArticleImage(article.value.id, getPexelsKey() || undefined)
    if (result.success && result.image_url) {
      article.value.image_url = result.image_url
    }
  } catch { /* ignore */ }
  changingImage.value = false
}

/** 高亮文章中涉及的日语单词 */
function highlightArticleContent(text: string): string {
  if (!article.value) return text
  const words = article.value.words.map(w => w.name).filter(Boolean) as string[]
  return highlightWords(text, words)
}

</script>

<template>
  <div class="article-detail">
    <button class="back-btn" @click="router.back()">← 返回</button>

    <!-- Loading -->
    <div v-if="loading" class="loading">加载中</div>

    <!-- Error -->
    <ErrorMessage v-else-if="error" :message="error" @retry="loadArticle" />

    <!-- Article -->
    <template v-else-if="article">
      <div class="article-header">
        <h1>{{ article.title }}</h1>
        <div class="meta">
          <span class="level-badge">{{ article.level }}</span>
          <span class="date">{{ article.created_at ? new Date(article.created_at).toLocaleDateString('zh-CN') : '' }}</span>
          <button class="speak-btn" title="朗读全文" @click="speakJapanese(article.content_japanese)">🔊 朗读全文</button>
        </div>
      </div>

      <!-- Article image -->
      <div v-if="article.image_url" class="article-image">
        <img :src="article.image_url" :alt="article.title" loading="lazy" />
        <button class="btn-change-image" :disabled="changingImage" @click="handleChangeImage">
          {{ changingImage ? '更换中...' : '🔄 换一张' }}
        </button>
      </div>
      <div v-else class="article-image-placeholder">
        <button class="btn-change-image" :disabled="changingImage" @click="handleChangeImage">
          {{ changingImage ? '加载中...' : '🖼️ 生成配图' }}
        </button>
      </div>

      <!-- Words used in this article -->
      <div class="words-section">
        <h3>本文使用的单词</h3>
        <div class="word-chips">
          <router-link
            v-for="w in article.words"
            :key="w.id"
            :to="`/word/${w.id}`"
            class="word-chip"
          >
            <span class="chip-jp">{{ w.name }}</span>
            <span class="chip-kana">{{ w.kana }}</span>
          </router-link>
        </div>
      </div>

      <!-- Content: bilingual -->
      <div class="content-section card">
        <div class="content-block">
          <h3>日本語</h3>
          <div class="jp-text" v-html="highlightArticleContent(article.content_japanese)"></div>
        </div>

        <div class="content-divider"></div>

        <div class="content-block">
          <h3>中文翻译</h3>
          <div class="cn-text">{{ article.content_chinese }}</div>
        </div>
      </div>
    </template>

    <!-- Not Found -->
    <ErrorMessage v-else message="文章未找到" />
  </div>
</template>

<style scoped>
.article-detail {
  max-width: 800px;
  margin: 0 auto;
}

.article-header {
  margin-bottom: 24px;
}

.article-header h1 {
  font-size: 1.8rem;
  margin-bottom: 12px;
}

.meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.article-image {
  margin-bottom: 20px;
  border: 4px solid var(--wood-dark);
  overflow: hidden;
  background: var(--cream);
}
.article-image img {
  width: 100%;
  height: auto;
  max-height: 400px;
  object-fit: cover;
  display: block;
}
.article-image-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 120px;
  margin-bottom: 20px;
  border: 3px dashed var(--wood-light);
  background: var(--cream);
}
.btn-change-image {
  display: block;
  width: 100%;
  font-family: 'Press Start 2P', monospace;
  font-size: 0.55rem;
  padding: 8px;
  border: 3px solid var(--wood-dark);
  background: var(--cream);
  color: var(--warm-brown);
  cursor: pointer;
  transition: all 0.05s step-start;
  box-shadow: 2px 2px 0 var(--wood-dark);
  margin-top: 4px;
}
.btn-change-image:hover:not(:disabled) {
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 var(--wood-dark);
}
.btn-change-image:disabled { opacity: 0.6; cursor: not-allowed; }
.meta .speak-btn {
  width: auto;
  height: auto;
  padding: 6px 14px;
  font-size: 0.8rem;
  gap: 4px;
  white-space: nowrap;
  border: 3px solid var(--wood-dark);
}
.level-badge {
  padding: 4px 14px;
  background: var(--primary);
  color: white;
  border-radius: 16px;
  font-size: 0.85rem;
  font-weight: 600;
}

.date {
  color: var(--text-light);
  font-size: 0.85rem;
}

/* Words section */
.words-section {
  margin-bottom: 20px;
}

.words-section h3 {
  font-size: 0.95rem;
  color: var(--text-light);
  margin-bottom: 10px;
}

.word-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.word-chip {
  display: flex;
  flex-direction: column;
  padding: 6px 14px;
  background: var(--bg);
  border-radius: var(--radius-sm);
  text-decoration: none;
  color: var(--text);
  border: 1px solid var(--border);
  transition: all 0.2s;
}

.word-chip:hover {
  border-color: var(--accent);
  background: var(--accent-light);
}

.chip-jp {
  font-weight: 600;
  font-size: 0.95rem;
}

.chip-kana {
  font-size: 0.75rem;
  color: var(--text-light);
}

/* Content */
.content-section {
  line-height: 1.8;
}

.content-block {
  margin-bottom: 16px;
}

.content-block h3 {
  font-size: 0.9rem;
  color: var(--text-light);
  margin-bottom: 12px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.jp-text {
  font-size: 1.1rem;
  white-space: pre-wrap;
}

.cn-text {
  font-size: 1rem;
  color: var(--text);
  white-space: pre-wrap;
}

.content-divider {
  height: 1px;
  background: var(--border);
  margin: 20px 0;
}

/* ── 单词高亮（文章中） ──────────────── */
:deep(.highlight-word) {
  color: var(--golden);
  font-weight: 700;
  text-shadow: 0 0 4px rgba(232, 184, 48, 0.3);
}
</style>
