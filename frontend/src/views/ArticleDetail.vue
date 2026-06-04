<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchArticle } from '@/api'
import { speakJapanese } from '@/utils/speech'
import type { Article } from '@/types'

const route = useRoute()
const router = useRouter()

const article = ref<Article | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

onMounted(() => {
  loadArticle()
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

</script>

<template>
  <div class="article-detail">
    <button class="back-btn" @click="router.back()">← 返回</button>

    <!-- Loading -->
    <div v-if="loading" class="loading">加载中</div>

    <!-- Error -->
    <div v-else-if="error" class="error-msg">
      <p>⚠ {{ error }}</p>
      <button class="btn btn-primary btn-sm" style="margin-top: 12px" @click="loadArticle">重试</button>
    </div>

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
            <span class="chip-jp">{{ w.japanese }}</span>
            <span class="chip-kana">{{ w.kana }}</span>
          </router-link>
        </div>
      </div>

      <!-- Content: bilingual -->
      <div class="content-section card">
        <div class="content-block">
          <h3>日本語</h3>
          <div class="jp-text">{{ article.content_japanese }}</div>
        </div>

        <div class="content-divider"></div>

        <div class="content-block">
          <h3>中文翻译</h3>
          <div class="cn-text">{{ article.content_chinese }}</div>
        </div>
      </div>
    </template>

    <!-- Not Found -->
    <div v-else class="error-msg">
      <p>文章未找到</p>
    </div>
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
  gap: 14px;
  flex-wrap: wrap;
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
</style>
