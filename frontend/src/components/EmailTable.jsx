import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Paperclip, MessageSquare } from 'lucide-react'

function highlightText(text, query) {
  if (!query || !text) return text
  const words = query.trim().split(/\s+/).filter(w => w.length > 2)
  if (words.length === 0) return text
  const escaped = words.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')
  const pattern = new RegExp(`(${escaped})`, 'gi')
  const parts = text.split(pattern)
  // Use a fresh non-global regex for matching to avoid lastIndex statefulness
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
    <div className="bg-white rounded-lg border border-gray-200 divide-y divide-gray-100">
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

export default function EmailTable({ emails, loading, pagination, onPageChange, searchQuery = '' }) {
  if (loading) return <LoadingSkeleton />
  if (!emails.length) return <div className="bg-white rounded-lg border border-gray-200 p-12 text-center text-gray-500">No emails found.</div>

  return (
    <div className="space-y-3">
      <div className="text-sm text-gray-500">{pagination.total.toLocaleString()} email{pagination.total !== 1 ? 's' : ''}</div>
      <div className="bg-white rounded-lg border border-gray-200 divide-y divide-gray-100">
        {emails.map((email) => (
          <Link key={email.id} to={`/email/${email.id}`} className="block px-4 py-3 hover:bg-gray-50 transition-colors">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-sm text-gray-900 truncate">
                    {highlightText(email.sender_name || email.sender_email || 'Unknown', searchQuery)}
                  </span>
                  {email.has_attachments && <Paperclip className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />}
                  {email.thread_group_id && (
                    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded text-[10px] font-medium flex-shrink-0">
                      <MessageSquare className="w-2.5 h-2.5" />thread
                    </span>
                  )}
                </div>
                <div className="text-sm text-gray-800 truncate mt-0.5">
                  {highlightText(email.subject || '(no subject)', searchQuery)}
                </div>
                {email.snippet && <div className="text-xs text-gray-400 truncate mt-0.5">{highlightText(email.snippet, searchQuery)}</div>}
              </div>
              <div className="text-xs text-gray-400 whitespace-nowrap flex-shrink-0">{formatDate(email.date_sent)}</div>
            </div>
          </Link>
        ))}
      </div>
      {pagination.total_pages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-500">Page {pagination.page} of {pagination.total_pages}</span>
          <div className="flex gap-2">
            <button onClick={() => onPageChange(pagination.page - 1)} disabled={pagination.page <= 1} className="flex items-center gap-1 px-3 py-1.5 text-sm border border-gray-200 rounded-md disabled:opacity-40 hover:bg-gray-50"><ChevronLeft className="w-4 h-4" /> Prev</button>
            <button onClick={() => onPageChange(pagination.page + 1)} disabled={pagination.page >= pagination.total_pages} className="flex items-center gap-1 px-3 py-1.5 text-sm border border-gray-200 rounded-md disabled:opacity-40 hover:bg-gray-50">Next <ChevronRight className="w-4 h-4" /></button>
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
