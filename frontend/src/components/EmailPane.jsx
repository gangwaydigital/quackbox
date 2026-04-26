/**
 * EmailPane — the email reading pane.
 *
 * Accepts emailId as a prop (for split-pane use) or reads it from
 * useParams (for the standalone /email/:id route via EmailDetail).
 *
 * Props:
 *   emailId    — string | number, the email to display
 *   onClose    — optional callback (shows ✕ button when provided)
 *   compact    — boolean, reduces padding for pane mode
 */
import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Paperclip, Tag, Sparkles, MessageSquare,
  FileText, CheckCircle, User, Quote, Download, X, ExternalLink,
  Mail
} from 'lucide-react'
import { api } from '../api/client'

function LoadingSkeleton({ compact }) {
  return (
    <div className={`space-y-4 ${compact ? 'p-3' : 'p-4'}`}>
      <div className="skeleton h-5 w-24 rounded" />
      <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-4 space-y-3">
        <div className="skeleton h-6 w-3/4 rounded" />
        <div className="skeleton h-4 w-1/2 rounded" />
        <div className="skeleton h-4 w-1/3 rounded" />
      </div>
      <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-4 space-y-2">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="skeleton h-4 rounded" style={{ width: `${70 + Math.random() * 30}%` }} />
        ))}
      </div>
    </div>
  )
}

export default function EmailPane({ emailId, onClose, compact = false }) {
  const navigate = useNavigate()
  const id = String(emailId)

  const [email, setEmail]           = useState(null)
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState(null)
  const [showHtml, setShowHtml]     = useState(false)
  const [cleanQuotes, setCleanQuotes] = useState(false)
  const [cleanedBody, setCleanedBody] = useState(null)
  const [similar, setSimilar]       = useState(null)
  const [loadingSimilar, setLoadingSimilar] = useState(false)
  const [summary, setSummary]       = useState(null)
  const [summarizing, setSummarizing] = useState(false)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    setError(null)
    setSimilar(null)
    setSummary(null)
    setCleanedBody(null)
    setCleanQuotes(false)
    setShowHtml(false)

    api.getEmail(id)
      .then(data => {
        if (typeof data.recipients === 'string') {
          try { data.recipients = JSON.parse(data.recipients) } catch { data.recipients = [] }
        }
        if (typeof data.attachment_names === 'string') {
          try { data.attachment_names = JSON.parse(data.attachment_names) } catch { data.attachment_names = [] }
        }
        if (!Array.isArray(data.recipients)) data.recipients = []
        if (!Array.isArray(data.attachment_names)) data.attachment_names = []
        if (!Array.isArray(data.topics)) data.topics = []
        setEmail(data)
      })
      .catch(err => setError(String(err.message || err)))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => {
    if (cleanQuotes && !cleanedBody) {
      api.getEmailClean(id).then(d => setCleanedBody(d.body_text)).catch(console.error)
    }
  }, [cleanQuotes, id])

  const handleFindSimilar = async () => {
    setLoadingSimilar(true)
    try { setSimilar((await api.findSimilar(id, 8)).results || []) }
    catch { setSimilar([]) }
    finally { setLoadingSimilar(false) }
  }

  const handleSummarize = async () => {
    setSummarizing(true)
    try { setSummary(await api.summarizeEmail(id)) }
    catch (err) { setSummary({ error: err.message }) }
    finally { setSummarizing(false) }
  }

  const pad = compact ? 'p-3 sm:p-4' : 'p-4 sm:p-6'

  // ── Loading ──────────────────────────────────────────────────────────────
  if (loading) return <LoadingSkeleton compact={compact} />

  // ── Error ────────────────────────────────────────────────────────────────
  if (error || !email) return (
    <div className="flex flex-col items-center justify-center h-64 text-center gap-3 px-6">
      <Mail className="w-10 h-10 text-gray-300 dark:text-gray-700" />
      <p className="text-sm font-medium text-gray-600 dark:text-gray-300">
        {error ? 'Couldn’t load this email.' : 'Email not found.'}
      </p>
      {error && <p className="text-xs text-gray-400 max-w-sm">{error}</p>}
      {onClose && (
        <button onClick={onClose} className="text-xs text-blue-500 hover:underline">Close</button>
      )}
    </div>
  )

  const bodyText      = cleanQuotes && cleanedBody ? cleanedBody : email.body_text
  const toRecipients  = (email.recipients || []).filter(r => r?.type === 'to')
  const ccRecipients  = (email.recipients || []).filter(r => r?.type === 'cc')
  const attachments   = email.attachment_names || []
  const topics        = email.topics || []

  return (
    <div className="space-y-3">
      {/* ── Toolbar ─────────────────────────────────────────────────────── */}
      <div className={`flex items-center justify-between gap-2 flex-wrap ${pad}`}>
        <div className="flex items-center gap-2 flex-wrap">
          {/* Back link only when used standalone (no onClose) */}
          {!onClose && (
            <button onClick={() => navigate(-1)}
              className="inline-flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300">
              <ArrowLeft className="w-4 h-4" /> Back
            </button>
          )}
          {/* Open full page when in pane mode */}
          {onClose && (
            <Link to={`/email/${id}`}
              className="inline-flex items-center gap-1 text-xs text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
              title="Open full page">
              <ExternalLink className="w-3.5 h-3.5" />
            </Link>
          )}
        </div>

        <div className="flex items-center gap-1.5 flex-wrap">
          {email.sender_email && (
            <Link to={`/contact/${encodeURIComponent(email.sender_email)}`}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs bg-green-50 dark:bg-green-900/40 text-green-700 dark:text-green-300 rounded-lg hover:bg-green-100 dark:hover:bg-green-900/60">
              <User className="w-3 h-3" /> Profile
            </Link>
          )}
          {email.thread_group_id && (
            <Link to={`/thread/${email.thread_group_id}`}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs bg-blue-50 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/60">
              <MessageSquare className="w-3 h-3" /> Thread
            </Link>
          )}
          <button onClick={handleSummarize} disabled={summarizing}
            className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs bg-amber-50 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 rounded-lg hover:bg-amber-100 dark:hover:bg-amber-900/60 disabled:opacity-50">
            <FileText className="w-3 h-3" /> {summarizing ? 'Summarizing…' : 'Summarize'}
          </button>
          <button onClick={handleFindSimilar} disabled={loadingSimilar}
            className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs bg-purple-50 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 rounded-lg hover:bg-purple-100 dark:hover:bg-purple-900/60 disabled:opacity-50">
            <Sparkles className="w-3 h-3" /> {loadingSimilar ? 'Searching…' : 'Similar'}
          </button>
          <a href={api.downloadEmlUrl(id)} download
            className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700">
            <Download className="w-3 h-3" /> .eml
          </a>
          {onClose && (
            <button onClick={onClose} aria-label="Close email"
              className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors ml-1">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* ── AI Summary ──────────────────────────────────────────────────── */}
      {summary && !summary.error && (
        <div className={`mx-3 bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-900/30 dark:to-orange-900/30 rounded-xl border border-amber-200 dark:border-amber-700/50 ${pad} space-y-2`}>
          <div className="text-xs font-semibold text-amber-700 dark:text-amber-300 flex items-center gap-1">
            <FileText className="w-3.5 h-3.5" /> AI Summary
          </div>
          <p className="text-sm text-gray-800 dark:text-gray-200">{summary.summary}</p>
          {summary.action_items?.length > 0 && (
            <div className="space-y-1">
              {summary.action_items.map((a, i) => (
                <div key={i} className="text-sm text-gray-700 dark:text-gray-300 flex items-start gap-1.5">
                  <CheckCircle className="w-3.5 h-3.5 text-amber-500 mt-0.5 flex-shrink-0" />{a}
                </div>
              ))}
            </div>
          )}
          {summary.key_points?.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {summary.key_points.map((p, i) => (
                <span key={i} className="px-2 py-0.5 bg-white/60 dark:bg-amber-900/30 rounded text-xs text-amber-700 dark:text-amber-200">{p}</span>
              ))}
            </div>
          )}
          <div className="text-[10px] text-amber-400">Generated by {summary.model}</div>
        </div>
      )}
      {summary?.error && (
        <div className="mx-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700/50 rounded-xl p-3 text-sm text-red-700 dark:text-red-300">
          {summary.error}
        </div>
      )}

      {/* ── Email header ────────────────────────────────────────────────── */}
      <div className={`mx-3 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 ${pad} space-y-3`}>
        <h2 className="text-base sm:text-lg font-semibold text-gray-900 dark:text-white leading-snug">
          {email.subject || '(no subject)'}
        </h2>
        <div className="space-y-1 text-sm">
          <div className="flex gap-2">
            <span className="text-gray-400 w-12 flex-shrink-0 text-xs pt-0.5">From</span>
            <span className="text-gray-900 dark:text-gray-100 truncate min-w-0">
              {email.sender_name && <strong>{email.sender_name} </strong>}
              {email.sender_email && <span className="text-gray-400 text-xs">&lt;{email.sender_email}&gt;</span>}
            </span>
          </div>
          {toRecipients.length > 0 && (
            <div className="flex gap-2">
              <span className="text-gray-400 w-12 flex-shrink-0 text-xs pt-0.5">To</span>
              <span className="text-gray-600 dark:text-gray-400 truncate text-xs">{toRecipients.map(r => r.name || r.email).join(', ')}</span>
            </div>
          )}
          {ccRecipients.length > 0 && (
            <div className="flex gap-2">
              <span className="text-gray-400 w-12 flex-shrink-0 text-xs pt-0.5">Cc</span>
              <span className="text-gray-600 dark:text-gray-400 truncate text-xs">{ccRecipients.map(r => r.name || r.email).join(', ')}</span>
            </div>
          )}
          <div className="flex gap-2">
            <span className="text-gray-400 w-12 flex-shrink-0 text-xs pt-0.5">Date</span>
            <span className="text-gray-600 dark:text-gray-400 text-xs">
              {email.date_sent ? new Date(email.date_sent).toLocaleString() : 'Unknown'}
            </span>
          </div>
          {email.thread_group_id && (
            <div className="flex gap-2">
              <span className="text-gray-400 w-12 flex-shrink-0 text-xs pt-0.5">Thread</span>
              <Link to={`/thread/${email.thread_group_id}`} className="text-blue-600 dark:text-blue-400 text-xs hover:underline flex items-center gap-1">
                <MessageSquare className="w-3 h-3" /> View conversation
              </Link>
            </div>
          )}
          <div className="flex gap-2">
            <span className="text-gray-400 w-12 flex-shrink-0 text-xs pt-0.5">Source</span>
            <span className="text-gray-400 text-xs font-mono">{email.mbox_source}</span>
          </div>
        </div>

        {/* Attachments */}
        {attachments.length > 0 && (
          <div className="pt-2 border-t border-gray-100 dark:border-gray-800">
            <div className="text-xs text-gray-400 mb-1.5 flex items-center gap-1">
              <Paperclip className="w-3 h-3" /> {attachments.length} attachment{attachments.length !== 1 ? 's' : ''}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {attachments.map((name, i) => (
                <a key={i} href={api.downloadAttachmentUrl(id, name)} download
                  className="inline-flex items-center gap-1 px-2 py-1 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-xs text-gray-700 dark:text-gray-300 hover:bg-blue-50 dark:hover:bg-blue-900/30 hover:border-blue-200 dark:hover:border-blue-700 hover:text-blue-700 dark:hover:text-blue-300 transition-colors group"
                  title={`Download ${name}`}>
                  <Paperclip className="w-2.5 h-2.5 text-gray-400 group-hover:text-blue-500" />
                  <span className="truncate max-w-[160px]">{name}</span>
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Topics */}
        {topics.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-2 border-t border-gray-100 dark:border-gray-800">
            {topics.map(topic => (
              <Link key={topic.id} to="/topics"
                className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 rounded text-xs hover:bg-blue-100 dark:hover:bg-blue-900/60">
                <Tag className="w-2.5 h-2.5" /> {topic.label}
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* ── Body ────────────────────────────────────────────────────────── */}
      <div className={`mx-3 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 ${pad}`}>
        <div className="flex flex-wrap gap-1.5 mb-3">
          {email.body_html && (
            <>
              <button onClick={() => setShowHtml(false)}
                className={`text-xs px-2.5 py-1 rounded-full transition-colors ${!showHtml ? 'bg-gray-900 dark:bg-white text-white dark:text-gray-900' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'}`}>
                Plain
              </button>
              <button onClick={() => setShowHtml(true)}
                className={`text-xs px-2.5 py-1 rounded-full transition-colors ${showHtml ? 'bg-gray-900 dark:bg-white text-white dark:text-gray-900' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'}`}>
                HTML
              </button>
            </>
          )}
          {!showHtml && (
            <button onClick={() => setCleanQuotes(!cleanQuotes)}
              className={`text-xs px-2.5 py-1 rounded-full flex items-center gap-1 transition-colors ${cleanQuotes ? 'bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'}`}>
              <Quote className="w-2.5 h-2.5" />
              {cleanQuotes ? 'Showing clean' : 'Strip quotes'}
            </button>
          )}
        </div>

        {showHtml && email.body_html ? (
          <div className="prose prose-sm dark:prose-invert max-w-none overflow-x-auto text-gray-800 dark:text-gray-200"
            dangerouslySetInnerHTML={{ __html: email.body_html }} />
        ) : (
          <pre className="whitespace-pre-wrap text-sm text-gray-800 dark:text-gray-200 font-sans leading-relaxed overflow-x-auto">
            {bodyText || '(no body)'}
          </pre>
        )}
      </div>

      {/* ── Similar emails ──────────────────────────────────────────────── */}
      {similar && (
        <div className={`mx-3 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 ${pad}`}>
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-purple-500" />
            Similar Emails
            <span className="text-xs font-normal text-gray-400">({similar.length})</span>
          </h3>
          {similar.length === 0 ? (
            <p className="text-sm text-gray-400">No similar emails found. Generate embeddings via Topics first.</p>
          ) : (
            <div className="divide-y divide-gray-100 dark:divide-gray-800">
              {similar.map(s => (
                <Link key={s.id} to={`/email/${s.id}`}
                  className="block py-2 hover:bg-gray-50 dark:hover:bg-gray-800/50 rounded px-1 -mx-1">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">{s.subject || '(no subject)'}</div>
                      <div className="text-xs text-gray-400">{s.sender_name || s.sender_email}</div>
                    </div>
                    <div className="px-1.5 py-0.5 bg-purple-50 dark:bg-purple-900/40 rounded text-xs text-purple-600 dark:text-purple-300 flex-shrink-0">
                      {Math.round((s.similarity || 0) * 100)}%
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="h-4" /> {/* bottom breathing room */}
    </div>
  )
}
