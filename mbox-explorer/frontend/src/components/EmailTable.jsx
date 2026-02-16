import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Paperclip } from 'lucide-react'

export default function EmailTable({ emails, loading, pagination, onPageChange }) {
  if (loading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-12 text-center text-gray-500">
        Loading emails...
      </div>
    )
  }

  if (!emails.length) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-12 text-center text-gray-500">
        No emails found. Import some .mbox files to get started.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Results count */}
      <div className="text-sm text-gray-500">
        {pagination.total.toLocaleString()} email{pagination.total !== 1 ? 's' : ''}
      </div>

      {/* Email list */}
      <div className="bg-white rounded-lg border border-gray-200 divide-y divide-gray-100">
        {emails.map((email) => (
          <Link
            key={email.id}
            to={`/email/${email.id}`}
            className="block px-4 py-3 hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                {/* Sender */}
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm text-gray-900 truncate">
                    {email.sender_name || email.sender_email || 'Unknown'}
                  </span>
                  {email.sender_name && email.sender_email && (
                    <span className="text-xs text-gray-400 truncate hidden sm:inline">
                      &lt;{email.sender_email}&gt;
                    </span>
                  )}
                  {email.has_attachments && (
                    <Paperclip className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                  )}
                </div>

                {/* Subject */}
                <div className="text-sm text-gray-800 truncate mt-0.5">
                  {email.subject || '(no subject)'}
                </div>

                {/* Snippet */}
                {email.snippet && (
                  <div className="text-xs text-gray-400 truncate mt-0.5">
                    {email.snippet}
                  </div>
                )}
              </div>

              {/* Date */}
              <div className="text-xs text-gray-400 whitespace-nowrap flex-shrink-0">
                {formatDate(email.date_sent)}
              </div>
            </div>
          </Link>
        ))}
      </div>

      {/* Pagination */}
      {pagination.total_pages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-500">
            Page {pagination.page} of {pagination.total_pages}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => onPageChange(pagination.page - 1)}
              disabled={pagination.page <= 1}
              className="flex items-center gap-1 px-3 py-1.5 text-sm border rounded-md disabled:opacity-40 hover:bg-gray-50"
            >
              <ChevronLeft className="w-4 h-4" /> Prev
            </button>
            <button
              onClick={() => onPageChange(pagination.page + 1)}
              disabled={pagination.page >= pagination.total_pages}
              className="flex items-center gap-1 px-3 py-1.5 text-sm border rounded-md disabled:opacity-40 hover:bg-gray-50"
            >
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
  } catch {
    return isoString.slice(0, 10)
  }
}
