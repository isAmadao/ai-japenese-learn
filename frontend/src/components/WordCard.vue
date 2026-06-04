<script setup lang="ts">
import type { CachedWord } from '@/types'
import { speakJapanese } from '@/utils/speech'

const props = withDefaults(defineProps<{
  word: CachedWord
  showFavorite?: boolean
  isFavorited?: boolean
  selectable?: boolean
  selected?: boolean
}>(), {
  showFavorite: true,
  isFavorited: false,
  selectable: false,
  selected: false,
})

const emit = defineEmits<{
  favorite: [id: number]
  select: [id: number]
  click: [id: number]
}>()
</script>

<template>
  <div
    class="word-card"
    :class="{ selected, selectable }"
    @click="emit('click', word.id)"
  >
    <div v-if="selectable" class="checkbox" @click.stop="emit('select', word.id)">
      <span class="checkmark" :class="{ checked: selected }">✓</span>
    </div>

    <div class="card-header">
      <div class="word-main">
        <h3 class="jp-text">{{ word.name }}</h3>
        <span class="kana">{{ word.kana }}</span>
      </div>
      <div class="card-actions">
        <button class="speak-btn" title="朗读" @click.stop="speakJapanese(word.name)">🔊</button>
        <button
          v-if="showFavorite"
          class="fav-btn"
          :class="{ favorited: isFavorited }"
          @click.stop="emit('favorite', word.id)"
          :title="isFavorited ? '取消收藏' : '收藏'"
        >
          {{ isFavorited ? '★' : '☆' }}
        </button>
      </div>
    </div>

    <p class="translation">{{ word.translation }}</p>
    <span v-if="word.type" class="type-badge">{{ word.type }}</span>

    <div class="examples">
      <div v-for="(sent, i) in word.example_sentences.slice(0, 2)" :key="i" class="example">
        <span class="ex-jp">{{ sent.japanese }}</span>
        <span class="ex-cn">{{ sent.chinese }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.word-card {
  background: var(--bg-card);
  border-radius: var(--radius);
  padding: 18px;
  box-shadow: var(--shadow);
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  border: 2px solid transparent;
}
.word-card:hover {
  box-shadow: var(--shadow-hover);
  transform: translateY(-2px);
}
.word-card.selectable { cursor: default; }
.word-card.selected { border-color: var(--primary); background: #fff5f5; }

.checkbox {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 2;
}
.checkmark {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px; height: 24px;
  border-radius: 50%;
  border: 2px solid var(--border);
  font-size: 0.8rem;
  color: transparent;
  transition: all 0.2s;
  background: white;
}
.checkmark.checked { background: var(--primary); border-color: var(--primary); color: white; }

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}
.word-main { flex: 1; }
.jp-text {
  font-size: 1.3rem;
  font-weight: 700;
  margin-bottom: 2px;
}
.kana { font-size: 0.85rem; color: var(--text-light); }
.card-actions { display: flex; gap: 6px; align-items: center; }

.fav-btn {
  background: none; border: none; font-size: 1.5rem; cursor: pointer;
  transition: transform 0.2s; color: var(--text-light);
}
.fav-btn:hover { transform: scale(1.2); }
.fav-btn.favorited { color: #f1c40f; }

.translation {
  font-size: 0.95rem; color: var(--accent); font-weight: 500;
  margin-bottom: 6px;
}
.type-badge {
  display: inline-block; font-size: 0.7rem; font-weight: 600;
  padding: 2px 8px; border-radius: 10px;
  background: var(--accent-light); color: var(--accent);
  margin-bottom: 8px;
}

.examples { display: flex; flex-direction: column; gap: 6px; }
.example {
  display: flex; flex-direction: column; gap: 1px;
  padding: 6px 8px; background: var(--bg); border-radius: 6px;
  font-size: 0.85rem;
}
.ex-jp { color: var(--text); }
.ex-cn { color: var(--text-light); font-size: 0.8rem; }
</style>
