<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useWordStore } from '@/stores/word'
import WordCard from '@/components/WordCard.vue'

const router = useRouter()
const store = useWordStore()
const favoritedIds = ref<Set<number>>(new Set())

onMounted(() => {
  store.loadRandomWords(5)
})

async function handleFavorite(wordId: number) {
  // WordCard 只 emit 了 id，从 store 中找到完整词对象
  const word = store.currentWords.find(w => w.id === wordId)
  if (!word) return

  const isFav = await store.toggleWordFavorite(
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
  if (isFav) {
    favoritedIds.value.add(wordId)
  } else {
    favoritedIds.value.delete(wordId)
  }
}

function goToDetail(id: number) {
  router.push(`/word/${id}`)
}

import { refreshSessionId } from '@/api'

function refreshWords() {
  refreshSessionId()         // 换新的 session_id → Redis 找不到旧缓存 → LLM 生成新词
  store.loadRandomWords(5)   // F5 刷新时读的还是这个新 id → 不会再变
}
</script>

<template>
  <div class="home">
    <div class="page-header">
      <h1>📝 今日的单词</h1>
      <button class="btn btn-primary" @click="refreshWords" :disabled="store.loading">
        {{ store.loading ? '⏳ 更换中...' : '🔄 换一批' }}
      </button>
    </div>

    <p class="subtitle">随机生成五个日语单词，点击收藏保存到你的单词本</p>

    <div v-if="store.loading && store.currentWords.length === 0" class="loading">
      <p>正在生成单词...</p>
      <p class="hint">首次使用需要调用 AI 生成，请稍候</p>
    </div>

    <div v-else-if="store.error" class="error-msg">
      <p>⚠ {{ store.error }}</p>
      <button class="btn btn-primary btn-sm" style="margin-top: 12px" @click="refreshWords">重试</button>
    </div>

    <div v-else-if="store.currentWords.length > 0" class="word-grid">
      <WordCard
        v-for="word in store.currentWords"
        :key="word.id"
        :word="word"
        :is-favorited="favoritedIds.has(word.id)"
        @favorite="handleFavorite"
        @click="goToDetail"
      />
    </div>

    <div v-else class="empty-state">
      <p>暂无单词数据</p>
      <button class="btn btn-primary btn-sm" @click="refreshWords">开始生成</button>
    </div>
  </div>
</template>

<style scoped>
.home { max-width: 900px; margin: 0 auto; }
.subtitle { color: var(--text-light); margin-bottom: 24px; font-size: 0.9rem; }
.word-grid { display: flex; flex-direction: column; gap: 16px; }
.hint { font-size: 0.85rem; color: var(--text-light); margin-top: 8px; }
.empty-state { text-align: center; padding: 60px; color: var(--text-light); }
</style>
