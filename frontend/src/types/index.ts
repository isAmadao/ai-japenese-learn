/** Word types shared across the app */

export interface ExampleSentence {
  japanese: string
  chinese: string
}

export interface Word {
  id: number
  japanese: string
  kana: string
  chinese_meaning: string
  example_sentences: ExampleSentence[]
  created_at?: string
}

export interface WordDetail extends Word {
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
  words: Word[]
}

export interface PaginatedResponse<T> {
  words: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
