import { useState, useEffect } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { MessageSquare, Users, Clock, ArrowLeft, RefreshCw, ChevronDown, ChevronRight, Paperclip } from 'lucide-react'
import { api } from '../api/client'

export function ThreadList() {
  const [threads, setThreads] = useState([])
  const [pagination, setPagination] = useState({ page: 1, total: 0, total_pages: 1 })
  const [sortBy, setSortBy] = useState('last_date')
  const [minMessages, setMinMessages] = useState(2)
  const [loading, setLoading] = useState(true)
  const [rebuilding, setRebuilding] = useState(false)
  const [rebuildStatus, setRebuildStatus] = useState(null)

  const loadThreads = async (page = 1) => {
    setLoading(true)
    try {
      const data = await api.getThreads({ page, sort_by: sortBy, min_messages: minMessages, page_size: 50 })
      setThreads(data.items)
      setPagination({ page: data.page, total: data.total, total_pages: data.total_pages })
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadThreads() }, [sortBy, minMessages])

  const handleRebuild = async () => {
    setRebuilding(true)
    setRebuildStatus('Starting thread reconstruction...')
    try {
      await api.rebuildThreads()
      // Poll status
      const poll = setInterval(async () => {
        try {
          const status = await api.getThreadStatus()
          setRebuildStatus(status.progress || 'Processing...')
          if (!status.running) {
            clearInterval(poll)
            setRebuilding(false)
            setRebuildStatus(status.result
              ? `Done! ${status.result.multi_message_threads} conversations found`
              : status.error || 'Complete')
            loadThreads()
          }
        } catch { clearInterval(poll); setRebuilding(false) }
      }, 2000)
    } catch (err) {
      setRebuilding(false)
      setRebuildStatus(`Error: ${err.message}`)
    }
  }

  const formatDuration = (seconds) => {
    if (!seconds) return '—'
    const days = Math.floor(seconds / 86400)
    if (days > 365) return `${Math.round(days / 365)}y`
    if (days > 30) return `${Math.round(days / 30)}mo`
    if (days > 0) return `${days}d`
    const hours = Math.floor(seconds / 3600)
    return hours > 0 ? `${hours}h` : '<1h'
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-blue-600" />
          Threads
          {pagination.total > 0 && <span className="text-sm font-normal text-gray-400">({pagination.total.toLocaleString()})</span>}
        </h2>
        <div className="flex items-center gap-3">
          <select value={minMessages} onChange={(e) => setMinMessages(Number(e.target.value))}
            className="text-xs border border-gray-200 rounded-lg px-2 py-1.5">
            <option value={2}>2+ messages</option>
            <option value={3}>3+ messages</option>
            <option value={5}>5+ messages</option>
            <option value={10}>10+ messages</option>
          </select>
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}
            className="text-xs border border-gray-200 rounded-lg px-2 py-1.5">
            <option value="last_date">Most Recent</option>
            <option value="message_count">Most Messages</option>
            <option value="participant_count">Most People</option>
            <option value="duration_seconds">Longest Running</option>
          </select>
          <button onClick={handleRebuild} disabled={rebuilding}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
            <RefreshCw className={`w-3.5 h-3.5 ${rebuilding ? 'animate-spin' : ''}`} />
            {rebuilding ? 'Rebuilding...' : 'Rebuild Threads'}
          </button>
        </div>
      </div>

      {rebuildStatus && (
        <div className={`text-sm px-3 py-2 rounded-lg ${rebuilding ? 'bg-blue-50 text-blue-700' : 'bg-green-50 text-green-700'}`}>
          {rebuildStatus}
        </div>
      )}

      {/* Thread list */}
      <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
        {loading ? (
          <div className="p-8 text-center text-gray-400">Loading threads...</div>
        ) : threads.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            No threads found. Click "Rebuild Threads" to reconstruct conversations from your emails.
          </div>
        ) : threads.map((t) => (
          <Link key={t.id} to={`/thread/${t.id}`}
            className="flex items-center gap-4 px-4 py-3 hover:bg-gray-50 transition-colors">
            <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center flex-shrink-0">
              <MessageSquare className="w-4 h-4 text-blue-600" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-gray-800 truncate">
                {t.original_subject || t.subject_normalized || '(no subject)'}
              </div>
              <div className="text-xs text-gray-400 flex items-center gap-3 mt-0.5">
                <span className="flex items-center gap-1">
                  <MessageSquare className="w-3 h-3" /> {t.message_count} messages
                </span>
                <span className="flex items-center gap-1">
                  <Users className="w-3 h-3" /> {t.participant_count} people
                </span>
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" /> {formatDuration(t.duration_seconds)}
                </span>
              </div>
            </div>
            <div className="text-xs text-gray-400 text-right flex-shrink-0">
              <div>{t.last_date ? new Date(t.last_date).toLocaleDateString() : '—'}</div>
              <div className="text-gray-300">{t.first_date ? new Date(t.first_date).toLocaleDateString() : ''}</div>
            </div>
            <ChevronRight className="w-4 h-4 text-gray-300" />
          </Link>
        ))}
      </div>

      {/* Pagination */}
      {pagination.total_pages > 1 && (
        <div className="flex items-center justify-between text-sm text-gray-500">
          <span>Page {pagination.page} of {pagination.total_pages}</span>
          <div className="flex gap-2">
            <button onClick={() => loadThreads(pagination.page - 1)} disabled={pagination.page <= 1}
              className="px-3 py-1 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50">Prev</button>
            <button onClick={() => loadThreads(pagination.page + 1)} disabled={pagination.page >= pagination.total_pages}
              className="px-3 py-1 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50">Next</button>
          </div>
        </div>
      )}
    </div>
  )
}

export function ThreadView() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [thread, setThread] = useState(null)
  const [loading, setLoading] = useState(true)
  const [expandedEmails, setExpandedEmails] = useState(new Set())

  useEffect(() => {
    setLoading(true)
    api.getThread(id).then(data => {
      setThread(data)
      // Auto-expand last 3 emails
      const ids = new Set(data.emails?.slice(-3).map(e => e.id) || [])
      setExpandedEmails(ids)
    }).catch(console.error).finally(() => setLoading(false))
  }, [id])

  const toggleEmail = (emailId) => {
    setExpandedEmails(prev => {
      const next = new Set(prev)
      if (next.has(emailId)) next.delete(emailId)
      else next.add(emailId)
      return next
    })
  }

  if (loading) return <div className="p-8 text-center text-gray-400">Loading thread...</div>
  if (!thread) return <div className="p-8 text-center text-gray-400">Thread not found</div>

  const participants = new Map()
  thread.emails?.forEach(e => {
    if (e.sender_email && !participants.has(e.sender_email)) {
      participants.set(e.sender_email, e.sender_name || e.sender_email)
    }
  })

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      {/* Header */}
      <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
        <ArrowLeft className="w-4 h-4" /> Back to threads
      </button>

      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="text-lg font-semibold text-gray-900">
          {thread.emails?.[0]?.subject || thread.subject_normalized || '(no subject)'}
        </h2>
        <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
          <span className="flex items-center gap-1"><MessageSquare className="w-3.5 h-3.5" /> {thread.message_count} messages</span>
          <span className="flex items-center gap-1"><Users className="w-3.5 h-3.5" /> {thread.participant_count} participants</span>
          <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" />
            {thread.first_date ? new Date(thread.first_date).toLocaleDateString() : '?'} — {thread.last_date ? new Date(thread.last_date).toLocaleDateString() : '?'}
          </span>
        </div>

        {/* Participants */}
        <div className="flex flex-wrap gap-1.5 mt-3">
          {Array.from(participants.entries()).map(([email, name]) => (
            <span key={email} className="px-2 py-0.5 bg-gray-100 rounded-full text-xs text-gray-600">
              {name}
            </span>
          ))}
        </div>
      </div>

      {/* Email timeline */}
      <div className="space-y-2">
        {thread.emails?.map((email, i) => {
          const expanded = expandedEmails.has(email.id)
          const initials = (email.sender_name || email.sender_email || '?').charAt(0).toUpperCase()
          const COLORS = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#6366f1']
          const colorIdx = Array.from(participants.keys()).indexOf(email.sender_email) % COLORS.length

          return (
            <div key={email.id} className="flex gap-3">
              {/* Timeline line */}
              <div className="flex flex-col items-center">
                <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium text-white flex-shrink-0"
                  style={{ backgroundColor: COLORS[colorIdx >= 0 ? colorIdx : 0] }}>
                  {initials}
                </div>
                {i < thread.emails.length - 1 && <div className="w-0.5 flex-1 bg-gray-200 mt-1" />}
              </div>

              {/* Email card */}
              <div className="flex-1 bg-white rounded-xl border border-gray-200 mb-1 overflow-hidden">
                <button onClick={() => toggleEmail(email.id)}
                  className="w-full flex items-center gap-2 px-4 py-2.5 hover:bg-gray-50 text-left">
                  <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${expanded ? '' : '-rotate-90'}`} />
                  <span className="text-sm font-medium text-gray-800">{email.sender_name || email.sender_email}</span>
                  {email.has_attachments && <Paperclip className="w-3 h-3 text-gray-400" />}
                  <span className="flex-1" />
                  <span className="text-xs text-gray-400">
                    {email.date_sent ? new Date(email.date_sent).toLocaleString() : ''}
                  </span>
                  <Link to={`/email/${email.id}`} onClick={(e) => e.stopPropagation()}
                    className="text-xs text-blue-500 hover:text-blue-600 ml-2">Open</Link>
                </button>

                {expanded && (
                  <div className="px-4 pb-3 border-t border-gray-100">
                    {/* Recipients */}
                    {email.recipients?.length > 0 && (
                      <div className="text-xs text-gray-400 mt-2 mb-2">
                        To: {email.recipients.map(r => r.name || r.email).join(', ')}
                      </div>
                    )}
                    {/* Body */}
                    <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed mt-1">
                      {email.body_text || '(no body)'}
                    </div>
                    {/* Attachments */}
                    {email.attachment_names?.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-3">
                        {email.attachment_names.map((name, j) => (
                          <span key={j} className="flex items-center gap-1 px-2 py-0.5 bg-gray-100 rounded text-xs text-gray-500">
                            <Paperclip className="w-3 h-3" /> {name}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
