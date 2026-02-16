import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Tags, Cpu, RefreshCw, ChevronDown, ChevronRight, Mail } from 'lucide-react'
import { api } from '../api/client'

export default function TopicClusters() {
  const [topics, setTopics] = useState([])
  const [ollamaStatus, setOllamaStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [clustering, setClustering] = useState(false)
  const [expandedTopic, setExpandedTopic] = useState(null)
  const [topicEmails, setTopicEmails] = useState({})
  const [statusMessage, setStatusMessage] = useState('')

  useEffect(() => {
    loadTopics()
    api.checkOllama().then(setOllamaStatus).catch(() => setOllamaStatus({ available: false }))
  }, [])

  const loadTopics = async () => {
    setLoading(true)
    try {
      const data = await api.getTopics()
      setTopics(data.topics || [])
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const runClustering = async () => {
    setClustering(true)
    setStatusMessage('Generating embeddings and clustering... this may take a while.')
    try {
      const result = await api.runClustering()
      setStatusMessage(
        `✅ Created ${result.num_clusters} topics from ${result.total_emails_clustered} emails (${result.duration_seconds}s)`
      )
      await loadTopics()
    } catch (err) {
      setStatusMessage(`❌ Error: ${err.message}`)
    } finally {
      setClustering(false)
    }
  }

  const toggleTopic = async (topicId) => {
    if (expandedTopic === topicId) {
      setExpandedTopic(null)
      return
    }
    setExpandedTopic(topicId)
    if (!topicEmails[topicId]) {
      try {
        const data = await api.getTopic(topicId)
        setTopicEmails(prev => ({ ...prev, [topicId]: data.emails?.items || [] }))
      } catch (err) {
        console.error(err)
      }
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Tags className="w-5 h-5 text-blue-600" />
          Topic Clusters
        </h2>
        <div className="flex items-center gap-3">
          {/* Ollama status indicator */}
          <div className="flex items-center gap-1.5 text-xs">
            <Cpu className="w-3.5 h-3.5" />
            <span className={ollamaStatus?.available ? 'text-green-600' : 'text-red-500'}>
              Ollama: {ollamaStatus?.available ? 'Connected' : 'Offline'}
            </span>
          </div>
          <button
            onClick={runClustering}
            disabled={clustering || !ollamaStatus?.available}
            className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw className={`w-4 h-4 ${clustering ? 'animate-spin' : ''}`} />
            {clustering ? 'Clustering...' : 'Run Clustering'}
          </button>
        </div>
      </div>

      {/* Status message */}
      {statusMessage && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-sm text-blue-700">
          {statusMessage}
        </div>
      )}

      {/* Ollama not available message */}
      {ollamaStatus && !ollamaStatus.available && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3 text-sm text-yellow-700">
          Ollama is not running. Start Ollama and pull the embedding model:
          <code className="block mt-2 bg-yellow-100 px-3 py-1.5 rounded text-xs">
            ollama pull nomic-embed-text
          </code>
        </div>
      )}

      {/* Topics list */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading topics...</div>
      ) : topics.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <Tags className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500 mb-2">No topics generated yet.</p>
          <p className="text-sm text-gray-400">
            Click "Run Clustering" to discover topics in your email archive.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {topics.map(topic => (
            <div key={topic.id} className="bg-white rounded-lg border border-gray-200 overflow-hidden">
              {/* Topic header */}
              <button
                onClick={() => toggleTopic(topic.id)}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors text-left"
              >
                <div className="flex items-center gap-3">
                  {expandedTopic === topic.id
                    ? <ChevronDown className="w-4 h-4 text-gray-400" />
                    : <ChevronRight className="w-4 h-4 text-gray-400" />}
                  <div>
                    <span className="font-medium text-sm text-gray-900">{topic.label}</span>
                    {topic.keywords.length > 0 && (
                      <div className="flex gap-1 mt-1">
                        {topic.keywords.slice(0, 5).map(kw => (
                          <span key={kw} className="px-1.5 py-0.5 bg-gray-100 rounded text-xs text-gray-500">
                            {kw}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
                <span className="flex items-center gap-1 text-xs text-gray-400">
                  <Mail className="w-3.5 h-3.5" />
                  {topic.email_count}
                </span>
              </button>

              {/* Expanded email list */}
              {expandedTopic === topic.id && (
                <div className="border-t border-gray-100 divide-y divide-gray-50">
                  {(topicEmails[topic.id] || []).slice(0, 10).map(email => (
                    <Link
                      key={email.id}
                      to={`/email/${email.id}`}
                      className="block px-8 py-2 hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-gray-600 truncate">{email.sender_name || email.sender_email}</span>
                          <span className="text-gray-400">—</span>
                          <span className="text-gray-800 truncate">{email.subject || '(no subject)'}</span>
                        </div>
                        <span className="text-xs text-gray-400 whitespace-nowrap ml-4">
                          {email.date_sent ? new Date(email.date_sent).toLocaleDateString() : ''}
                        </span>
                      </div>
                    </Link>
                  ))}
                  {(topicEmails[topic.id] || []).length > 10 && (
                    <div className="px-8 py-2 text-xs text-gray-400">
                      ... and {topic.email_count - 10} more
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
