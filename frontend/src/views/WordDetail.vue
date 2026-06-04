<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchWordDetail, toggleFavorite } from '@/api'
import { speakJapanese } from '@/utils/speech'
import type { WordDetailResponse } from '@/types'

const route = useRoute()
const router = useRouter()

const word = ref<WordDetailResponse | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const favorited = ref(false)

onMounted(() => { loadWord() })
watch(() => route.params.id, () => { loadWord() })

async function loadWord() {
  const id = Number(route.params.id)
  if (!id) return
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
    const result = await toggleFavorite(word.value.id)
    favorited.value = result.is_favorited
  } catch { /* silent */ }
}

function goToArticle(id: number) {
  router.push(`/article/${id}`)
}
</script>

<template>
  <div class="word-detail">
    <button class="back-btn" @click="router.back()">← 返回</button>

    <div v-if="loading" class="loading">加载中</div>

    <div v-else-if="error" class="error-msg">
      <p>⚠ {{ error }}</p>
      <button class="btn btn-primary btn-sm" style="margin-top: 12px" @click="loadWord">重试</button>
    </div>

    <template v-else-if="word">
      <div class="detail-card card">
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
          <h3>📖 例句</h3>
          <div v-if="word.example_sentences && word.example_sentences.length > 0" class="sentence-list">
            <div v-for="(sent, i) in word.example_sentences" :key="i" class="sentence-item">
              <div class="sentence-header">
                <span class="sentence-num">#{{ i + 1 }}</span>
                <button class="speak-btn" @click="speakJapanese(sent.japanese)">🔊</button>
              </div>
              <p class="sent-jp">{{ sent.japanese }}</p>
              <p class="sent-cn">{{ sent.chinese }}</p>
            </div>
          </div>
          <p v-else class="no-data">暂无例句</p>
        </div>
      </div>

      <div v-if="word.articles && word.articles.length > 0" class="articles-section card">
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
.detail-card { margin-bottom: 20px; }

.word-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 20px;
}
.jp-text { font-size: 2.2rem; font-weight: 700; margin-bottom: 4px; }
.kana { font-size: 1.1rem; color: var(--text-light); }

.word-actions { display: flex; gap: 10px; align-items: center; }
.fav-btn {
  background: none; border: none; font-size: 2rem; cursor: pointer;
  transition: transform 0.2s; color: var(--text-light);
}
.fav-btn:hover { transform: scale(1.2); }
.fav-btn.favorited { color: #f1c40f; }

.info-row { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; }
.translation { font-size: 1.2rem; color: var(--accent); font-weight: 600; }
.type-badge {
  font-size: 0.75rem; font-weight: 600; padding: 2px 10px;
  border-radius: 12px; background: var(--accent-light); color: var(--accent);
}
.description {
  font-size: 0.9rem; color: var(--text-light); margin-bottom: 16px;
  padding-bottom: 16px; border-bottom: 1px solid var(--border);
}

.sentences-section { margin-top: 16px; }
.sentences-section h3, .articles-section h3 {
  font-size: 1rem; color: var(--text-light); margin-bottom: 12px;
}

.sentence-list { display: flex; flex-direction: column; gap: 14px; }
.sentence-item { padding: 14px; background: var(--bg); border-radius: var(--radius-sm); }
.sentence-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.sentence-num { font-size: 0.8rem; font-weight: 600; color: var(--accent); }
.sent-jp { font-size: 1.05rem; margin-bottom: 4px; }
.sent-cn { font-size: 0.9rem; color: var(--text-light); }
.no-data { color: var(--text-light); font-style: italic; }

.articles-section { margin-top: 0; }
.article-list { display: flex; flex-direction: column; gap: 8px; }
.article-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; background: var(--bg); border-radius: var(--radius-sm);
  cursor: pointer; transition: background 0.2s;
}
.article-item:hover { background: var(--accent-light); }
.article-title { font-weight: 500; }
.article-level {
  font-size: 0.8rem; padding: 2px 10px;
  background: var(--accent); color: white; border-radius: 12px;
}
</style>
