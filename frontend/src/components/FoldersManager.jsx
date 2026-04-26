/**
 * FoldersManager — registered ingest folders panel embedded above the
 * existing Mailboxes / ImportStatus controls.
 *
 * Lets users add a folder via the FolderPicker modal, see what's currently
 * registered, and unregister one. Removing here doesn't delete already-
 * imported emails — the next ingest just won't scan that path.
 */
import { useState, useEffect } from 'react'
import { FolderPlus, FolderOpen, Trash2, AlertCircle, CheckCircle2, Folder } from 'lucide-react'
import { api } from '../api/client'
import FolderPicker from './FolderPicker'

export default function FoldersManager() {
  const [folders, setFolders] = useState(null)
  const [showPicker, setShowPicker] = useState(false)
  const [error, setError] = useState(null)
  const [adding, setAdding] = useState(false)

  const load = async () => {
    try {
      const result = await api.listIngestFolders()
      setFolders(result.folders || [])
    } catch (err) {
      console.error(err)
      setFolders([])
    }
  }

  useEffect(() => { load() }, [])

  const handlePick = async (host_path) => {
    if (!host_path) return
    setAdding(true)
    setError(null)
    try {
      await api.addIngestFolder(host_path)
      setShowPicker(false)
      load()
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setAdding(false)
    }
  }

  const handleRemove = async (id) => {
    try {
      await api.removeIngestFolder(id)
      load()
    } catch (err) {
      setError(String(err.message || err))
    }
  }

  if (folders === null) return null  // initial load

  return (
    <>
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 space-y-3">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <FolderOpen className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            <span className="text-sm font-medium text-gray-800 dark:text-gray-200">
              Mailbox folders
            </span>
            <span className="text-xs text-gray-400">
              ({folders.length} added · scanned on every import)
            </span>
          </div>
          <button onClick={() => { setError(null); setShowPicker(true) }}
            disabled={adding}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
            <FolderPlus className="w-3.5 h-3.5" />
            {adding ? 'Adding…' : 'Add folder'}
          </button>
        </div>

        {error && (
          <div className="flex items-start gap-2 px-3 py-2 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700/50 rounded-lg text-xs text-red-700 dark:text-red-300">
            <AlertCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">{error}</div>
            <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600 flex-shrink-0">×</button>
          </div>
        )}

        {folders.length === 0 ? (
          <div className="text-center py-6">
            <Folder className="w-8 h-8 text-gray-300 dark:text-gray-700 mx-auto mb-2" />
            <p className="text-sm text-gray-500 dark:text-gray-400">No additional folders registered.</p>
            <p className="text-[11px] text-gray-400 mt-0.5">
              QuackBox is also scanning the legacy <code className="font-mono">DATA_PATH</code> mount.
              Click <strong>Add folder</strong> to include another location from your filesystem.
            </p>
          </div>
        ) : (
          <div className="space-y-1.5">
            {folders.map(f => (
              <div key={f.id}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg border ${
                  f.accessible
                    ? 'border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/30'
                    : 'border-amber-200 dark:border-amber-700/50 bg-amber-50/50 dark:bg-amber-900/20'
                }`}>
                {f.accessible
                  ? <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />
                  : <AlertCircle className="w-4 h-4 text-amber-500 flex-shrink-0" />}
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
                    {f.label}
                  </div>
                  <div className="text-[11px] text-gray-400 font-mono truncate" title={f.host_path}>
                    {f.host_path}
                  </div>
                  {!f.accessible && (
                    <div className="text-[11px] text-amber-700 dark:text-amber-300 mt-0.5">
                      Not currently readable — drive may be unmounted. Skipped during ingest.
                    </div>
                  )}
                </div>
                <button onClick={() => handleRemove(f.id)}
                  title="Stop scanning this folder (already-imported emails stay)"
                  className="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/30 text-gray-300 dark:text-gray-600 hover:text-red-500 transition-colors flex-shrink-0">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {showPicker && (
        <FolderPicker
          onPick={handlePick}
          onClose={() => setShowPicker(false)}
        />
      )}
    </>
  )
}
