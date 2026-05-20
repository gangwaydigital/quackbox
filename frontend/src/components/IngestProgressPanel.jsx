/**
 * IngestProgressPanel — live progress + per-source breakdown for the
 * /api/ingest/progress polling cycle.
 *
 * Extracted from ImportStatus.jsx so the Mailboxes page composition is
 * easier to follow. Exported as ProgressPanel to match the original
 * internal name. Behavior unchanged.
 */
import { useState } from 'react'
import { RefreshCw, CheckCircle, AlertCircle, ChevronDown, ChevronRight } from 'lucide-react'

const MODE_BADGE = {
  incremental: 'bg-blue-100 text-blue-700',
  full:        'bg-purple-100 text-purple-700',
  unchanged:   'bg-gray-100 text-gray-500',
}

export default function ProgressPanel({ status }) {
  const [expanded, setExpanded] = useState(false)

  if (!status?.running && status?.phase !== 'done' && status?.phase !== 'error') return null

  return (
    <div className={`rounded-xl border p-4 space-y-3 ${
      status.phase === 'error' ? 'bg-red-50 border-red-200' :
      status.phase === 'done'  ? 'bg-green-50 border-green-200' :
                                  'bg-blue-50 border-blue-200'
    }`}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {status.running ? (
            <RefreshCw className="w-4 h-4 text-blue-500 animate-spin" />
          ) : status.phase === 'done' ? (
            <CheckCircle className="w-4 h-4 text-green-500" />
          ) : (
            <AlertCircle className="w-4 h-4 text-red-500" />
          )}
          <span className="text-sm font-medium text-gray-800">{status.progress}</span>
        </div>
        {status.sources_progress?.length > 0 && (
          <button onClick={() => setExpanded(e => !e)}
            className="text-gray-400 hover:text-gray-600 transition-colors">
            {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        )}
      </div>

      {/* Progress bar */}
      {status.running && status.files_total > 0 && (
        <div>
          <div className="h-1.5 bg-blue-100 rounded-full overflow-hidden">
            <div className="h-full bg-blue-500 rounded-full transition-all duration-500"
              style={{ width: `${Math.max(3, (status.files_done / status.files_total) * 100)}%` }} />
          </div>
          <div className="flex justify-between text-[10px] text-blue-500 mt-1">
            <span>{status.current_source || 'Processing…'}</span>
            <span>{status.files_done}/{status.files_total} sources</span>
          </div>
        </div>
      )}

      {/* Counters */}
      <div className="flex items-center gap-4">
        <div className="text-center">
          <div className="text-lg font-bold text-blue-700">{(status.emails_imported || 0).toLocaleString()}</div>
          <div className="text-[10px] text-blue-500">imported</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-bold text-gray-500">{(status.emails_skipped || 0).toLocaleString()}</div>
          <div className="text-[10px] text-gray-400">skipped</div>
        </div>
        {status.elapsed_seconds > 0 && (
          <div className="text-center">
            <div className="text-lg font-bold text-gray-500">{status.elapsed_seconds}s</div>
            <div className="text-[10px] text-gray-400">elapsed</div>
          </div>
        )}
      </div>

      {/* Per-source breakdown */}
      {expanded && status.sources_progress?.length > 0 && (
        <div className="space-y-1 border-t border-blue-100 pt-3">
          {status.sources_progress.map((s, i) => (
            <div key={i} className="flex items-center justify-between text-xs text-gray-600">
              <span className="truncate flex-1">{s.name}</span>
              <div className="flex items-center gap-3 flex-shrink-0">
                {s.mode && (
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${MODE_BADGE[s.mode] || MODE_BADGE.unchanged}`}>
                    {s.mode}
                  </span>
                )}
                <span className="text-green-600 font-medium">+{s.imported}</span>
                <span className="text-gray-400">{s.skipped} skipped</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
