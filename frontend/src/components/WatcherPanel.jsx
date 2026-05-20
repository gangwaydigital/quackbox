/**
 * WatcherPanel — status + Scan-now control for the background watcher.
 *
 * Extracted from ImportStatus.jsx so the Mailboxes page composition is
 * easier to follow. Behavior unchanged.
 */
import { useState, useEffect } from 'react'
import { Eye, EyeOff, Zap } from 'lucide-react'
import { api } from '../api/client'

function formatRelative(epochSeconds) {
  if (!epochSeconds) return 'never'
  const ms = Date.now() - epochSeconds * 1000
  const sec = Math.round(ms / 1000)
  if (sec < 60) return `${sec}s ago`
  const min = Math.round(sec / 60)
  if (min < 60) return `${min}m ago`
  const hr = Math.round(min / 60)
  if (hr < 24) return `${hr}h ago`
  return `${Math.round(hr / 24)}d ago`
}

export default function WatcherPanel({ disabled }) {
  const [status, setStatus] = useState(null)
  const [scanning, setScanning] = useState(false)
  const [scanResult, setScanResult] = useState(null)

  // Force a re-render every 10s so "Xm ago" stays fresh, and refetch the status
  useEffect(() => {
    let timer
    const tick = async () => {
      try {
        const s = await api.getWatcherStatus()
        setStatus(s)
      } catch {}
    }
    tick()
    timer = setInterval(tick, 10_000)
    return () => clearInterval(timer)
  }, [])

  const scanNow = async () => {
    setScanning(true)
    setScanResult(null)
    try {
      const result = await api.triggerWatcherScan()
      setScanResult(result)
      // Re-fetch status so checks/runs counters refresh
      const s = await api.getWatcherStatus()
      setStatus(s)
    } catch (err) {
      setScanResult({ queued: false, reason: err.message })
    } finally {
      setScanning(false)
    }
  }

  if (!status) return null

  const enabled = status.enabled
  const intervalMin = Math.round((status.interval_seconds || 0) / 60)
  const nextEta = status.last_check_at && status.interval_seconds
    ? Math.max(0, status.interval_seconds - Math.round(Date.now() / 1000 - status.last_check_at))
    : null

  const reasonLabel = {
    no_new_content: 'Nothing new on disk.',
    ingest_already_running: 'An ingest is already running.',
    ingest_started: 'Scan triggered — watch the progress panel below.',
  }

  return (
    <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 space-y-3">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          {enabled
            ? <Eye className="w-4 h-4 text-green-600 dark:text-green-400" />
            : <EyeOff className="w-4 h-4 text-gray-400" />
          }
          <span className="text-sm font-medium text-gray-800 dark:text-gray-200">Auto-import watcher</span>
          <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${
            enabled
              ? 'bg-green-50 dark:bg-green-900/40 text-green-700 dark:text-green-300'
              : 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400'
          }`}>
            {enabled ? `Every ${intervalMin}m` : 'Disabled'}
          </span>
        </div>
        {enabled && (
          <button
            onClick={scanNow}
            disabled={scanning || disabled}
            title="Run a scan now without waiting for the next tick"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs bg-blue-50 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-700 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/60 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Zap className={`w-3 h-3 ${scanning ? 'animate-pulse' : ''}`} />
            {scanning ? 'Scanning…' : 'Scan now'}
          </button>
        )}
      </div>

      {enabled && (
        <div className="grid grid-cols-3 gap-3 text-xs">
          <div>
            <div className="text-gray-400 text-[10px] uppercase tracking-wider">Last check</div>
            <div className="text-gray-700 dark:text-gray-300 font-medium">{formatRelative(status.last_check_at)}</div>
          </div>
          <div>
            <div className="text-gray-400 text-[10px] uppercase tracking-wider">Total checks</div>
            <div className="text-gray-700 dark:text-gray-300 font-medium">{status.checks?.toLocaleString() || 0}</div>
          </div>
          <div>
            <div className="text-gray-400 text-[10px] uppercase tracking-wider">Auto runs</div>
            <div className="text-gray-700 dark:text-gray-300 font-medium">{status.runs?.toLocaleString() || 0}</div>
          </div>
        </div>
      )}

      {enabled && status.last_status_summary && (
        <div className="text-xs text-gray-500 dark:text-gray-400">
          <span className="text-gray-400">Last result:</span> {status.last_status_summary}
          {nextEta !== null && (
            <span className="text-gray-400"> · next check in {Math.max(0, nextEta)}s</span>
          )}
        </div>
      )}

      {scanResult && (
        <div className={`text-xs px-3 py-2 rounded-lg ${
          scanResult.queued
            ? 'bg-blue-50 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300'
            : 'bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-400'
        }`}>
          {reasonLabel[scanResult.reason] || scanResult.reason}
        </div>
      )}

      {!enabled && (
        <div className="text-xs text-gray-500 dark:text-gray-400">
          Set <code className="font-mono px-1 py-0.5 bg-gray-100 dark:bg-gray-800 rounded">WATCH_INTERVAL_MINUTES=15</code> in <code className="font-mono px-1 py-0.5 bg-gray-100 dark:bg-gray-800 rounded">.env</code> and restart the backend to enable automatic re-import as new mail arrives in <code className="font-mono px-1 py-0.5 bg-gray-100 dark:bg-gray-800 rounded">DATA_PATH</code>.
        </div>
      )}
    </div>
  )
}
