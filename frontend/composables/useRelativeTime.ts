const DAY = 86_400_000

export function relativeTimeHe(iso?: string | null): string {
  if (!iso) return '—'
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return '—'
  const diff = Date.now() - t
  if (diff < 0) return 'עתידי'
  const days = Math.floor(diff / DAY)
  if (days === 0) return 'היום'
  if (days === 1) return 'אתמול'
  if (days < 7) return `לפני ${days} ימים`
  if (days < 30) return `לפני ${Math.floor(days / 7)} שבועות`
  if (days < 365) return `לפני ${Math.floor(days / 30)} חודשים`
  return `לפני ${Math.floor(days / 365)} שנים`
}

export function formatBytes(size?: number | null): string {
  if (!size) return '—'
  if (size < 1024) return `${size} B`
  if (size < 1024 ** 2) return `${(size / 1024).toFixed(0)} KB`
  if (size < 1024 ** 3) return `${(size / 1024 ** 2).toFixed(1)} MB`
  return `${(size / 1024 ** 3).toFixed(2)} GB`
}

export function formatNumber(n?: number | null): string {
  if (n == null) return '—'
  return n.toLocaleString('he-IL')
}
