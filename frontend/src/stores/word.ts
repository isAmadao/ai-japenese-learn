/** Word store — manages homepage cached words and favorite actions */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { fetchRandomWords, streamRandomWords, toggleFavorite } from '@/api'
import type { CachedWord } from '@/types'

export const useWordStore = defineStore('word', () => {
  const currentWords = ref<CachedWord[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const streaming = ref(false)
  const selectedScene = ref<string>('')

  // Favorited IDs (session-relative, 1-5) — shared between Home and WordDetail
  const favoritedIds = ref<number[]>([])

  function isWordFavorited(id: number): boolean {
    return favoritedIds.value.includes(id)
  }

  function setWordFavorited(id: number, fav: boolean) {
    if (fav) {
      if (!favoritedIds.value.includes(id)) {
        favoritedIds.value = [...favoritedIds.value, id]
      }
    } else {
      favoritedIds.value = favoritedIds.value.filter(v => v !== id)
    }
  }

  function setScene(scene: string) {
    selectedScene.value = scene
  }

  async function loadRandomWords(count = 5) {
    loading.value = true
    error.value = null
    streaming.value = false
    try {
      currentWords.value = await fetchRandomWords(count, selectedScene.value)
    } catch (e: any) {
      error.value = e?.response?.data?.detail || '获取单词失败，请检查后端服务是否运行'
      currentWords.value = []
    } finally {
      loading.value = false
    }
  }

  /** Load words via SSE streaming — progressively populates currentWords */
  async function loadRandomWordsStreaming(count = 5) {
    loading.value = true
    error.value = null
    streaming.value = true
    currentWords.value = []
    favoritedIds.value = []

    return new Promise<void>((resolve) => {
      streamRandomWords(
        count,
        selectedScene.value,
        // onWord — append each word as it arrives
        (word) => {
          currentWords.value = [...currentWords.value, word]
        },
        // onDone
        () => {
          loading.value = false
          streaming.value = false
          resolve()
        },
        // onError
        (message) => {
          error.value = message || '获取单词失败'
          loading.value = false
          streaming.value = false
          resolve()
        },
      )
    })
  }

  /** Toggle favorite — sends full word data as ext so backend can persist it.
   *  Returns the new favorited status. */
  async function toggleWordFavorite(
    wordId: number,
    ext?: Record<string, any>,
  ): Promise<boolean> {
    try {
      const result = await toggleFavorite(wordId, ext)
      setWordFavorited(wordId, result.is_favorited)
      return result.is_favorited
    } catch {
      return false
    }
  }

  // Word detail page uses this when navigating from Home (cached word)
  const clickedWord = ref<CachedWord | null>(null)
  const clickedWordFavorited = ref(false)

  return {
    currentWords, loading, error, streaming,
    selectedScene, setScene,
    favoritedIds, isWordFavorited, setWordFavorited,
    clickedWord, clickedWordFavorited,
    loadRandomWords, loadRandomWordsStreaming, toggleWordFavorite,
  }
})
