/** API client — communicates with the FastAPI backend */

import axios from 'axios'
import type { Word, WordDetail, Article, PaginatedResponse } from '@/types'

const http = axios.create({
  baseURL: '/api',
  timeout: 60000, // LLM generation can be slow
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

/** Generate article from selected words */
export async function generateArticle(wordIds: number[], level: string): Promise<Article> {
  const { data } = await http.post('/articles/generate', { word_ids: wordIds, level })
  return data.article
}

/** Get article detail */
export async function fetchArticle(id: number): Promise<Article> {
  const { data } = await http.get(`/articles/${id}`)
  return data
}
