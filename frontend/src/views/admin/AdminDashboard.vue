<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchAdminStats } from '@/api'
import type { AdminStats } from '@/api'

const stats = ref<AdminStats | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    stats.value = await fetchAdminStats()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '加载失败'
  } finally {
    loading.value = false
  }
})

const levelColors: Record<string, string> = {
  N5: 'var(--grass)',
  N4: 'var(--grass-light)',
  N3: 'var(--golden)',
  N2: 'var(--warm-orange)',
  N1: 'var(--danger)',
}

const levelOrder = ['N5', 'N4', 'N3', 'N2', 'N1']

const maxTypeCount = (): number => {
  if (!stats.value?.words_by_type) return 1
  return Math.max(1, ...Object.values(stats.value.words_by_type))
}
</script>

<template>
  <div class="dashboard">
    <!-- Loading -->
    <div v-if="loading" class="loading">加载统计数据</div>

    <!-- Error -->
    <div v-else-if="error" class="error-msg">⚠ {{ error }}</div>

    <!-- Stats Cards -->
    <template v-else-if="stats">
      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-icon">👥</div>
          <div class="stat-body">
            <div class="stat-value">{{ stats.total_users }}</div>
            <div class="stat-label">总用户数</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">📖</div>
          <div class="stat-body">
            <div class="stat-value">{{ stats.total_words }}</div>
            <div class="stat-label">单词总数</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">⭐</div>
          <div class="stat-body">
            <div class="stat-value">{{ stats.total_favorites }}</div>
            <div class="stat-label">收藏次数</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">📄</div>
          <div class="stat-body">
            <div class="stat-value">{{ stats.total_articles }}</div>
            <div class="stat-label">文章总数</div>
          </div>
        </div>
      </div>

      <!-- JLPT Distribution -->
      <div class="section-card">
        <h2 class="section-title">📊 JLPT 级别分布</h2>
        <div v-if="Object.keys(stats.words_by_type).length === 0" class="section-empty">
          暂无单词分布数据
        </div>
        <div v-else class="level-bars">
          <div
            v-for="level in levelOrder"
            :key="level"
            v-show="stats.words_by_type[level] !== undefined"
            class="level-row"
          >
            <span class="level-label">{{ level }}</span>
            <div class="level-bar-track">
              <div
                class="level-bar-fill"
                :style="{
                  width: (stats.words_by_type[level] / maxTypeCount() * 100) + '%',
                  background: levelColors[level] || 'var(--golden)',
                }"
              ></div>
            </div>
            <span class="level-count">{{ stats.words_by_type[level] }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.dashboard {
  max-width: 900px;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 14px;
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  background: var(--bg-card);
  border: 4px solid var(--wood-dark);
  padding: 18px;
  box-shadow:
    inset -3px -3px 0 var(--wood-dark),
    inset 3px 3px 0 var(--wood-light);
}

.stat-icon {
  font-size: 2rem;
  width: 50px;
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--cream);
  border: 3px solid var(--wood-dark);
  flex-shrink: 0;
}

.stat-body {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-family: 'Press Start 2P', monospace;
  font-size: 1.3rem;
  color: var(--text);
  letter-spacing: 2px;
  line-height: 1.2;
}

.stat-label {
  font-size: 0.8rem;
  color: var(--text-light);
  margin-top: 4px;
}

/* Section card */
.section-card {
  background: var(--bg-card);
  border: 4px solid var(--wood-dark);
  padding: 20px;
  box-shadow:
    inset -3px -3px 0 var(--wood-dark),
    inset 3px 3px 0 var(--wood-light);
}

.section-title {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.6rem;
  color: var(--text);
  letter-spacing: 1px;
  margin-bottom: 16px;
}

.section-empty {
  text-align: center;
  padding: 24px;
  color: var(--text-muted);
  font-size: 0.85rem;
}

/* Level bars */
.level-bars {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.level-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.level-label {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.5rem;
  width: 36px;
  color: var(--text);
  text-align: right;
  flex-shrink: 0;
}

.level-bar-track {
  flex: 1;
  height: 20px;
  background: var(--cream);
  border: 3px solid var(--wood-dark);
  overflow: hidden;
}

.level-bar-fill {
  height: 100%;
  transition: width 0.6s ease;
  min-width: 4px;
}

.level-count {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.5rem;
  width: 40px;
  color: var(--text-light);
  flex-shrink: 0;
}
</style>
