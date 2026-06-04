/** Word store — manages homepage words and favorite cache */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchRandomWords, toggleFavorite } from '@/api'
import type { Word } from '@/types'

export const useWordStore = defineStore('word', () => {
  const currentWords = ref<Word[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  /** Load random words from backend */
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

  /** Toggle favorite and return new status */
  async function toggleWordFavorite(wordId: number): Promise<boolean> {
    try {
      const result = await toggleFavorite(wordId)
      return result.is_favorited
    } catch {
      return false
    }
  }

  return { currentWords, loading, error, loadRandomWords, toggleWordFavorite }
})
