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
      <span class="checkmark" :class="{ checked: selected }">✦</span>
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
    <div class="badge-row">
      <span v-if="word.type" class="type-badge">{{ word.type }}</span>
      <span v-for="s in (word.scene || [])" :key="s" class="scene-badge">{{ s }}</span>
    </div>

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
  border: 4px solid var(--wood-dark);
  padding: 18px;
  cursor: pointer;
  transition: all 0.15s step-start;
  position: relative;
  box-shadow:
    inset -3px -3px 0 var(--wood-dark),
    inset 3px 3px 0 var(--wood-light),
    2px 3px 0 rgba(60,40,20,0.1);
}
.word-card:hover {
  transform: translateY(-2px);
  box-shadow:
    inset -3px -3px 0 var(--wood-dark),
    inset 3px 3px 0 var(--wood-light),
    3px 4px 0 rgba(60,40,20,0.15);
}
.word-card.selectable { cursor: default; }
.word-card.selected {
  border-color: var(--golden);
  background: #FFF8E0;
  box-shadow:
    inset -3px -3px 0 var(--wood-dark),
    inset 3px 3px 0 var(--golden-light),
    2px 3px 0 rgba(200,160,48,0.2);
}

.checkbox {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 2;
}
.checkmark {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  background: var(--cream);
  border: 3px solid var(--wood-dark);
  font-size: 0.7rem;
  color: transparent;
  transition: all 0.05s step-start;
  box-shadow: 1px 1px 0 var(--wood-dark);
}
.checkmark.checked {
  background: var(--golden);
  border-color: var(--warm-brown-dark);
  color: var(--text);
  box-shadow: 1px 1px 0 var(--warm-brown-dark);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}
.word-main { flex: 1; }
.jp-text {
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 4px;
  color: var(--text);
}
.kana { font-size: 1rem; color: var(--text-light); }
.card-actions { display: flex; gap: 6px; align-items: center; }

.fav-btn {
  background: none;
  border: 3px solid var(--wood-dark);
  font-size: 1.4rem;
  width: 38px;
  height: 38px;
  cursor: pointer;
  transition: all 0.05s step-start;
  color: var(--text-muted);
  background: var(--cream);
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
}

.translation {
  font-size: 1.1rem;
  color: var(--warm-brown);
  font-weight: 600;
  margin-bottom: 8px;
}
.type-badge {
  margin-bottom: 10px;
}
.badge-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}
.scene-badge {
  font-size: 0.6rem;
  font-family: 'Press Start 2P', monospace;
  padding: 3px 7px;
  border: 2px solid var(--golden);
  color: var(--golden);
  background: rgba(255, 215, 0, 0.06);
}

.examples { display: flex; flex-direction: column; gap: 8px; }
.example {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 12px;
  background: var(--cream);
  border: 2px solid var(--wood-light);
  font-size: 0.95rem;
}
.ex-jp { color: var(--text); font-weight: 500; }
.ex-cn { color: var(--text-light); font-size: 0.85rem; }
</style>
