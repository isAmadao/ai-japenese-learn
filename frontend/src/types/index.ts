/** Types matching backend schemas (v2 — name/translation instead of japanese/chinese_meaning) */

export interface ExampleSentence {
  japanese: string
  chinese: string
}

/** CachedWord — from Redis session cache (not yet persisted to DB) */
export interface CachedWord {
  id: number
  db_id?: number | null
  name: string
  kana: string
  translation: string
  description?: string | null
  type?: string | null
  example_sentences: ExampleSentence[]
  scene: string[]
  created_at?: string | null
}

/** WordResponse — from DB (favorited words) */
export interface WordResponse {
  id: number
  name: string
  kana: string
  translation: string
  description?: string | null
  type?: string | null
  example_sentences: ExampleSentence[]
  image_url?: string | null
  scene: string[]
  ext?: Record<string, any> | null
  created_at?: string | null
}

export interface WordDetailResponse extends WordResponse {
  is_favorited: boolean
  favorited_at?: string | null
  articles: ArticleBrief[]
}

export interface ArticleBrief {
  id: number
  title: string
  level: string
}

export interface Article {
  id: number
  title: string
  content_japanese: string
  content_chinese: string
  level: string
  image_url?: string | null
  created_at?: string
  words: WordResponse[]
}


export interface PaginatedResponse {
  words: WordResponse[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface LearnedTypeCounts {
  N5: number
  N4: number
  N3: number
  N2: number
  N1: number
  [key: string]: number
}

// ── Auth / Registration ──────────────────────────────────────

export interface CaptchaChallenge {
  id: string
  type: 'math' | 'emoji' | 'color'
  data: CaptchaData
}

export type CaptchaData =
  | { question: string }                              // math
  | { question: string; options: string[] }           // emoji / color

export interface VerifyCaptchaResult {
  captcha_token: string
  message: string
}

export interface SendCodeResult {
  success: boolean
  message: string
  cooldown: number
  resend_token?: string
}

export interface VerifyCodeResult {
  verified: boolean
  register_token: string
  message: string
}

// ── Search ─────────────────────────────────────────────────────

export interface SearchResultItem {
  id: number
  name: string
  kana: string
  translation: string
  description?: string | null
  type?: string | null
  score: number
}

export interface SearchResponse {
  results: SearchResultItem[]
  total: number
  query: string
}

// ── Image Search ─────────────────────────────────────────────────

export interface ImageSearchResponse {
  results: SearchResultItem[]
  total: number
  query: string
  ocr_texts: string[]
  scene: string
  usable: boolean
  saved_to_gallery: boolean
  processing_time_ms: number
  message?: string
}
