import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Paperclip, Tag } from 'lucide-react'
import { api } from '../api/client'

export default function EmailDetail() {
  const { id } = useParams()
  const [email, setEmail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showHtml, setShowHtml] = useState(false)

  useEffect(() => {
    setLoading(true)
    api.getEmail(id)
      .then(setEmail)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return <div className="text-center py-12 text-gray-500">Loading...</div>
  }

  if (!email) {
    return <div className="text-center py-12 text-gray-500">Email not found.</div>
  }

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      {/* Back link */}
      <Link to="/" className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700">
        <ArrowLeft className="w-4 h-4" /> Back to inbox
      </Link>

      {/* Email header */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-3">
        <h2 className="text-xl font-semibold text-gray-900">
          {email.subject || '(no subject)'}
        </h2>

        <div className="space-y-1.5 text-sm">
          <div className="flex gap-2">
            <span className="text-gray-500 w-16">From:</span>
            <span className="text-gray-900">
              {email.sender_name && <strong>{email.sender_name}</strong>}
              {email.sender_email && (
                <span className="text-gray-500"> &lt;{email.sender_email}&gt;</span>
              )}
            </span>
          </div>

          {email.recipients?.length > 0 && (
            <div className="flex gap-2">
              <span className="text-gray-500 w-16">To:</span>
              <span className="text-gray-700">
                {email.recipients
                  .filter(r => r.type === 'to')
                  .map(r => r.name || r.email)
                  .join(', ')}
              </span>
            </div>
          )}

          {email.recipients?.filter(r => r.type === 'cc').length > 0 && (
            <div className="flex gap-2">
              <span className="text-gray-500 w-16">Cc:</span>
              <span className="text-gray-700">
                {email.recipients
                  .filter(r => r.type === 'cc')
                  .map(r => r.name || r.email)
                  .join(', ')}
              </span>
            </div>
          )}

          <div className="flex gap-2">
            <span className="text-gray-500 w-16">Date:</span>
            <span className="text-gray-700">
              {email.date_sent ? new Date(email.date_sent).toLocaleString() : 'Unknown'}
            </span>
          </div>

          <div className="flex gap-2">
            <span className="text-gray-500 w-16">Source:</span>
            <span className="text-gray-400 text-xs">{email.mbox_source}</span>
          </div>
        </div>

        {/* Attachments */}
        {email.attachment_names?.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-100">
            {email.attachment_names.map((name, i) => (
              <span key={i} className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 rounded text-xs text-gray-600">
                <Paperclip className="w-3 h-3" /> {name}
              </span>
            ))}
          </div>
        )}

        {/* Topics */}
        {email.topics?.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-100">
            {email.topics.map(topic => (
              <Link
                key={topic.id}
                to={`/topics`}
                className="inline-flex items-center gap-1 px-2 py-1 bg-blue-50 text-blue-700 rounded text-xs hover:bg-blue-100"
              >
                <Tag className="w-3 h-3" /> {topic.label}
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Email body */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        {email.body_html && (
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => setShowHtml(false)}
              className={`text-xs px-3 py-1 rounded-full ${!showHtml ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600'}`}
            >
              Plain Text
            </button>
            <button
              onClick={() => setShowHtml(true)}
              className={`text-xs px-3 py-1 rounded-full ${showHtml ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600'}`}
            >
              HTML
            </button>
          </div>
        )}

        {showHtml && email.body_html ? (
          <div
            className="prose prose-sm max-w-none"
            dangerouslySetInnerHTML={{ __html: email.body_html }}
          />
        ) : (
          <pre className="whitespace-pre-wrap text-sm text-gray-800 font-sans leading-relaxed">
            {email.body_text || '(no body)'}
          </pre>
        )}
      </div>
    </div>
  )
}
