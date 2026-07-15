/** 共享常量 — 集中管理所有硬编码值和 localStorage key */

// ── localStorage / sessionStorage keys ───────────────────
export const STORAGE_KEYS = {
  TOKEN: 'ai_jp_token',
  REFRESH: 'ai_jp_refresh',
  USER: 'ai_jp_user',
  LLM_KEY: 'ai_jp_llm_key',
  PEXELS_KEY: 'ai_jp_pexels_key',
  SESSION_ID: 'ai_jp_session_id',
  IMG_SEARCH: 'ai_jp_img_search',
} as const

// ── JLPT level tabs (used in Favorites / Learned / Mastered) ──
export const TYPE_TABS = [
  { key: null as string | null, label: '全部' },
  { key: 'N5', label: 'N5' },
  { key: 'N4', label: 'N4' },
  { key: 'N3', label: 'N3' },
  { key: 'N2', label: 'N2' },
  { key: 'N1', label: 'N1' },
]

// ── Scene options (Home page scene selector) ──────────────
export const SCENES = [
  { key: '', label: '🌐 全部' },
  { key: '日常生活', label: '🏠 日常' },
  { key: '工作', label: '💼 工作' },
  { key: '商务', label: '🏢 商务' },
  { key: '影视剧', label: '🎬 影视' },
  { key: '动漫', label: '🎮 动漫' },
  { key: '旅游', label: '✈️ 旅游' },
]

// ── Pagination ───────────────────────────────────────────
export const PAGE_SIZE = 30
export const PAGE_SIZE_ADMIN = 20

// ── Image upload ─────────────────────────────────────────
export const MAX_IMAGE_SIZE = 10 * 1024 * 1024  // 10 MB
export const IMAGE_SEARCH_TIMEOUT = 120000       // 2 min
