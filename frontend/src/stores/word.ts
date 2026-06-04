/** Word store — manages homepage cached words and favorite actions */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchRandomWords, toggleFavorite } from '@/api'
import type { CachedWord } from '@/types'

export const useWordStore = defineStore('word', () => {
  const currentWords = ref<CachedWord[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function loadRandomWords(count = 5) {
    loading.value = true
    error.value = null
    try {
      currentWords.value = await fetchRandomWords(count)
    } catch (e: any) {
      error.value = e?.response?.data?.detail || '获取单词失败，请检查后端服务是否运行'
      currentWords.value = []
    } finally {
      loading.value = false
    }
  }

  /** Toggle favorite — sends full word data as ext so backend can persist it */
  async function toggleWordFavorite(
    wordId: number,
    ext?: Record<string, any>,
  ): Promise<boolean> {
    try {
      const result = await toggleFavorite(wordId, ext)
      return result.is_favorited
    } catch {
      return false
    }
  }

  return { currentWords, loading, error, loadRandomWords, toggleWordFavorite }
})
