/** API client — communicates with the FastAPI backend */

import axios from 'axios'
import type { CachedWord, WordDetailResponse, Article, PaginatedResponse, LearnedTypeCounts } from '@/types'

const http = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

/** Generate or retrieve a stable session id (stored in localStorage) */
export function getSessionId(): string {
  const KEY = 'ai_jp_session_id'
  let sid = localStorage.getItem(KEY)
  if (!sid) {
    sid = crypto.randomUUID?.() || Math.random().toString(36).slice(2, 18)
    localStorage.setItem(KEY, sid)
  }
  return sid
}

/** Replace the session id with a new one — forces "换一批" to get different words.
 *  F5 / page refresh still reads the NEW id and finds its cache. */
export function refreshSessionId(): string {
  const KEY = 'ai_jp_session_id'
  const sid = crypto.randomUUID?.() || Math.random().toString(36).slice(2, 18)
  localStorage.setItem(KEY, sid)
  return sid
}

/** Get random words (session-cached via Redis — same session = same batch) */
export async function fetchRandomWords(count = 5): Promise<CachedWord[]> {
  const session_id = getSessionId()
  const { data } = await http.get('/words/random', {
    params: { count, session_id },
  })
  return data.words
}

/** Get word detail (from DB, for favorited words) */
export async function fetchWordDetail(id: number): Promise<WordDetailResponse> {
  const { data } = await http.get(`/words/${id}`)
  return data
}

/** Toggle word favorite status.  *ext* should contain the cached word data. */
export async function toggleFavorite(
  id: number,
  ext?: Record<string, any>,
): Promise<{ is_favorited: boolean; message: string }> {
  const { data } = await http.post(`/words/${id}/favorite`, { ext })
  return data
}

/** Get paginated favorites */
export async function fetchFavorites(page = 1, pageSize = 30): Promise<PaginatedResponse> {
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

// --- Learned words ---

/** Mark a favorited word as learned (favorite → learned) */
export async function markAsLearned(wordId: number): Promise<{ success: boolean; message: string }> {
  const { data } = await http.patch(`/favorites/${wordId}/learn`)
  return data
}

/** Get learned words, optionally filtered by type */
export async function fetchLearned(
  type?: string,
  page = 1,
  pageSize = 30,
): Promise<PaginatedResponse> {
  const params: any = { page, page_size: pageSize }
  if (type) params.type = type
  const { data } = await http.get('/learned', { params })
  return data
}

/** Get learned word counts per type */
export async function fetchLearnedTypeCounts(): Promise<LearnedTypeCounts> {
  const { data } = await http.get('/learned/types')
  return data
}

// --- SSE streaming ---

export interface SSEEvent {
  type: 'token' | 'done' | 'error'
  content?: string
  article_id?: number
  message?: string
}

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
            case 'token': onToken(event.content || ''); break
            case 'done': onDone(event.article_id || 0); return
            case 'error': onError(event.message || '未知错误'); return
          }
        } catch { /* skip malformed */ }
      }
    }
  } catch (e: any) {
    onError(e.message || '网络错误')
  }
}
