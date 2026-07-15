/** 共享工具函数 */

// ── N1-N5 级别颜色映射 ─────────────────────────────────
export function typeColor(type: string | null | undefined): string {
  const colors: Record<string, string> = {
    N5: '#52c41a', N4: '#1890ff', N3: '#faad14',
    N2: '#ff7a45', N1: '#f5222d',
  }
  return type && colors[type] ? colors[type] : '#888'
}

// ── sleep / delay ───────────────────────────────────────
export function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}
