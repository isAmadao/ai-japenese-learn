/** API client — communicates with the FastAPI backend */

import axios from 'axios'
import type { Word, WordDetail, Article, PaginatedResponse } from '@/types'

const http = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

/** Get random words (excluding favorited) */
export async function fetchRandomWords(count = 5): Promise<Word[]> {
  const { data } = await http.get('/words/random', { params: { count } })
  return data.words
}

/** Get word detail with favorite status and related articles */
export async function fetchWordDetail(id: number): Promise<WordDetail> {
  const { data } = await http.get(`/words/${id}`)
  return data
}

/** Toggle word favorite status */
export async function toggleFavorite(id: number): Promise<{ is_favorited: boolean; message: string }> {
  const { data } = await http.post(`/words/${id}/favorite`)
  return data
}

/** Get paginated favorites */
export async function fetchFavorites(page = 1, pageSize = 30): Promise<PaginatedResponse<Word>> {
  const { data } = await http.get('/favorites', { params: { page, page_size: pageSize } })
  return data
}

/** Generate article from selected words (synchronous — full result at once) */
export async function generateArticle(wordIds: number[], level: string): Promise<Article> {
  const { data } = await http.post('/articles/generate', { word_ids: wordIds, level })
  return data.article
}

/** Get article detail */
export async function fetchArticle(id: number): Promise<Article> {
  const { data } = await http.get(`/articles/${id}`)
  return data
}

// --- SSE streaming for article generation ---

export interface SSEEvent {
  type: 'token' | 'done' | 'error'
  content?: string
  article_id?: number
  message?: string
}

/**
 * Generate article via SSE streaming.
 * Calls onToken for each chunk, onDone when finished, onError on failure.
 */
export async function generateArticleStream(
  wordIds: number[],
  level: string,
  onToken: (text: string) => void,
  onDone: (articleId: number) => void,
  onError: (message: string) => void,
): Promise<void> {
  try {
    const response = await fetch('/api/articles/generate-stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ word_ids: wordIds, level }),
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: '请求失败' }))
      onError(err.detail || `HTTP ${response.status}`)
      return
    }

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''

      for (const part of parts) {
        if (!part.startsWith('data: ')) continue
        try {
          const event: SSEEvent = JSON.parse(part.slice(6))
          switch (event.type) {
            case 'token':
              onToken(event.content || '')
              break
            case 'done':
              onDone(event.article_id || 0)
              return
            case 'error':
              onError(event.message || '未知错误')
              return
          }
        } catch {
          // skip malformed events
        }
      }
    }
  } catch (e: any) {
    onError(e.message || '网络错误')
  }
}
