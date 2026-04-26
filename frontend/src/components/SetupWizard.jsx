import { useState, useEffect } from 'react'
import { Mail, FolderSearch, Play, CheckCircle, AlertCircle, Loader, Archive, Inbox, Clock } from 'lucide-react'
import { api } from '../api/client'

export default function SetupWizard({ onComplete }) {
  const [phase, setPhase] = useState('scanning')
  const [scanResult, setScanResult] = useState(null)
  const [progress, setProgress] = useState(null)

  useEffect(() => {
    api.scanData().then(data => {
      setScanResult(data)
      setPhase(data.total_files > 0 ? 'ready' : 'empty')
    }).catch(err => { setPhase('error'); setProgress({ error: err.message }) })
  }, [])

  const startImport = async () => {
    setPhase('ingesting')
    try {
      await api.startIngest()
      const poll = setInterval(async () => {
        try {
          const status = await api.getIngestProgress()
          setProgress(status)
          if (!status.running && status.phase === 'done') { clearInterval(poll); setPhase('done') }
          else if (!status.running && status.error) { clearInterval(poll); setPhase('error') }
        } catch { clearInterval(poll); setPhase('error') }
      }, 1000)
    } catch (err) { setPhase('error'); setProgress({ error: err.message }) }
  }

  const fmtTime = (s) => s >= 60 ? `${Math.floor(s/60)}m ${s%60}s` : `${s}s`

  return (
    <div className="max-w-2xl mx-auto py-12">
      <div className="text-center mb-8">
        <div className="w-16 h-16 rounded-2xl bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center mx-auto mb-4">
          <Mail className="w-8 h-8 text-blue-600 dark:text-blue-300" />
        </div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Welcome to QuackBox 🦆</h1>
        <p className="text-gray-500 mt-2">Let's import your email archive to get started.</p>
      </div>

      {phase === 'scanning' && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-8 text-center">
          <Loader className="w-8 h-8 text-blue-500 mx-auto mb-3 animate-spin" />
          <p className="text-gray-600 dark:text-gray-400">Scanning data directory for email files...</p>
        </div>
      )}

      {phase === 'empty' && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-8">
          <div className="text-center mb-6">
            <FolderSearch className="w-10 h-10 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
            <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">No Email Data Found</h2>
            <p className="text-sm text-gray-500 mt-1">Place your email files in the data directory and refresh.</p>
          </div>
          <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 text-sm space-y-2">
            <p className="font-medium text-gray-700 dark:text-gray-300">Supported formats:</p>
            <div className="text-gray-500 space-y-1">
              <p>Apple Mail .emlx — Copy your V10 mailbox folder</p>
              <p>.mbox files — Standard mbox format (Google Takeout, Thunderbird)</p>
              <p>Apple Mail bundles — .mbox folders with nested mbox files</p>
            </div>
            <p className="text-gray-500 mt-3">Data directory: <code className="px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">{scanResult?.data_dir || '/app/data'}</code></p>
          </div>
          <button onClick={() => { setPhase('scanning'); api.scanData().then(d => { setScanResult(d); setPhase(d.total_files > 0 ? 'ready' : 'empty') }) }}
            className="w-full mt-4 px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium">
            Scan Again
          </button>
        </div>
      )}

      {phase === 'ready' && scanResult && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-6 space-y-5">
          <div className="text-center">
            <CheckCircle className="w-10 h-10 text-green-500 mx-auto mb-2" />
            <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">Email Data Found!</h2>
          </div>
          <div className="space-y-3">
            {scanResult.emlx_mailboxes?.length > 0 && (
              <div className="bg-blue-50 dark:bg-blue-900/40 rounded-lg p-4">
                <div className="text-sm font-medium text-blue-800 dark:text-blue-200 mb-2 flex items-center gap-2">
                  <Inbox className="w-4 h-4" /> Apple Mail Mailboxes ({scanResult.emlx_mailboxes.length})
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {scanResult.emlx_mailboxes.slice(0, 12).map(m => (
                    <div key={m.name} className="flex items-center justify-between text-sm bg-white/60 rounded px-2 py-1">
                      <span className="text-blue-700 truncate">{m.name}</span>
                      <span className="text-blue-500 text-xs flex-shrink-0 ml-2">{m.message_count.toLocaleString()}</span>
                    </div>
                  ))}
                  {scanResult.emlx_mailboxes.length > 12 && (
                    <div className="text-xs text-blue-500 col-span-2">...and {scanResult.emlx_mailboxes.length - 12} more</div>
                  )}
                </div>
              </div>
            )}
            {scanResult.mbox_files?.length > 0 && (
              <div className="bg-purple-50 dark:bg-purple-900/40 rounded-lg p-4">
                <div className="text-sm font-medium text-purple-800 dark:text-purple-200 mb-2 flex items-center gap-2">
                  <Archive className="w-4 h-4" /> Mbox Files ({scanResult.mbox_files.length})
                </div>
                <div className="space-y-1">
                  {scanResult.mbox_files.slice(0, 8).map(f => (
                    <div key={f.path} className="flex items-center justify-between text-sm bg-white/60 rounded px-2 py-1">
                      <span className="text-purple-700 truncate">{f.name}</span>
                      <span className="text-purple-500 text-xs flex-shrink-0 ml-2">{f.size_mb} MB</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          <button onClick={startImport}
            className="w-full px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium flex items-center justify-center gap-2">
            <Play className="w-4 h-4" /> Import All Email Data
          </button>
        </div>
      )}

      {phase === 'ingesting' && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-6 space-y-5">
          <div className="text-center">
            <Loader className="w-10 h-10 text-blue-500 mx-auto mb-3 animate-spin" />
            <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">Importing Emails...</h2>
          </div>

          {progress && (
            <div className="space-y-4">
              {/* Main progress bar */}
              <div>
                <div className="flex items-center justify-between text-xs text-gray-500 mb-1.5">
                  <span>{progress.current_source ? `Importing: ${progress.current_source}` : progress.progress}</span>
                  <span>{progress.files_done}/{progress.files_total} sources</span>
                </div>
                <div className="w-full bg-gray-100 dark:bg-gray-800 rounded-full h-3 overflow-hidden">
                  <div className="bg-blue-600 h-full rounded-full transition-all duration-700 ease-out"
                    style={{ width: progress.files_total ? `${Math.max(2, (progress.files_done / progress.files_total) * 100)}%` : '5%' }} />
                </div>
              </div>

              {/* Stats row */}
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="bg-blue-50 dark:bg-blue-900/40 rounded-lg py-2">
                  <div className="text-lg font-bold text-blue-700 dark:text-blue-300">{(progress.emails_imported || 0).toLocaleString()}</div>
                  <div className="text-[10px] text-blue-500">imported</div>
                </div>
                <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg py-2">
                  <div className="text-lg font-bold text-gray-700 dark:text-gray-300">{(progress.emails_skipped || 0).toLocaleString()}</div>
                  <div className="text-[10px] text-gray-400">skipped (dupes)</div>
                </div>
                <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg py-2 flex flex-col items-center justify-center">
                  <div className="text-lg font-bold text-gray-700 dark:text-gray-300 flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" /> {fmtTime(progress.elapsed_seconds || 0)}
                  </div>
                  <div className="text-[10px] text-gray-400">elapsed</div>
                </div>
              </div>

              {/* Per-source log */}
              {progress.sources_progress?.length > 0 && (
                <div className="max-h-40 overflow-y-auto space-y-1">
                  {progress.sources_progress.map((s, i) => (
                    <div key={i} className="flex items-center justify-between text-xs bg-gray-50 dark:bg-gray-800/50 rounded px-3 py-1.5">
                      <span className="text-gray-600 dark:text-gray-400 truncate">{s.name}</span>
                      <div className="flex items-center gap-3 flex-shrink-0">
                        <span className="text-green-600">{s.imported.toLocaleString()} new</span>
                        {s.skipped > 0 && <span className="text-gray-400">{s.skipped} skipped</span>}
                        <CheckCircle className="w-3 h-3 text-green-500" />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {phase === 'done' && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-8 text-center">
          <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-3" />
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">Import Complete!</h2>
          <p className="text-sm text-gray-500 mt-1">{progress?.progress}</p>
          {progress?.sources_progress?.length > 0 && (
            <div className="mt-4 max-h-32 overflow-y-auto text-left">
              {progress.sources_progress.map((s, i) => (
                <div key={i} className="flex items-center justify-between text-xs px-3 py-1">
                  <span className="text-gray-600 dark:text-gray-400">{s.name}</span>
                  <span className="text-green-600">{s.imported.toLocaleString()} emails</span>
                </div>
              ))}
            </div>
          )}
          <button onClick={onComplete}
            className="mt-6 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium">
            Start Exploring
          </button>
        </div>
      )}

      {phase === 'error' && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-red-200 dark:border-red-800 p-8 text-center">
          <AlertCircle className="w-10 h-10 text-red-400 mx-auto mb-3" />
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">Import Error</h2>
          <p className="text-sm text-red-600 mt-2">{progress?.error || 'Unknown error'}</p>
          <button onClick={() => setPhase('scanning')}
            className="mt-4 px-4 py-2 bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 text-sm">Try Again</button>
        </div>
      )}
    </div>
  )
}
