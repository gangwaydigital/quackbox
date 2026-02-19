import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Paperclip, MessageSquare } from 'lucide-react'

function highlightText(text, query) {
  if (!query || !text) return text
  const words = query.trim().split(/\s+/).filter(w => w.length > 2)
  if (words.length === 0) return text
  const escaped = words.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')
  const pattern = new RegExp(`(${escaped})`, 'gi')
  const parts = text.split(pattern)
  const matchTest = new RegExp(`^(?:${escaped})$`, 'i')
  return parts.map((part, i) =>
    matchTest.test(part) ? <mark key={i} className="search-highlight">{part}</mark> : part
  )
}

function Skeleton({ className = '' }) {
  return <div className={`skeleton ${className}`}>&nbsp;</div>
}

function LoadingSkeleton() {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 divide-y divide-gray-100 dark:divide-gray-800">
      {Array.from({ length: 8 }, (_, i) => (
        <div key={i} className="px-4 py-3 space-y-2">
          <div className="flex items-center gap-3">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-3 w-48 hidden sm:block" />
          </div>
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      ))}
    </div>
  )
}

/**
 * EmailTable
 *
 * Props:
 *   emails, loading, pagination, onPageChange, searchQuery  — same as before
 *   onSelect(email)  — if provided, rows call this instead of navigating
 *   selectedId       — id of the currently selected email (for highlight)
 */
export default function EmailTable({
  emails, loading, pagination, onPageChange,
  searchQuery = '', onSelect = null, selectedId = null,
}) {
  if (loading) return <LoadingSkeleton />
  if (!emails.length) return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-12 text-center text-gray-500">
      No emails found.
    </div>
  )

  const rowClass = (email) => {
    const base = 'block w-full text-left px-4 py-3 transition-colors'
    const active = selectedId && String(email.id) === String(selectedId)
    if (active) return `${base} bg-blue-50 dark:bg-blue-900/30 border-l-2 border-blue-500`
    return `${base} hover:bg-gray-50 dark:hover:bg-gray-800 border-l-2 border-transparent`
  }

  const rowContent = (email) => (
    <div className="flex items-start justify-between gap-4">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-medium text-sm text-gray-900 dark:text-gray-100 truncate">
            {highlightText(email.sender_name || email.sender_email || 'Unknown', searchQuery)}
          </span>
          {email.has_attachments && <Paperclip className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />}
          {email.thread_group_id && (
            <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-blue-50 dark:bg-blue-900/40 text-blue-600 dark:text-blue-300 rounded text-[10px] font-medium flex-shrink-0">
              <MessageSquare className="w-2.5 h-2.5" />thread
            </span>
          )}
        </div>
        <div className="text-sm text-gray-800 dark:text-gray-200 truncate mt-0.5">
          {email.highlight_subject
            ? <span dangerouslySetInnerHTML={{ __html: email.highlight_subject }} />
            : highlightText(email.subject || '(no subject)', searchQuery)}
        </div>
        {email.highlight_body
          ? <div className="text-xs text-gray-400 mt-0.5 truncate search-preview-hl" dangerouslySetInnerHTML={{ __html: email.highlight_body }} />
          : email.snippet && <div className="text-xs text-gray-400 truncate mt-0.5">{highlightText(email.snippet, searchQuery)}</div>}
      </div>
      <div className="text-xs text-gray-400 whitespace-nowrap flex-shrink-0">{formatDate(email.date_sent)}</div>
    </div>
  )

  return (
    <div className="space-y-3">
      <div className="text-sm text-gray-500 dark:text-gray-400">
        {pagination.total.toLocaleString()} email{pagination.total !== 1 ? 's' : ''}
      </div>
      <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 divide-y divide-gray-100 dark:divide-gray-800 overflow-hidden">
        {emails.map((email) =>
          onSelect ? (
            <button key={email.id} className={rowClass(email)} onClick={() => onSelect(email)}>
              {rowContent(email)}
            </button>
          ) : (
            <Link key={email.id} to={`/email/${email.id}`} className={rowClass(email)}>
              {rowContent(email)}
            </Link>
          )
        )}
      </div>
      {pagination.total_pages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-500">Page {pagination.page} of {pagination.total_pages}</span>
          <div className="flex gap-2">
            <button onClick={() => onPageChange(pagination.page - 1)} disabled={pagination.page <= 1}
              className="flex items-center gap-1 px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-md disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800">
              <ChevronLeft className="w-4 h-4" /> Prev
            </button>
            <button onClick={() => onPageChange(pagination.page + 1)} disabled={pagination.page >= pagination.total_pages}
              className="flex items-center gap-1 px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-md disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800">
              Next <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function formatDate(isoString) {
  if (!isoString) return ''
  try {
    const date = new Date(isoString)
    const now = new Date()
    const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24))
    if (diffDays === 0) return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    if (diffDays < 7) return date.toLocaleDateString([], { weekday: 'short' })
    if (date.getFullYear() === now.getFullYear()) return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
    return date.toLocaleDateString([], { year: 'numeric', month: 'short', day: 'numeric' })
  } catch { return isoString.slice(0, 10) }
}
