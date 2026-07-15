/**
 * highlight.ts — 在日语文本中高亮指定的单词
 */

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function escapeRegex(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * 在文本中高亮指定的单词列表
 * @param text  原始日语文本
 * @param words 要高亮的单词列表（按长度降序匹配，长词优先）
 * @returns     包含 <span class="highlight-word"> 标签的 HTML 字符串
 */
export function highlightWords(text: string, words: string[]): string {
  if (!text) return ''
  if (!words.length) return escapeHtml(text)

  // 去重并按长度降序排列，优先匹配长词避免部分匹配
  const unique = [...new Set(words)]
    .filter(w => w.length > 0)
    .sort((a, b) => b.length - a.length)

  if (!unique.length) return escapeHtml(text)

  const escaped = escapeHtml(text)
  const pattern = unique
    .map(w => escapeRegex(escapeHtml(w)))
    .join('|')

  const regex = new RegExp(`(${pattern})`, 'g')
  return escaped.replace(regex, '<span class="highlight-word">$1</span>')
}
