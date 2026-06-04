/** Types matching backend schemas (v2 — name/translation instead of japanese/chinese_meaning) */

export interface ExampleSentence {
  japanese: string
  chinese: string
}

/** CachedWord — from Redis session cache (not yet persisted to DB) */
export interface CachedWord {
  id: number
  name: string
  kana: string
  translation: string
  description?: string
  type?: string
  example_sentences: ExampleSentence[]
  created_at?: string
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
