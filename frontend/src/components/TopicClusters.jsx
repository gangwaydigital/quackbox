import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Tags, Cpu, RefreshCw, ChevronDown, ChevronRight, Mail, AlertCircle, CheckCircle2, X, StopCircle } from 'lucide-react'
import { api } from '../api/client'

const POLL_INTERVAL_MS = 2000

export default function TopicClusters() {
  const [topics, setTopics] = useState([])
  const [ollamaStatus, setOllamaStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [taskStatus, setTaskStatus] = useState(null)  // null | { running, phase, progress, embeddings_done, embeddings_total, error, result }
  const [expandedTopic, setExpandedTopic] = useState(null)
  const [topicEmails, setTopicEmails] = useState({})
  const pollRef = useRef(null)

  const isRunning = !!taskStatus?.running
  const ollamaReady = !!ollamaStatus?.available

  // Fetch topics + ollama status + resume polling if a job is already in flight
  useEffect(() => {
    loadTopics()
    api.checkOllama().then(setOllamaStatus).catch(() => setOllamaStatus({ available: false }))
    // On mount, check whether a clustering job is already running (e.g.
    // user navigated away and came back) and resume polling if so
    api.getClusteringStatus().then(s => {
      setTaskStatus(s)
      if (s.running) startPolling()
    }).catch(() => {})

    return () => stopPolling()
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

  const startPolling = () => {
    if (pollRef.current) return
    pollRef.current = setInterval(async () => {
      try {
        const s = await api.getClusteringStatus()
        setTaskStatus(s)
        if (!s.running) {
          stopPolling()
          // If clustering finished successfully, refresh the topics list
          if (!s.error && s.result) loadTopics()
        }
      } catch (err) {
        // Network blip — keep polling, don't tear down state
        console.warn('Status poll failed:', err)
      }
    }, POLL_INTERVAL_MS)
  }

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  const runClustering = async () => {
    setTaskStatus({ running: true, phase: 'starting', progress: 'Starting…', embeddings_done: 0, embeddings_total: 0 })
    try {
      await api.runClustering()
      startPolling()
    } catch (err) {
      setTaskStatus({ running: false, phase: 'error', error: err.message })
    }
  }

  const cancelClustering = async () => {
    try {
      await api.cancelClustering()
      // Don't stop polling here — the loop has to finish its current batch
      // before _task_status flips to running:false. Let the poll see it.
    } catch (err) {
      console.error('Cancel failed:', err)
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
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <Tags className="w-5 h-5 text-blue-600" />
          Topic Clusters
        </h2>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs">
            <Cpu className="w-3.5 h-3.5" />
            <span className={ollamaReady ? 'text-green-600 dark:text-green-400' : 'text-red-500 dark:text-red-400'}>
              Ollama: {ollamaReady ? 'Connected' : 'Offline'}
            </span>
          </div>
          <button
            onClick={runClustering}
            disabled={isRunning || !ollamaReady}
            className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw className={`w-4 h-4 ${isRunning ? 'animate-spin' : ''}`} />
            {isRunning ? 'Clustering…' : 'Run Clustering'}
          </button>
        </div>
      </div>

      {/* Status panel — running */}
      {taskStatus?.running && (
        <ProgressPanel status={taskStatus} onCancel={cancelClustering} />
      )}

      {/* Status panel — cancelled */}
      {!taskStatus?.running && taskStatus?.phase === 'cancelled' && (
        <div className="bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-700/50 rounded-lg px-4 py-3 flex items-start gap-2 text-sm text-amber-700 dark:text-amber-300">
          <StopCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <div>{taskStatus.progress}</div>
        </div>
      )}

      {/* Status panel — finished successfully */}
      {!taskStatus?.running && taskStatus?.phase === 'done' && taskStatus?.result && !taskStatus?.error && (
        <div className="bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-700/50 rounded-lg px-4 py-3 flex items-start gap-2 text-sm text-green-700 dark:text-green-300">
          <CheckCircle2 className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <div>{taskStatus.progress}</div>
        </div>
      )}

      {/* Status panel — error */}
      {!taskStatus?.running && taskStatus?.error && (
        <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700/50 rounded-lg px-4 py-3 flex items-start gap-2 text-sm text-red-700 dark:text-red-300">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <div>
            <div className="font-medium">Clustering failed</div>
            <div className="mt-0.5 font-mono text-xs">{taskStatus.error}</div>
          </div>
        </div>
      )}

      {/* Ollama not available message */}
      {ollamaStatus && !ollamaReady && (
        <div className="bg-yellow-50 dark:bg-yellow-900/40 border border-yellow-200 dark:border-yellow-800 rounded-lg px-4 py-3 text-sm text-yellow-700 dark:text-yellow-300">
          Ollama is not running. Start Ollama and pull the embedding model:
          <code className="block mt-2 bg-yellow-100 dark:bg-yellow-900/60 px-3 py-1.5 rounded text-xs">
            ollama pull nomic-embed-text
          </code>
        </div>
      )}

      {/* Topics list */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading topics…</div>
      ) : topics.length === 0 ? (
        <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-12 text-center">
          <Tags className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <p className="text-gray-500 mb-2">No topics generated yet.</p>
          <p className="text-sm text-gray-400">
            Click "Run Clustering" to discover topics in your email archive.
            Embedding ~50,000 emails on local Ollama can take 30–90 minutes;
            you can navigate away and come back — progress will resume on this page.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {topics.map(topic => (
            <div key={topic.id} className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
              {/* Topic header */}
              <button
                onClick={() => toggleTopic(topic.id)}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors text-left"
              >
                <div className="flex items-center gap-3">
                  {expandedTopic === topic.id
                    ? <ChevronDown className="w-4 h-4 text-gray-400" />
                    : <ChevronRight className="w-4 h-4 text-gray-400" />}
                  <div>
                    <span className="font-medium text-sm text-gray-900 dark:text-white">{topic.label}</span>
                    {topic.keywords.length > 0 && (
                      <div className="flex gap-1 mt-1">
                        {topic.keywords.slice(0, 5).map(kw => (
                          <span key={kw} className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-xs text-gray-500">
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
                <div className="border-t border-gray-100 dark:border-gray-800 divide-y divide-gray-50 dark:divide-gray-800">
                  {(topicEmails[topic.id] || []).slice(0, 10).map(email => (
                    <Link
                      key={email.id}
                      to={`/email/${email.id}`}
                      className="block px-8 py-2 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
                    >
                      <div className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-gray-600 dark:text-gray-400 truncate">{email.sender_name || email.sender_email}</span>
                          <span className="text-gray-400">—</span>
                          <span className="text-gray-800 dark:text-gray-200 truncate">{email.subject || '(no subject)'}</span>
                        </div>
                        <span className="text-xs text-gray-400 whitespace-nowrap ml-4">
                          {email.date_sent ? new Date(email.date_sent).toLocaleDateString() : ''}
                        </span>
                      </div>
                    </Link>
                  ))}
                  {(topicEmails[topic.id] || []).length > 10 && (
                    <div className="px-8 py-2 text-xs text-gray-400">
                      … and {topic.email_count - 10} more
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


function formatEta(seconds) {
  if (seconds == null) return null
  if (seconds < 60) return `~${seconds}s left`
  if (seconds < 3600) return `~${Math.round(seconds / 60)}m left`
  const h = Math.floor(seconds / 3600)
  const m = Math.round((seconds - h * 3600) / 60)
  return `~${h}h ${m}m left`
}

function ProgressPanel({ status, onCancel }) {
  const {
    phase, progress, embeddings_done, embeddings_total,
    embeddings_per_second, eta_seconds,
  } = status
  const pct = embeddings_total > 0
    ? Math.min(100, Math.round((embeddings_done / embeddings_total) * 100))
    : null
  const cancelling = (progress || '').toLowerCase().startsWith('cancelling')
  const etaLabel = formatEta(eta_seconds)

  return (
    <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700/50 rounded-lg px-4 py-3 space-y-2">
      <div className="flex items-center gap-2 text-sm text-blue-700 dark:text-blue-300">
        <RefreshCw className="w-4 h-4 animate-spin flex-shrink-0" />
        <span className="font-medium flex-1">{progress || `Working… (${phase})`}</span>
        <button
          onClick={onCancel}
          disabled={cancelling}
          title="Cancel — already-completed embeddings stay persisted"
          className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-white dark:bg-blue-900/50 border border-blue-300 dark:border-blue-700 text-blue-700 dark:text-blue-200 rounded-md hover:bg-blue-100 dark:hover:bg-blue-900/70 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <X className="w-3 h-3" />
          {cancelling ? 'Cancelling…' : 'Cancel'}
        </button>
      </div>
      {pct !== null && phase === 'embedding' && (
        <div className="space-y-1">
          <div className="h-1.5 bg-blue-100 dark:bg-blue-900/60 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 dark:bg-blue-400 rounded-full transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-[10px] text-blue-600 dark:text-blue-400">
            <span>
              {embeddings_per_second != null && embeddings_per_second > 0 && (
                <>{embeddings_per_second}/s</>
              )}
            </span>
            <span className="text-right">
              {embeddings_done.toLocaleString()} / {embeddings_total.toLocaleString()}
              {etaLabel && <span className="ml-2 font-medium">· {etaLabel}</span>}
            </span>
          </div>
        </div>
      )}
      <div className="text-[10px] text-blue-600/70 dark:text-blue-400/70">
        Safe to navigate away — progress will resume when you come back. Cancelling preserves embeddings already generated.
      </div>
    </div>
  )
}
