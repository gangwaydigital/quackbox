/**
 * FolderPicker — modal directory browser for selecting a mailbox folder.
 *
 * The browser lives in a Docker container and can only see paths that have
 * been bind-mounted under /host. The backend's /api/folders/browse endpoint
 * returns only paths reachable through those mounts, so the user can't
 * navigate above what's been exposed.
 *
 * Props:
 *   onPick(host_path)  — called when user clicks "Use this folder"
 *   onClose()          — close without picking
 *   initialPath        — optional starting directory (default: roots)
 */
import { useState, useEffect, useRef } from 'react'
import { Folder, FolderOpen, ChevronRight, ChevronLeft, Home, X, AlertCircle, Inbox, Mail } from 'lucide-react'
import { api } from '../api/client'

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'

function ArtifactBadges({ artifacts }) {
  if (!artifacts) return null
  const { mbox_files, emlx_files, looks_like_mailbox } = artifacts
  if (!mbox_files && !emlx_files && !looks_like_mailbox) return null
  return (
    <div className="flex items-center gap-1.5 flex-shrink-0">
      {mbox_files > 0 && (
        <span className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 bg-blue-50 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 rounded">
          <Mail className="w-2.5 h-2.5" /> {mbox_files} mbox
        </span>
      )}
      {emlx_files > 0 && (
        <span className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 bg-purple-50 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 rounded">
          <Inbox className="w-2.5 h-2.5" /> {emlx_files.toLocaleString()} emlx
        </span>
      )}
      {looks_like_mailbox && (
        <span className="text-[10px] px-1.5 py-0.5 bg-amber-50 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 rounded">
          mail bundle
        </span>
      )}
    </div>
  )
}

export default function FolderPicker({ onPick, onClose, initialPath = null }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const dialogRef = useRef(null)
  const previousFocusRef = useRef(null)

  const load = async (path) => {
    setLoading(true); setError(null)
    try {
      const result = await api.browseFolders(path)
      setData(result)
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(initialPath) }, [])

  // A11y: focus trap, Escape to close, focus restoration
  useEffect(() => {
    previousFocusRef.current = document.activeElement
    const first = dialogRef.current?.querySelector(FOCUSABLE)
    first?.focus()

    const onKey = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); onClose(); return }
      if (e.key !== 'Tab' || !dialogRef.current) return
      const items = dialogRef.current.querySelectorAll(FOCUSABLE)
      if (!items.length) return
      const first = items[0], last = items[items.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault(); last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault(); first.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
      previousFocusRef.current?.focus?.()
    }
  }, [onClose])

  const currentPath = data?.path
  const canPick = !!currentPath  // can only pick once you've navigated into something
  const dirs = (data?.entries || []).filter(e => e.is_dir)
  const files = (data?.entries || []).filter(e => !e.is_dir)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.5)' }}
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div ref={dialogRef}
        role="dialog" aria-modal="true" aria-labelledby="folder-picker-title"
        className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-gray-100 dark:border-gray-800">
          <FolderOpen className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <div id="folder-picker-title" className="font-semibold text-gray-900 dark:text-white text-sm">Pick a mailbox folder</div>
            <div className="text-xs text-gray-400 mt-0.5 font-mono truncate" title={currentPath || ''}>
              {currentPath || 'Choose a starting location'}
            </div>
          </div>
          <button onClick={onClose} aria-label="Close folder picker"
            className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors text-gray-400 flex-shrink-0">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Breadcrumb / nav row */}
        <div className="flex items-center gap-2 px-5 py-2 border-b border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/30 text-xs">
          <button onClick={() => load(null)}
            className="inline-flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-200 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-300"
            title="Top-level mounted roots">
            <Home className="w-3 h-3" /> Roots
          </button>
          {data?.parent !== null && data?.parent !== undefined && (
            <button onClick={() => load(data.parent)}
              className="inline-flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-200 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-300">
              <ChevronLeft className="w-3 h-3" /> Up
            </button>
          )}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="p-8 text-center text-sm text-gray-400">Loading…</div>
          ) : error ? (
            <div className="p-5 flex items-start gap-2 text-sm text-red-700 dark:text-red-300">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <div>{error}</div>
            </div>
          ) : data?.entries?.length === 0 ? (
            <div className="p-8 text-center text-sm text-gray-400">Empty folder.</div>
          ) : (
            <div className="divide-y divide-gray-100 dark:divide-gray-800">
              {dirs.map(entry => (
                <button key={entry.host_path}
                  onClick={() => load(entry.host_path)}
                  className="w-full flex items-center gap-3 px-5 py-2.5 text-left hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                  <Folder className="w-4 h-4 text-blue-500 dark:text-blue-400 flex-shrink-0" />
                  <span className="flex-1 text-sm text-gray-800 dark:text-gray-200 truncate">{entry.name}</span>
                  <ArtifactBadges artifacts={entry.email_artifacts} />
                  <ChevronRight className="w-3.5 h-3.5 text-gray-300 dark:text-gray-600 flex-shrink-0" />
                </button>
              ))}
              {files.length > 0 && (
                <div className="px-5 py-2 bg-gray-50/50 dark:bg-gray-800/30 text-[10px] uppercase tracking-wider text-gray-400">
                  Files (informational — pick the parent folder to ingest)
                </div>
              )}
              {files.slice(0, 50).map(entry => (
                <div key={entry.host_path} className="flex items-center gap-3 px-5 py-1.5 text-sm text-gray-500 dark:text-gray-400">
                  <span className="w-4 flex-shrink-0" />
                  <Mail className="w-3.5 h-3.5 text-gray-300 dark:text-gray-600 flex-shrink-0" />
                  <span className="truncate">{entry.name}</span>
                </div>
              ))}
              {files.length > 50 && (
                <div className="px-5 py-1.5 text-[10px] text-gray-400">
                  … and {files.length - 50} more files
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-3 px-5 py-3 border-t border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/30">
          <div className="text-[10px] text-gray-400 truncate">
            {currentPath ? <>Will register: <code className="font-mono text-gray-600 dark:text-gray-300">{currentPath}</code></> : 'Navigate into a folder to pick it'}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <button onClick={onClose}
              className="px-3 py-1.5 text-xs text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800">
              Cancel
            </button>
            <button onClick={() => onPick(currentPath)} disabled={!canPick}
              className="px-4 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed">
              Use this folder
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
