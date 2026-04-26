import { useState, useEffect } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { MessageSquare, Users, Clock, ArrowLeft, RefreshCw, ChevronDown, ChevronRight, Paperclip, Sparkles, CheckCircle, HelpCircle, AlertCircle } from 'lucide-react'
import { api } from '../api/client'

function formatDate(dateStr) {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    const now = new Date()
    const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24))
    if (diffDays === 0) return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    if (diffDays < 7) return date.toLocaleDateString([], { weekday: 'short' })
    if (date.getFullYear() === now.getFullYear()) return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
    return date.toLocaleDateString([], { year: 'numeric', month: 'short', day: 'numeric' })
  } catch { return dateStr.slice(0, 10) }
}

function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return '—'
  const d = Math.floor(seconds / 86400)
  if (d > 365) return `${Math.round(d / 365)}y`
  if (d > 30) return `${Math.round(d / 30)}mo`
  if (d > 0) return `${d}d`
  const h = Math.floor(seconds / 3600)
  return h > 0 ? `${h}h` : '<1h'
}

export function ThreadList() {
  const [threads, setThreads] = useState([])
  const [expandedThreads, setExpandedThreads] = useState(new Set())
  const [expandedThreadEmails, setExpandedThreadEmails] = useState({})
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

  useEffect(() => {
    loadThreads()
  }, [sortBy, minMessages])

  const handleRebuild = async () => {
    setRebuilding(true)
    setRebuildStatus('Starting thread reconstruction...')
    try {
      await api.rebuildThreads()
      const poll = setInterval(async () => {
        try {
          const s = await api.getThreadStatus()
          setRebuildStatus(s.progress || 'Processing...')
          if (!s.running) {
            clearInterval(poll)
            setRebuilding(false)
            setRebuildStatus(s.result ? `Done! ${s.result.multi_message_threads} conversations found` : s.error || 'Complete')
            loadThreads()
          }
        } catch {
          clearInterval(poll)
          setRebuilding(false)
        }
      }, 2000)
    } catch (err) {
      setRebuilding(false)
      setRebuildStatus(`Error: ${err.message}`)
    }
  }

  const toggleThread = async (threadId) => {
    const nextExpanded = new Set(expandedThreads)
    if (nextExpanded.has(threadId)) {
      nextExpanded.delete(threadId)
      // Clear emails when collapsing
      setExpandedThreadEmails(prev => {
        const next = { ...prev }
        delete next[threadId]
        return next
      })
    } else {
      nextExpanded.add(threadId)
      // Fetch emails when expanding
      try {
        const data = await api.getThread(threadId)
        setExpandedThreadEmails(prev => ({ ...prev, [threadId]: data.emails || [] }))
      } catch (err) {
        console.error('Failed to fetch thread emails:', err)
      }
    }
    setExpandedThreads(nextExpanded)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-blue-600" />
          Threads
          {pagination.total > 0 && <span className="text-sm font-normal text-gray-400">({pagination.total.toLocaleString()})</span>}
        </h2>
        <div className="flex items-center gap-3">
          <select
            value={minMessages}
            onChange={(e) => setMinMessages(Number(e.target.value))}
            className="text-xs border border-gray-200 rounded-lg px-2 py-1.5"
          >
            <option value={2}>2+ messages</option>
            <option value={3}>3+</option>
            <option value={5}>5+</option>
            <option value={10}>10+</option>
          </select>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="text-xs border border-gray-200 rounded-lg px-2 py-1.5"
          >
            <option value="last_date">Most Recent</option>
            <option value="message_count">Most Messages</option>
            <option value="participant_count">Most People</option>
            <option value="duration_seconds">Longest Running</option>
          </select>
          <button
            onClick={handleRebuild}
            disabled={rebuilding}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
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
      <div className="space-y-3">
        {loading ? (
          <div className="p-8 text-center text-gray-400">Loading threads...</div>
        ) : threads.length === 0 ? (
          <div className="p-12 text-center bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
            <MessageSquare className="w-10 h-10 text-gray-300 dark:text-gray-700 mx-auto mb-3" />
            <p className="text-sm font-medium text-gray-600 dark:text-gray-300">No conversations yet.</p>
            <p className="text-xs text-gray-400 mt-1">
              Click <span className="font-medium">Rebuild Threads</span> to reconstruct conversations from your archive.
            </p>
          </div>
        ) : (
          threads.map((t) => (
            <div key={t.id} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              {/* Thread header (always visible) */}
              <div
                onClick={() => toggleThread(t.id)}
                className="px-4 py-3 hover:bg-gray-50 cursor-pointer transition-colors flex items-start gap-4"
              >
                <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <MessageSquare className="w-4 h-4 text-blue-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-800 truncate flex-1">
                        {t.original_subject || t.subject_normalized || '(no subject)'}
                      </span>
                      <span className="flex items-center gap-1 px-1.5 py-0.5 bg-blue-50 dark:bg-blue-900/40 text-blue-600 dark:text-blue-300 rounded text-[10px] font-medium flex-shrink-0">
                        <MessageSquare className="w-2.5 h-2.5" />{t.message_count} msgs
                      </span>
                    </div>
                    <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${expandedThreads.has(t.id) ? '' : '-rotate-90'}`} />
                  </div>
                  <div className="text-xs text-gray-500 flex items-center gap-4 flex-wrap">
                    <span className="flex items-center gap-1">
                      <Users className="w-3 h-3" />
                      {t.participant_count} participant{t.participant_count !== 1 ? 's' : ''}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatDuration(t.duration_seconds)}
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                      {t.first_date ? formatDate(t.first_date) : '?'} — {t.last_date ? formatDate(t.last_date) : '?'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Expanded thread content (email tree) */}
              {expandedThreads.has(t.id) && (
                <div className="px-4 pb-4 pt-0 border-t border-gray-100 bg-gray-50/50">
                  <ThreadEmailTree emails={expandedThreadEmails[t.id] || []} messageCount={t.message_count} />
                </div>
              )}
            </div>
          ))
        )}
      </div>
      {pagination.total_pages > 1 && (
        <div className="flex items-center justify-between text-sm text-gray-500">
          <span>Page {pagination.page} of {pagination.total_pages}</span>
          <div className="flex gap-2">
            <button
              onClick={() => loadThreads(pagination.page - 1)}
              disabled={pagination.page <= 1}
              className="px-3 py-1 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50"
            >
              Prev
            </button>
            <button
              onClick={() => loadThreads(pagination.page + 1)}
              disabled={pagination.page >= pagination.total_pages}
              className="px-3 py-1 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function ThreadEmailTree({ emails, messageCount }) {
  const CL = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#6366f1']

  return (
    <div className="py-3">
      <div className="flex items-center gap-2 mb-3 px-1">
        <span className="text-xs font-medium text-gray-500 flex items-center gap-1.5">
          <MessageSquare className="w-3 h-3" />
          Conversation ({messageCount} messages)
        </span>
      </div>
      <div className="space-y-2">
        {emails.map((email, i) => {
          const senderEmail = email.sender_email || 'unknown@example.com'
          const senderName = email.sender_name || senderEmail.split('@')[0]
          const colorIndex = Array.from(new Set(emails.map(e => e.sender_email || ''))).indexOf(senderEmail)
          const color = CL[colorIndex >= 0 ? colorIndex % CL.length : 0]
          const init = senderName.charAt(0).toUpperCase() || '?'
          return (
            <div key={email.id} className="flex gap-3 animate-in fade-in duration-200">
              {/* Thread tree connector */}
              <div className="flex flex-col items-center">
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium text-white flex-shrink-0 shadow-sm"
                  style={{ backgroundColor: color }}
                >
                  {init}
                </div>
                {i < emails.length - 1 && <div className="w-0.5 flex-1 bg-gray-200 mt-1" />}
              </div>

              {/* Email card */}
              <div className="flex-1 bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
                <div className="px-4 py-2.5 hover:bg-gray-50">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-gray-800">{email.sender_name || email.sender_email}</span>
                      {email.has_attachments && <Paperclip className="w-3 h-3 text-gray-400" />}
                    </div>
                    <span className="text-xs text-gray-500">{formatDate(email.date_sent)}</span>
                  </div>
                  <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed line-clamp-2">
                    {email.body_text || '(no body)'}
                  </div>
                  {email.recipients?.length > 0 && (
                    <div className="text-xs text-gray-400 mt-2">
                      To: {email.recipients.map(r => r.name || r.email).join(', ')}
                    </div>
                  )}
                </div>
                <div className="px-4 py-2 bg-gray-50 border-t border-gray-100 flex items-center gap-2">
                  <Link
                    to={`/email/${email.id}`}
                    className="text-xs font-medium text-blue-600 hover:text-blue-700"
                  >
                    View full email
                  </Link>
                  {email.attachment_names?.length > 0 && (
                    <span className="text-xs text-gray-400 flex items-center gap-1">
                      <Paperclip className="w-2.5 h-2.5" />
                      {email.attachment_names.length} attachment{email.attachment_names.length !== 1 ? 's' : ''}
                    </span>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function ThreadView() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [thread, setThread] = useState(null)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(new Set())
  const [summary, setSummary] = useState(null)
  const [summarizing, setSummarizing] = useState(false)

  useEffect(() => {
    setLoading(true)
    setSummary(null)
    api.getThread(id).then((d) => {
      setThread(d)
      // Auto-expand last 3 emails by default
      setExpanded(new Set(d.emails?.slice(-3).map((e) => e.id) || []))
      // Auto-summarize threads with 5+ messages
      if (d.message_count >= 5 && !summary) {
        setSummarizing(true)
        api.summarizeThread(id).then(setSummary).catch(() => {}).finally(() => setSummarizing(false))
      }
    }).catch(console.error).finally(() => setLoading(false))
  }, [id, summary])

  const toggle = (eid) => {
    setExpanded((p) => {
      const n = new Set(p)
      if (n.has(eid)) n.delete(eid)
      else n.add(eid)
      return n
    })
  }

  const handleSummarize = async () => {
    setSummarizing(true)
    try {
      const data = await api.summarizeThread(id)
      setSummary(data)
    } catch (err) {
      setSummary({ error: err.message })
    } finally {
      setSummarizing(false)
    }
  }

  if (loading) return <div className="p-8 text-center text-gray-400">Loading thread...</div>
  if (!thread) return <div className="p-8 text-center text-gray-400">Thread not found</div>

  const parts = new Map()
  thread.emails?.forEach((e) => {
    if (e.sender_email && !parts.has(e.sender_email)) parts.set(e.sender_email, e.sender_name || e.sender_email)
  })
  const CL = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#6366f1']

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
          <ArrowLeft className="w-4 h-4" /> Back to threads
        </button>
        <button
          onClick={handleSummarize}
          disabled={summarizing}
          className="flex items-center gap-1.5 px-4 py-2 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 shadow-sm"
        >
          <Sparkles className="w-4 h-4" /> {summarizing ? 'Summarizing...' : 'Summarize Thread'}
        </button>
      </div>

      {/* AI Summary Card */}
      {summary && !summary.error && (
        <div className="bg-gradient-to-br from-purple-50 to-indigo-50 rounded-xl border border-purple-200 p-5 space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-purple-800">
            <Sparkles className="w-4 h-4" /> AI Summary
            {summary.sentiment && <span className="ml-auto px-2 py-0.5 bg-white/60 rounded-full text-xs font-medium text-purple-600">{summary.sentiment}</span>}
          </div>
          <p className="text-sm text-gray-800 leading-relaxed">{summary.summary}</p>

          {summary.key_decisions?.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-purple-700 mb-1.5 flex items-center gap-1"><CheckCircle className="w-3.5 h-3.5" />Key Decisions</div>
              <ul className="space-y-1">{summary.key_decisions.map((d, i) => <li key={i} className="text-sm text-gray-700 flex items-start gap-2"><span className="text-purple-400 mt-1">•</span>{d}</li>)}</ul>
            </div>
          )}

          {summary.action_items?.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-purple-700 mb-1.5 flex items-center gap-1"><AlertCircle className="w-3.5 h-3.5" />Action Items</div>
              <ul className="space-y-1.5">{summary.action_items.map((a, i) => (
                <li key={i} className="text-sm flex items-start gap-2">
                  <span className={`mt-0.5 w-2 h-2 rounded-full flex-shrink-0 ${a.status === 'done' ? 'bg-green-400' : a.status === 'open' ? 'bg-amber-400' : 'bg-gray-300'}`} />
                  <span className="text-gray-700">{typeof a === 'string' ? a : a.task}</span>
                  {a.owner && <span className="text-xs text-purple-500 flex-shrink-0">→ {a.owner}</span>}
                </li>))}
              </ul>
            </div>
          )}

          {summary.open_questions?.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-purple-700 mb-1.5 flex items-center gap-1"><HelpCircle className="w-3.5 h-3.5" />Open Questions</div>
              <ul className="space-y-1">{summary.open_questions.map((q, i) => <li key={i} className="text-sm text-gray-700 flex items-start gap-2"><span className="text-purple-400 mt-1">?</span>{q}</li>)}</ul>
            </div>
          )}

          {summary.topic_tags?.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-2 border-t border-purple-200/50">
              {summary.topic_tags.map((t, i) => <span key={i} className="px-2 py-0.5 bg-white/60 rounded-full text-xs text-purple-600">{t}</span>)}
            </div>
          )}

          <div className="text-[10px] text-purple-400 pt-1">Generated by {summary.model} • {summary.message_count} messages analyzed</div>
        </div>
      )}
      {summary?.error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">{summary.error}</div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="text-lg font-semibold text-gray-900">{thread.emails?.[0]?.subject || thread.subject_normalized || '(no subject)'}</h2>
        <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
          <span className="flex items-center gap-1"><MessageSquare className="w-3.5 h-3.5" />{thread.message_count} messages</span>
          <span className="flex items-center gap-1"><Users className="w-3.5 h-3.5" />{thread.participant_count} participants</span>
          <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" />{thread.first_date ? formatDate(thread.first_date) : '?'} — {thread.last_date ? formatDate(thread.last_date) : '?'}</span>
        </div>
        <div className="flex flex-wrap gap-1.5 mt-3">
          {Array.from(parts.entries()).map(([email, name]) => <span key={email} className="px-2 py-0.5 bg-gray-100 rounded-full text-xs text-gray-600">{name}</span>)}
        </div>
      </div>

      <div className="space-y-2">
        {thread.emails?.map((email, i) => {
          const exp = expanded.has(email.id)
          const init = (email.sender_name || email.sender_email || '?').charAt(0).toUpperCase()
          const ci = Array.from(parts.keys()).indexOf(email.sender_email) % CL.length
          return (
            <div key={email.id} className="flex gap-3">
              <div className="flex flex-col items-center">
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium text-white flex-shrink-0"
                  style={{ backgroundColor: CL[ci >= 0 ? ci : 0] }}
                >
                  {init}
                </div>
                {i < thread.emails.length - 1 && <div className="w-0.5 flex-1 bg-gray-200 mt-1" />}
              </div>
              <div className="flex-1 bg-white rounded-xl border border-gray-200 mb-1 overflow-hidden">
                <button
                  onClick={() => toggle(email.id)}
                  className="w-full flex items-center gap-2 px-4 py-2.5 hover:bg-gray-50 text-left"
                >
                  <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${exp ? '' : '-rotate-90'}`} />
                  <span className="text-sm font-medium text-gray-800">{email.sender_name || email.sender_email}</span>
                  {email.has_attachments && <Paperclip className="w-3 h-3 text-gray-400" />}
                  <span className="flex-1" />
                  <span className="text-xs text-gray-400">{email.date_sent ? formatDate(email.date_sent) : ''}</span>
                  <Link to={`/email/${email.id}`} onClick={(e) => e.stopPropagation()} className="text-xs text-blue-500 hover:text-blue-600 ml-2">Open</Link>
                </button>
                {exp && (
                  <div className="px-4 pb-3 border-t border-gray-100">
                    {email.recipients?.length > 0 && <div className="text-xs text-gray-400 mt-2 mb-2">To: {email.recipients.map((r) => r.name || r.email).join(', ')}</div>}
                    <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed mt-1">{email.body_text || '(no body)'}</div>
                    {email.attachment_names?.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-3">
                        {email.attachment_names.map((n, j) => <span key={j} className="flex items-center gap-1 px-2 py-0.5 bg-gray-100 rounded text-xs text-gray-500"><Paperclip className="w-3 h-3" />{n}</span>)}
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
