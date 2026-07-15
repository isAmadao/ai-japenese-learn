/** API client — communicates with the FastAPI backend */

import axios from 'axios'
import type { CachedWord, WordDetailResponse, Article, PaginatedResponse, LearnedTypeCounts, CaptchaChallenge, VerifyCaptchaResult, SendCodeResult, VerifyCodeResult, SearchResponse, ImageSearchResponse } from '@/types'

export const http = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// ── API Keys (user-provided, stored in localStorage) ────────

const LLM_KEY = 'ai_jp_llm_key'
const PEXELS_KEY = 'ai_jp_pexels_key'

export function getApiKey(): string { return localStorage.getItem(LLM_KEY) || '' }
export function setApiKey(k: string): void {
  if (k) localStorage.setItem(LLM_KEY, k); else localStorage.removeItem(LLM_KEY)
}
export function hasApiKey(): boolean { return !!getApiKey() }

export function getPexelsKey(): string { return localStorage.getItem(PEXELS_KEY) || '' }
export function setPexelsKey(k: string): void {
  if (k) localStorage.setItem(PEXELS_KEY, k); else localStorage.removeItem(PEXELS_KEY)
}

// ── Auth token interceptor ──────────────────────────────
// Automatically attach Bearer token if available.

http.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('ai_jp_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// ── Refresh token lock ────────────────────────────────
// Prevents multiple concurrent refresh attempts.

let _refreshing = false
interface RefreshQueueItem {
  resolve: (v: any) => void
  reject: (e: any) => void
  config: any  // the original request config — retry with this, not the first request's
}
let _refreshQueue: RefreshQueueItem[] = []

function _doRefresh(): Promise<string | null> {
  const rt = localStorage.getItem('ai_jp_refresh')
  if (!rt) return Promise.resolve(null)

  return axios.post('/api/auth/refresh', { refresh_token: rt })
    .then(res => {
      const { access_token, refresh_token } = res.data
      localStorage.setItem('ai_jp_token', access_token)
      if (refresh_token) localStorage.setItem('ai_jp_refresh', refresh_token)
      return access_token
    })
    .catch(() => {
      localStorage.removeItem('ai_jp_token')
      localStorage.removeItem('ai_jp_refresh')
      localStorage.removeItem('ai_jp_user')
      return null
    })
}

// ── Response interceptor ──────────────────────────────
// 1. Network errors: retry
// 2. 401: try refresh token, then retry.  If refresh fails → /login

let retryCount = 0

http.interceptors.response.use(
  (res) => {
    retryCount = 0
    return res
  },
  async (err) => {
    const cfg = err.config

    // ── 401 — try refresh ─────────────────────────────
    if (err.response?.status === 401 && !cfg._retried) {
      // Skip refresh for the /auth/refresh endpoint itself
      if (cfg.url === '/auth/refresh') {
        if (!window.location.pathname.startsWith('/login')) {
          window.location.href = '/login'
        }
        return Promise.reject(err)
      }

      cfg._retried = true

      if (!_refreshing) {
        _refreshing = true
        const newToken = await _doRefresh()
        _refreshing = false

        if (newToken) {
          // Retry original request with new token
          cfg.headers.Authorization = `Bearer ${newToken}`
          // Resolve queued requests — each with its OWN config (fixes bug
          // where GETs were replayed as the first queued request's method/URL)
          _refreshQueue.forEach(q => {
            q.config.headers.Authorization = `Bearer ${newToken}`
            q.resolve(http(q.config))
          })
          _refreshQueue = []
          return http(cfg)
        }

        // Refresh failed — reject all queued
        _refreshQueue.forEach(q => q.reject(err))
        _refreshQueue = []
        if (!window.location.pathname.startsWith('/login')) {
          window.location.href = '/login'
        }
        return Promise.reject(err)
      }

      // Another refresh is in progress — queue this request with its own config
      return new Promise((resolve, reject) => {
        _refreshQueue.push({ resolve, reject, config: cfg })
      })
    }

    // ── Network retry ─────────────────────────────────
    if (!err.response && !cfg._retryCount) {
      cfg._retryCount = cfg._retryCount || 0
      const isGet = cfg.method === 'get'
      const maxRetries = isGet ? 2 : 1
      if (cfg._retryCount < maxRetries) {
        cfg._retryCount++
        const delay = isGet
          ? (cfg._retryCount === 1 ? 500 : 1000)
          : 1000
        await new Promise(r => setTimeout(r, delay))
        return http(cfg)
      }
    }
    retryCount = 0
    return Promise.reject(err)
  },
)

/** Ensure a fresh auth token exists — silently refreshes if needed.
 *  Returns the token, or null if the user is unauthenticated. */
async function _ensureAuthToken(): Promise<string | null> {
  let token = localStorage.getItem('ai_jp_token')
  if (!token) return null

  // If we have a refresh token, try to use it proactively to get a fresh
  // access token before starting the SSE connection.
  const rt = localStorage.getItem('ai_jp_refresh')
  if (rt) {
    try {
      const res = await axios.post('/api/auth/refresh', { refresh_token: rt })
      const { access_token, refresh_token } = res.data
      localStorage.setItem('ai_jp_token', access_token)
      if (refresh_token) localStorage.setItem('ai_jp_refresh', refresh_token)
      return access_token
    } catch {
      // Refresh failed — use existing token (may be valid still)
      return token
    }
  }
  return token
}

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
export async function fetchRandomWords(count = 5, scene = ''): Promise<CachedWord[]> {
  const session_id = getSessionId()
  const params: Record<string, any> = { count, session_id }
  if (scene) params.scene = scene
  const { data } = await http.get('/words/random', { params })
  return data.words
}

/** Search words via Elasticsearch (BM25 keyword + vector semantic).
 *
 *  Uses a local embedding model — no API key needed.
 */
export async function searchWords(
  q: string,
  top_k = 20,
): Promise<SearchResponse> {
  const { data } = await http.get('/words/search', { params: { q, top_k } })
  return data
}

/** Stream random words via SSE — yields each word as it arrives */
export async function streamRandomWords(
  count: number,
  scene = '',
  onWord: (word: CachedWord) => void,
  onDone: () => void,
  onError: (message: string) => void,
): Promise<void> {
  const session_id = getSessionId()
  let url = `/api/words/random/stream?count=${count}&session_id=${session_id}`
  if (scene) url += `&scene=${encodeURIComponent(scene)}`
  const token = await _ensureAuthToken()
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`

  async function connect(attempt: number): Promise<void> {
    try {
      const response = await fetch(url, { headers })
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: '请求失败' }))
        // On 401, try refreshing the token and retry
        if (response.status === 401 && attempt < 2) {
          const newToken = await _ensureAuthToken()
          if (newToken) headers['Authorization'] = `Bearer ${newToken}`
          await new Promise(r => setTimeout(r, 1000))
          return connect(attempt + 1)
        }
        if (attempt < 2) {
          await new Promise(r => setTimeout(r, 1000))
          return connect(attempt + 1)
        }
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
            const event = JSON.parse(part.slice(6))
            switch (event.type) {
              case 'word': onWord(event.word); break
              case 'done': onDone(); return
              case 'error': onError(event.message || '未知错误'); return
            }
          } catch { /* skip malformed */ }
        }
      }
    } catch (e: any) {
      if (attempt < 2) {
        await new Promise(r => setTimeout(r, 1000))
        return connect(attempt + 1)
      }
      onError(e.message || '网络错误')
    }
  }

  return connect(1)
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

// --- Auth ---

export interface AuthResponse {

export async function fetchCaptcha(): Promise<CaptchaChallenge> {
  const { data } = await http.get('/auth/captcha')
  return data
}

export async function verifyCaptcha(id: string, answer: string): Promise<VerifyCaptchaResult> {
  const { data } = await http.post('/auth/captcha/verify', { id, answer })
  return data
}

export async function sendVerificationCode(email: string, captchaToken: string): Promise<SendCodeResult> {
  const { data } = await http.post('/auth/send-code', { email, captcha_token: captchaToken })
  return data
}

export async function verifyEmailCode(email: string, code: string): Promise<VerifyCodeResult> {
  const { data } = await http.post('/auth/verify-code', { email, code })
  return data
}

export async function registerWithEmail(
  nickname: string,
  email: string,
  password: string,
  registerToken: string,
): Promise<AuthResponse> {
  const { data } = await http.post('/auth/register/email', {
    nickname,
    email,
    password,
    register_token: registerToken,
  })
  return data
}

// --- Profile settings ---

export async function updateProfile(nickname: string): Promise<{ id: number; username: string; email: string }> {
  const { data } = await http.put('/auth/profile', { nickname })
  return data
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<{ success: boolean; message: string }> {
  const { data } = await http.put('/auth/password', { current_password: currentPassword, new_password: newPassword })
  return data
}

export async function checkNicknameAvailable(nickname: string): Promise<{ available: boolean }> {
  const { data } = await http.get('/auth/check-nickname', { params: { nickname } })
  return data
}

export async function resendVerificationCode(email: string, resendToken: string): Promise<SendCodeResult> {
  const { data } = await http.post('/auth/resend-code', null, {
    params: { email, resend_token: resendToken },
  })
  return data
}

// --- Forgot Password ---

export async function forgotPasswordSendCode(email: string, captchaToken: string): Promise<{ success: boolean; message: string; cooldown: number }> {
  const { data } = await http.post('/auth/forgot-password/send-code', { email, captcha_token: captchaToken })
  return data
}

export async function forgotPasswordReset(email: string, code: string, newPassword: string): Promise<{ success: boolean; message: string }> {
  const { data } = await http.post('/auth/forgot-password/reset', { email, code, new_password: newPassword })
  return data
}

/** Get paginated favorites, optionally filtered by type (N5-N1) */
export async function fetchFavorites(page = 1, pageSize = 30, type?: string): Promise<PaginatedResponse> {
  const params: Record<string, any> = { page, page_size: pageSize }
  if (type) params.type = type
  const { data } = await http.get('/favorites', { params })
  return data
}

/** Get article detail */
export async function fetchArticle(id: number): Promise<Article> {
  const { data } = await http.get(`/articles/${id}`)
  return data
}

/** Generate/replace the Pexels illustration for a word */
export async function generateWordImage(wordId: number, pexelsKey?: string): Promise<{ success: boolean; image_url?: string; message?: string }> {
  const body: Record<string, any> = {}
  if (pexelsKey) body.pexels_key = pexelsKey
  const { data } = await http.post(`/words/${wordId}/image`, body)
  return data
}

/** CLIP 智能配图 — 语义匹配最佳图片 */
export async function smartWordImage(wordId: number, pexelsKey?: string): Promise<{ success: boolean; image_url?: string; method?: string; message?: string }> {
  const body: Record<string, any> = {}
  if (pexelsKey) body.pexels_key = pexelsKey
  const { data } = await http.post(`/words/${wordId}/smart-image`, body)
  return data
}

/** 图片搜索单词 — 上传图片，OCR 识别日语文字并搜索 */
export async function searchWordsByImage(file: File): Promise<ImageSearchResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('api_key', getApiKey())
  const { data } = await http.post('/words/search-by-image', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000, // 2 minutes — OCR + LLM can be slow
  })
  return data
}

/** Replace the Pexels illustration for an article */
export async function generateArticleImage(articleId: number, pexelsKey?: string): Promise<{ success: boolean; image_url?: string; message?: string }> {
  const body: Record<string, any> = {}
  if (pexelsKey) body.pexels_key = pexelsKey
  const { data } = await http.post(`/articles/${articleId}/image`, body)
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

// --- Mastered words ---

/** Mark a learned word as mastered (learned → mastered) */
export async function markAsMastered(wordId: number): Promise<{ success: boolean; message: string }> {
  const { data } = await http.patch(`/learned/${wordId}/master`)
  return data
}

/** Get mastered words, optionally filtered by type */
export async function fetchMastered(
  type?: string,
  page = 1,
  pageSize = 30,
): Promise<PaginatedResponse> {
  const params: any = { page, page_size: pageSize }
  if (type) params.type = type
  const { data } = await http.get('/mastered', { params })
  return data
}

/** Get mastered word counts per type */
export async function fetchMasteredTypeCounts(): Promise<LearnedTypeCounts> {
  const { data } = await http.get('/mastered/types')
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
  apiKey: string | undefined,
  onToken: (text: string) => void,
  onDone: (articleId: number) => void,
  onError: (message: string) => void,
  options?: { content_type?: string; style?: string; source?: string; pexels_key?: string },
): Promise<void> {
  async function connect(attempt: number): Promise<void> {
    try {
      const token = await _ensureAuthToken()
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`
      const body: any = { word_ids: wordIds, level }
      if (apiKey) body.api_key = apiKey
      if (options?.content_type) body.content_type = options.content_type
      if (options?.style) body.style = options.style
      if (options?.source) body.source = options.source
      if (options?.pexels_key) body.pexels_key = options.pexels_key
      const response = await fetch('/api/articles/generate-stream', {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
      })
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: '请求失败' }))
        // On 401, try refreshing the token and retry
        if (response.status === 401 && attempt < 2) {
          const newToken = await _ensureAuthToken()
          if (newToken) headers['Authorization'] = `Bearer ${newToken}`
          await new Promise(r => setTimeout(r, 1500))
          return connect(attempt + 1)
        }
        if (attempt < 2) {
          await new Promise(r => setTimeout(r, 1500))
          return connect(attempt + 1)
        }
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
      if (attempt < 2) {
        await new Promise(r => setTimeout(r, 1500))
        return connect(attempt + 1)
      }
      onError(e.message || '网络错误')
    }
  }

  return connect(1)
}

// --- Dictionary upgrade ---

export interface DictionaryStatus {
  mecab_installed: boolean
  current: string
  description: string
}

/** Check current dictionary status (pykakasi vs MeCab) */
export async function fetchDictionaryStatus(): Promise<DictionaryStatus> {
  const { data } = await http.get('/settings/dictionary')
  return data
}

/** Upgrade to MeCab dictionary for better rare-kanji accuracy */
export async function upgradeDictionary(): Promise<{ success: boolean; message: string }> {
  const { data } = await http.post('/settings/dictionary/upgrade')
  return data
}

/** Stream upgrade progress via SSE */
export async function streamUpgradeDictionary(
  onProgress: (text: string) => void,
  onDone: (message: string) => void,
  onError: (message: string) => void,
): Promise<void> {
  async function connect(attempt: number): Promise<void> {
    try {
      const token = await _ensureAuthToken()
      const headers: Record<string, string> = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      const response = await fetch('/api/settings/dictionary/upgrade', { headers })
      if (!response.ok) {
        if (attempt < 2) {
          await new Promise(r => setTimeout(r, 1500))
          return connect(attempt + 1)
        }
        onError(`HTTP ${response.status}`)
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
            const event = JSON.parse(part.slice(6))
            switch (event.type) {
              case 'progress': onProgress(event.text || ''); break
              case 'done': onDone(event.message || '升级成功'); return
              case 'error': onError(event.message || '未知错误'); return
            }
          } catch { /* skip */ }
        }
      }
    } catch (e: any) {
      if (attempt < 2) {
        await new Promise(r => setTimeout(r, 1500))
        return connect(attempt + 1)
      }
      onError(e.message || '网络错误')
    }
  }

  return connect(1)
}

/** Rollback to pykakasi */
export async function rollbackDictionary(): Promise<{ success: boolean; message: string }> {
  const { data } = await http.post('/settings/dictionary/rollback')
  return data
}

/** 「句子换新」— 用 AI 重新生成单词的例句 */
export async function refreshWordSentences(
  wordId: number,
  apiKey?: string,
  options?: { content_type?: string; style?: string; source?: string; pexels_key?: string },
): Promise<{
  success: boolean
  message: string
  example_sentences?: Array<{ japanese: string; chinese: string }>
  image_url?: string | null
}> {
  const body: Record<string, any> = {}
  if (apiKey) body.api_key = apiKey
  if (options?.content_type) body.content_type = options.content_type
  if (options?.style) body.style = options.style
  if (options?.source) body.source = options.source
  if (options?.pexels_key) body.pexels_key = options.pexels_key
  const { data } = await http.post(`/words/${wordId}/refresh-sentences`, body)
  return data
}

// ── Admin dashboard ──────────────────────────────────────────────

export interface AdminStats {
  total_users: number
  total_words: number
  total_favorites: number
  total_articles: number
  words_by_type: Record<string, number>
}

export interface AdminUserItem {
  id: number
  username: string
  email: string
  role: string
  is_verified: boolean
  deleted: boolean
  created_at?: string | null
  favorite_count: number
  learned_count: number
}

export interface AdminWordItem {
  id: number
  name: string
  kana: string
  translation: string
  type?: string | null
  favorite_count: number
  created_at?: string | null
}

export interface AdminArticleItem {
  id: number
  title: string
  level: string
  word_count: number
  created_at?: string | null
}

export interface AdminPaginatedResponse<T> {
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface AdminUserListResponse extends AdminPaginatedResponse<AdminUserItem> {
  users: AdminUserItem[]
}

export interface AdminWordListResponse extends AdminPaginatedResponse<AdminWordItem> {
  words: AdminWordItem[]
}

export interface AdminArticleListResponse extends AdminPaginatedResponse<AdminArticleItem> {
  articles: AdminArticleItem[]
}

export async function fetchAdminStats(): Promise<AdminStats> {
  const { data } = await http.get('/admin/stats')
  return data
}

export async function fetchAdminUsers(page = 1, pageSize = 30, showDeleted = false): Promise<AdminUserListResponse> {
  const { data } = await http.get('/admin/users', { params: { page, page_size: pageSize, show_deleted: showDeleted } })
  return data
}

export async function adminDeleteUser(userId: number): Promise<{ success: boolean; message: string }> {
  const { data } = await http.post(`/admin/users/${userId}/delete`)
  return data
}

export async function adminRestoreUser(userId: number): Promise<{ success: boolean; message: string }> {
  const { data } = await http.post(`/admin/users/${userId}/restore`)
  return data
}

export async function fetchAdminWords(page = 1, pageSize = 30, type?: string): Promise<AdminWordListResponse> {
  const params: Record<string, any> = { page, page_size: pageSize }
  if (type) params.type = type
  const { data } = await http.get('/admin/words', { params })
  return data
}

export async function fetchAdminArticles(page = 1, pageSize = 30): Promise<AdminArticleListResponse> {
  const { data } = await http.get('/admin/articles', { params: { page, page_size: pageSize } })
  return data
}
