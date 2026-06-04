<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchFavorites, generateArticle } from '@/api'
import type { Word } from '@/types'
import WordCard from '@/components/WordCard.vue'

const router = useRouter()

// -- Favorites list state --
const words = ref<Word[]>([])
const total = ref(0)
const page = ref(1)
const totalPages = ref(1)
const pageSize = 30
const loading = ref(false)
const error = ref<string | null>(null)

// -- Selection / article generation state --
const selecting = ref(false)
const selectedIds = ref<Set<number>>(new Set())
const showLevelModal = ref(false)
const articleLevel = ref('')
const generating = ref(false)
const genError = ref<string | null>(null)

onMounted(() => {
  loadFavorites()
})

async function loadFavorites() {
  loading.value = true
  error.value = null
  try {
    const data = await fetchFavorites(page.value, pageSize)
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

function goToDetail(id: number) {
  if (!selecting.value) {
    router.push(`/word/${id}`)
  }
}

// -- Article generation flow --

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
  if (s.has(id)) {
    s.delete(id)
  } else {
    s.add(id)
  }
  selectedIds.value = s
}

function confirmSelection() {
  if (selectedIds.value.size === 0) return
  showLevelModal.value = true
  articleLevel.value = ''
}

function selectLevel(level: string) {
  articleLevel.value = level
}

async function confirmGenerate() {
  if (!articleLevel.value) return
  generating.value = true
  genError.value = null
  try {
    const article = await generateArticle([...selectedIds.value], articleLevel.value)
    selecting.value = false
    showLevelModal.value = false
    router.push(`/article/${article.id}`)
  } catch (e: any) {
    genError.value = e?.response?.data?.detail || '生成文章失败'
  } finally {
    generating.value = false
  }
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

    <!-- Select mode hint -->
    <p v-if="selecting" class="select-hint">
      请勾选要用于生成文章的单词，然后点击"确认"
    </p>

    <!-- Loading -->
    <div v-if="loading && words.length === 0" class="loading">加载中</div>

    <!-- Error -->
    <div v-else-if="error" class="error-msg">
      <p>⚠ {{ error }}</p>
      <button class="btn btn-primary btn-sm" style="margin-top: 12px" @click="loadFavorites">重试</button>
    </div>

    <!-- Empty -->
    <div v-else-if="words.length === 0" class="empty-state">
      <p>还没有收藏的单词</p>
      <p class="hint">去首页发现并收藏你的第一个单词吧！</p>
      <router-link to="/" class="btn btn-primary btn-sm" style="margin-top: 12px; text-decoration: none">
        去首页
      </router-link>
    </div>

    <!-- Word Grid: 6 columns -->
    <div v-else class="word-grid">
      <WordCard
        v-for="word in words"
        :key="word.id"
        :word="word"
        :show-favorite="false"
        :selectable="selecting"
        :selected="selectedIds.has(word.id)"
        @select="toggleSelect"
        @click="goToDetail"
      />
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="pagination">
      <button :disabled="page <= 1" @click="goToPage(page - 1)">上一页</button>
      <button
        v-for="p in totalPages"
        :key="p"
        :class="{ active: p === page }"
        @click="goToPage(p)"
      >
        {{ p }}
      </button>
      <button :disabled="page >= totalPages" @click="goToPage(page + 1)">下一页</button>
    </div>

    <!-- Level Selection Modal -->
    <div v-if="showLevelModal" class="modal-overlay" @click.self="showLevelModal = false">
      <div class="modal">
        <h2>选择文章级别</h2>
        <p style="color: var(--text-light); margin-bottom: 12px">
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
            <span style="display: block; font-size: 0.7rem; font-weight: 400; margin-top: 2px">
              {{ { N5: '最简单', N4: '简单', N3: '中等', N2: '较难', N1: '困难' }[level] }}
            </span>
          </button>
        </div>

        <div v-if="genError" class="error-msg" style="padding: 8px; font-size: 0.9rem">
          {{ genError }}
        </div>

        <div class="modal-actions">
          <button class="btn btn-outline" @click="showLevelModal = false" :disabled="generating">取消</button>
          <button
            class="btn btn-primary"
            :disabled="!articleLevel || generating"
            @click="confirmGenerate"
          >
            {{ generating ? '生成中...' : '确认生成' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.favorites {
  max-width: 1000px;
  margin: 0 auto;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.select-hint {
  color: var(--primary);
  font-size: 0.9rem;
  margin-bottom: 16px;
  padding: 8px 12px;
  background: #fff5f5;
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--primary);
}

.word-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

@media (min-width: 800px) {
  .word-grid {
    grid-template-columns: repeat(6, 1fr);
  }
}

@media (max-width: 600px) {
  .word-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.empty-state {
  text-align: center;
  padding: 60px;
  color: var(--text-light);
}

.hint {
  font-size: 0.85rem;
  margin-top: 8px;
}
</style>
