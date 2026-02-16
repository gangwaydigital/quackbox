import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Paperclip, Tag, Sparkles, MessageSquare, FileText, CheckCircle, User, Quote } from 'lucide-react'
import { api } from '../api/client'

export default function EmailDetail() {
  const { id } = useParams()
  const [email, setEmail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showHtml, setShowHtml] = useState(false)
  const [cleanQuotes, setCleanQuotes] = useState(false)
  const [cleanedBody, setCleanedBody] = useState(null)
  const [similar, setSimilar] = useState(null)
  const [loadingSimilar, setLoadingSimilar] = useState(false)
  const [summary, setSummary] = useState(null)
  const [summarizing, setSummarizing] = useState(false)

  useEffect(() => {
    setLoading(true); setSimilar(null); setSummary(null); setCleanedBody(null); setCleanQuotes(false)
    api.getEmail(id).then(setEmail).catch(console.error).finally(() => setLoading(false))
  }, [id])

  useEffect(() => {
    if (cleanQuotes && !cleanedBody) {
      api.getEmail(id + '?clean=true').then(d => setCleanedBody(d.body_text)).catch(console.error)
    }
  }, [cleanQuotes, id])

  const handleFindSimilar = async () => {
    setLoadingSimilar(true)
    try { setSimilar((await api.findSimilar(id, 8)).results || []) }
    catch (err) { console.error(err); setSimilar([]) }
    finally { setLoadingSimilar(false) }
  }

  const handleSummarize = async () => {
    setSummarizing(true)
    try { setSummary(await api.summarizeEmail(id)) }
    catch (err) { setSummary({ error: err.message }) }
    finally { setSummarizing(false) }
  }

  if (loading) return (
    <div className="max-w-4xl mx-auto space-y-4">
      <div className="skeleton h-6 w-32" />
      <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-3">
        <div className="skeleton h-6 w-3/4" />
        <div className="skeleton h-4 w-1/2" />
        <div className="skeleton h-4 w-1/3" />
      </div>
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="skeleton h-4 w-full mb-2" />
        <div className="skeleton h-4 w-5/6 mb-2" />
        <div className="skeleton h-4 w-4/6" />
      </div>
    </div>
  )
  if (!email) return <div className="text-center py-12 text-gray-500">Email not found.</div>

  const bodyText = cleanQuotes && cleanedBody ? cleanedBody : email.body_text

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
        <Link to="/emails" className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700">
          <ArrowLeft className="w-4 h-4" /> Back to inbox
        </Link>
        <div className="flex flex-wrap gap-2">
          {email.sender_email && (
            <Link to={`/contact/${encodeURIComponent(email.sender_email)}`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs bg-green-50 text-green-700 rounded-lg hover:bg-green-100">
              <User className="w-3.5 h-3.5" /> Profile
            </Link>
          )}
          {email.thread_group_id && (
            <Link to={`/thread/${email.thread_group_id}`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100">
              <MessageSquare className="w-3.5 h-3.5" /> Thread
            </Link>
          )}
          <button onClick={handleSummarize} disabled={summarizing}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs bg-amber-50 text-amber-700 rounded-lg hover:bg-amber-100 disabled:opacity-50">
            <FileText className="w-3.5 h-3.5" /> {summarizing ? 'Summarizing...' : 'Summarize'}
          </button>
          <button onClick={handleFindSimilar} disabled={loadingSimilar}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs bg-purple-50 text-purple-700 rounded-lg hover:bg-purple-100 disabled:opacity-50">
            <Sparkles className="w-3.5 h-3.5" /> {loadingSimilar ? 'Searching...' : 'Similar'}
          </button>
        </div>
      </div>

      {/* AI Summary */}
      {summary && !summary.error && (
        <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-xl border border-amber-200 p-4 space-y-2">
          <div className="text-xs font-semibold text-amber-700 flex items-center gap-1"><FileText className="w-3.5 h-3.5" />AI Summary</div>
          <p className="text-sm text-gray-800">{summary.summary}</p>
          {summary.action_items?.length > 0 && (
            <div className="space-y-1">{summary.action_items.map((a, i) => (
              <div key={i} className="text-sm text-gray-700 flex items-start gap-1.5"><CheckCircle className="w-3.5 h-3.5 text-amber-500 mt-0.5 flex-shrink-0" />{a}</div>
            ))}</div>
          )}
          {summary.key_points?.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-1">{summary.key_points.map((p, i) => (
              <span key={i} className="px-2 py-0.5 bg-white/60 rounded text-xs text-amber-700">{p}</span>
            ))}</div>
          )}
          <div className="text-[10px] text-amber-400">Generated by {summary.model}</div>
        </div>
      )}
      {summary?.error && <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">{summary.error}</div>}

      {/* Email header */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 sm:p-6 space-y-3">
        <h2 className="text-lg sm:text-xl font-semibold text-gray-900">{email.subject || '(no subject)'}</h2>
        <div className="space-y-1.5 text-sm">
          <div className="flex gap-2"><span className="text-gray-500 w-16 flex-shrink-0">From:</span>
            <span className="text-gray-900 truncate">{email.sender_name && <strong>{email.sender_name}</strong>}
            {email.sender_email && <span className="text-gray-500"> &lt;{email.sender_email}&gt;</span>}</span></div>
          {email.recipients?.filter(r => r.type === 'to').length > 0 && (
            <div className="flex gap-2"><span className="text-gray-500 w-16 flex-shrink-0">To:</span>
              <span className="text-gray-700 truncate">{email.recipients.filter(r => r.type === 'to').map(r => r.name || r.email).join(', ')}</span></div>
          )}
          {email.recipients?.filter(r => r.type === 'cc').length > 0 && (
            <div className="flex gap-2"><span className="text-gray-500 w-16 flex-shrink-0">Cc:</span>
              <span className="text-gray-700 truncate">{email.recipients.filter(r => r.type === 'cc').map(r => r.name || r.email).join(', ')}</span></div>
          )}
          <div className="flex gap-2"><span className="text-gray-500 w-16 flex-shrink-0">Date:</span>
            <span className="text-gray-700">{email.date_sent ? new Date(email.date_sent).toLocaleString() : 'Unknown'}</span></div>
          <div className="flex gap-2"><span className="text-gray-500 w-16 flex-shrink-0">Source:</span>
            <span className="text-gray-400 text-xs">{email.mbox_source}</span></div>
        </div>
        {email.attachment_names?.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-100">
            {email.attachment_names.map((name, i) => (
              <span key={i} className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 rounded text-xs text-gray-600"><Paperclip className="w-3 h-3" /> {name}</span>
            ))}
          </div>
        )}
        {email.topics?.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-100">
            {email.topics.map(topic => (
              <Link key={topic.id} to="/topics" className="inline-flex items-center gap-1 px-2 py-1 bg-blue-50 text-blue-700 rounded text-xs hover:bg-blue-100">
                <Tag className="w-3 h-3" /> {topic.label}
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Email body */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 sm:p-6">
        <div className="flex flex-wrap gap-2 mb-4">
          {email.body_html && <>
            <button onClick={() => setShowHtml(false)} className={`text-xs px-3 py-1 rounded-full ${!showHtml ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600'}`}>Plain Text</button>
            <button onClick={() => setShowHtml(true)} className={`text-xs px-3 py-1 rounded-full ${showHtml ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600'}`}>HTML</button>
          </>}
          {!showHtml && (
            <button onClick={() => setCleanQuotes(!cleanQuotes)}
              className={`text-xs px-3 py-1 rounded-full flex items-center gap-1 ${cleanQuotes ? 'bg-indigo-100 text-indigo-700' : 'bg-gray-100 text-gray-600'}`}>
              <AlignLeft className="w-3 h-3" />{cleanQuotes ? 'Showing clean' : 'Strip quotes'}
            </button>
          )}
        </div>
        {showHtml && email.body_html ? (
          <div className="prose prose-sm max-w-none overflow-x-auto" dangerouslySetInnerHTML={{ __html: email.body_html }} />
        ) : (
          <pre className="whitespace-pre-wrap text-sm text-gray-800 font-sans leading-relaxed overflow-x-auto">{bodyText || '(no body)'}</pre>
        )}
      </div>

      {/* Similar emails */}
      {similar && (
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-purple-500" /> Similar Emails <span className="text-xs font-normal text-gray-400">({similar.length})</span>
          </h3>
          {similar.length === 0 ? <div className="text-sm text-gray-400">No similar emails found. Generate embeddings first via Topics.</div>
          : <div className="divide-y divide-gray-100">{similar.map(s => (
            <Link key={s.id} to={`/email/${s.id}`} className="block py-2.5 hover:bg-gray-50 rounded px-2 -mx-2">
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-800 truncate">{s.subject || '(no subject)'}</div>
                  <div className="text-xs text-gray-400">{s.sender_name || s.sender_email} · {s.date_sent ? new Date(s.date_sent).toLocaleDateString() : ''}</div>
                </div>
                <div className="ml-3 px-2 py-0.5 bg-purple-50 rounded text-xs text-purple-600">{Math.round(s.similarity * 100)}%</div>
              </div>
            </Link>
          ))}</div>}
        </div>
      )}
    </div>
  )
}
