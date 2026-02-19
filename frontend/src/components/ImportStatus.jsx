/**
 * ImportStatus — live source health panel.
 *
 * Shows each ingested source with its status (unchanged / updated / new / missing),
 * estimated new email count, and last-import timestamp. Provides buttons to run
 * an incremental import or force a full re-scan.
 *
 * Meant to live on the Mailboxes page and/or be accessible from the sidebar.
 */
import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, CheckCircle, AlertCircle, Clock, Database,
         Inbox, Archive, XCircle, Zap, RotateCcw, ChevronDown, ChevronRight } from 'lucide-react'
import { api } from '../api/client'
import { OnboardingBanner } from './OnboardingTips'

const STATUS_CONFIG = {
  new:       { label: 'New source',   color: 'text-blue-600',  bg: 'bg-blue-50  border-blue-200',  icon: Inbox },
  updated:   { label: 'Has new mail', color: 'text-amber-600', bg: 'bg-amber-50 border-amber-200', icon: AlertCircle },
  unchanged: { label: 'Up to date',   color: 'text-green-600', bg: 'bg-green-50 border-green-200', icon: CheckCircle },
  missing:   { label: 'File missing', color: 'text-red-500',   bg: 'bg-red-50   border-red-200',   icon: XCircle },
}

const MODE_BADGE = {
  incremental: 'bg-blue-100 text-blue-700',
  full:        'bg-purple-100 text-purple-700',
  unchanged:   'bg-gray-100 text-gray-500',
}

function formatTime(iso) {
  if (!iso) return '—'
  try {
    const d = new Date(iso + 'Z')
    return d.toLocaleString(undefined, { month: 'short', day: 'numeric',
                                         hour: '2-digit', minute: '2-digit' })
  } catch { return iso }
}

function SourceRow({ source }) {
  const cfg = STATUS_CONFIG[source.status] || STATUS_CONFIG.unchanged
  const Icon = cfg.icon
  const TypeIcon = source.source_type === 'emlx' ? Inbox : Archive

  return (
    <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${cfg.bg} transition-colors`}>
      <TypeIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-gray-800 truncate">{source.source_name}</span>
          <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${cfg.color}`}>
            <Icon className="w-2.5 h-2.5" />
            {cfg.label}
          </span>
        </div>
        <div className="flex items-center gap-3 mt-0.5 text-xs text-gray-400">
          <span className="flex items-center gap-1">
            <Database className="w-3 h-3" />
            {source.emails_total?.toLocaleString() ?? 0} stored
          </span>
          {source.new_count != null && source.new_count > 0 && (
            <span className="text-amber-600 font-medium">
              +{source.new_count} new
            </span>
          )}
          {source.new_count === null && source.status === 'updated' && (
            <span className="text-amber-600 font-medium">updated</span>
          )}
          {source.last_ingest_at && (
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatTime(source.last_ingest_at)}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

function ProgressPanel({ status }) {
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

export default function ImportStatus({ compact = false }) {
  const [checkData, setCheckData] = useState(null)
  const [checking, setChecking] = useState(false)
  const [importStatus, setImportStatus] = useState(null)
  const [polling, setPolling] = useState(false)

  const check = useCallback(async () => {
    setChecking(true)
    try {
      const data = await api.checkIngest()
      setCheckData(data)
    } catch (err) {
      console.error('Check failed:', err)
    } finally {
      setChecking(false)
    }
  }, [])

  // Poll progress while running
  useEffect(() => {
    let timer
    if (polling) {
      const tick = async () => {
        try {
          const status = await api.getIngestProgress()
          setImportStatus(status)
          if (!status.running) {
            setPolling(false)
            // Refresh source status after import finishes
            check()
          }
        } catch (err) {
          console.error('Progress poll error:', err)
          setPolling(false)
        }
      }
      tick()
      timer = setInterval(tick, 1500)
    }
    return () => clearInterval(timer)
  }, [polling, check])

  useEffect(() => { check() }, [check])

  const runImport = async (force = false) => {
    try {
      await api.startIngest(force)
      setPolling(true)
      const status = await api.getIngestProgress()
      setImportStatus(status)
    } catch (err) {
      console.error('Import start failed:', err)
    }
  }

  const hasUpdates = checkData?.has_updates
  const sources = checkData?.sources || []
  const isRunning = importStatus?.running || polling

  if (compact) {
    // Minimal version for embedding in other pages
    return (
      <div className="flex items-center gap-2">
        {hasUpdates && (
          <span className="text-xs text-amber-600 font-medium flex items-center gap-1">
            <AlertCircle className="w-3.5 h-3.5" />
            New mail available
          </span>
        )}
        <button
          onClick={() => runImport(false)}
          disabled={isRunning}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-xs rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
          {isRunning
            ? <><RefreshCw className="w-3 h-3 animate-spin" /> Importing…</>
            : <><Zap className="w-3 h-3" /> {hasUpdates ? 'Import new' : 'Check for new'}</>
          }
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <Database className="w-5 h-5 text-blue-600" />
          Import Sources
          {checkData && (
            <span className="text-sm font-normal text-gray-400">
              ({sources.length} source{sources.length !== 1 ? 's' : ''})
            </span>
          )}
        </h2>
        <div className="flex items-center gap-2">
          <button
            onClick={check}
            disabled={checking || isRunning}
            title="Check for new emails"
            className="flex items-center gap-1.5 px-3 py-2 border border-gray-200 text-gray-600 text-sm rounded-lg hover:bg-gray-50 disabled:opacity-40 transition-colors">
            <RefreshCw className={`w-4 h-4 ${checking ? 'animate-spin' : ''}`} />
            {checking ? 'Checking…' : 'Check'}
          </button>
          <button
            onClick={() => runImport(true)}
            disabled={isRunning}
            title="Force full re-scan of all sources"
            className="flex items-center gap-1.5 px-3 py-2 border border-gray-200 text-gray-600 text-sm rounded-lg hover:bg-gray-50 disabled:opacity-40 transition-colors">
            <RotateCcw className="w-4 h-4" />
            Full re-scan
          </button>
          <button
            onClick={() => runImport(false)}
            disabled={isRunning || (!hasUpdates && !checking)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors disabled:opacity-40 ${
              hasUpdates
                ? 'bg-amber-500 text-white hover:bg-amber-600'
                : 'bg-blue-600 text-white hover:bg-blue-700'
            }`}>
            {isRunning
              ? <><RefreshCw className="w-4 h-4 animate-spin" /> Importing…</>
              : <><Zap className="w-4 h-4" /> {hasUpdates ? 'Import New Mail' : 'Run Import'}</>
            }
          </button>
        </div>
      </div>

      <OnboardingBanner id="import-incremental">
        QuackBox now tracks each import source. <strong>Incremental imports</strong> only process
        new emails — unchanged sources are skipped instantly. Use <em>Full re-scan</em> only if
        you've manually moved or replaced source files.
      </OnboardingBanner>

      {/* Active progress */}
      {importStatus && <ProgressPanel status={importStatus} />}

      {/* Source list */}
      {sources.length === 0 && !checking ? (
        <div className="py-10 text-center text-gray-400 text-sm">
          No sources tracked yet. Run an import to get started.
        </div>
      ) : (
        <div className="space-y-2">
          {sources.map(source => (
            <SourceRow key={source.source_name} source={source} />
          ))}
        </div>
      )}

      {checkData && (
        <div className="text-xs text-gray-400 text-right">
          {hasUpdates
            ? `${checkData.total_new_estimated > 0 ? `~${checkData.total_new_estimated.toLocaleString()} new emails estimated` : 'Updates detected'}`
            : 'All sources up to date'}
        </div>
      )}
    </div>
  )
}
