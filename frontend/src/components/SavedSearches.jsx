/**
 * SavedSearches — sidebar panel showing saved search smart folders.
 *
 * Props:
 *   onRun(search)   — called when user clicks a saved search to run it
 *   activeId        — id of the currently active saved search (for highlight)
 *   currentFilters  — {query, sender, dateFrom, dateTo, hasAttach} from parent
 *   onSave(name)    — called when user saves the current filters
 */
import { useState, useEffect } from 'react'
import { Bookmark, Plus, Trash2, X, Check, Search } from 'lucide-react'
import { api } from '../api/client'

const COLORS = [
  '#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b',
  '#10b981', '#6366f1', '#ef4444', '#14b8a6',
]

function describeSearch(s) {
  const parts = []
  if (s.query)          parts.push(`"${s.query}"`)
  if (s.sender)         parts.push(`from: ${s.sender}`)
  if (s.date_from)      parts.push(`after ${s.date_from}`)
  if (s.date_to)        parts.push(`before ${s.date_to}`)
  if (s.has_attachments) parts.push('has attachments')
  if (s.mbox_source)    parts.push(`in ${s.mbox_source}`)
  return parts.join(' · ') || 'All emails'
}

function SaveRow({ search, isActive, onRun, onDelete }) {
  const [confirmDelete, setConfirmDelete] = useState(false)

  return (
    <div className={`group flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer transition-colors ${
      isActive ? 'bg-blue-50 dark:bg-blue-900/30' : 'hover:bg-gray-50 dark:hover:bg-gray-800'
    }`}
      onClick={() => onRun(search)}>
      {/* Color dot */}
      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: search.color }} />

      <div className="flex-1 min-w-0">
        <div className={`text-sm truncate font-medium ${isActive ? 'text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-300'}`}>
          {search.name}
        </div>
        <div className="text-[10px] text-gray-400 truncate">{describeSearch(search)}</div>
      </div>

      {search.run_count > 0 && (
        <span className="text-[10px] text-gray-300 flex-shrink-0 hidden group-hover:hidden">
          {search.run_count}×
        </span>
      )}

      {/* Delete */}
      <button
        onClick={e => { e.stopPropagation(); setConfirmDelete(true) }}
        className="flex-shrink-0 opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-red-50 hover:text-red-500 text-gray-300 transition-all"
        title="Delete saved search">
        {confirmDelete
          ? <Check className="w-3.5 h-3.5 text-red-500" onClick={e => { e.stopPropagation(); onDelete(search.id); setConfirmDelete(false) }} />
          : <Trash2 className="w-3.5 h-3.5" />
        }
      </button>
    </div>
  )
}

function SaveDialog({ currentFilters, onSave, onCancel }) {
  const [name, setName]   = useState('')
  const [color, setColor] = useState(COLORS[0])

  const hasFilters = currentFilters?.query || currentFilters?.sender ||
                     currentFilters?.dateFrom || currentFilters?.dateTo ||
                     currentFilters?.hasAttach

  return (
    <div className="border border-blue-200 bg-blue-50 dark:bg-blue-950/30 dark:border-blue-800 rounded-xl p-3 space-y-2.5">
      <div className="text-xs font-semibold text-blue-700 dark:text-blue-300 flex items-center gap-1.5">
        <Bookmark className="w-3.5 h-3.5" /> Save current search
      </div>

      {!hasFilters && (
        <p className="text-xs text-amber-600">No active filters to save yet.</p>
      )}

      <input
        autoFocus
        value={name}
        onChange={e => setName(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && name.trim() && hasFilters && onSave(name.trim(), color)}
        placeholder="Name this search…"
        className="w-full px-2.5 py-1.5 text-sm border border-blue-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white dark:bg-gray-900 dark:text-white dark:border-blue-700"
      />

      {/* Color picker */}
      <div className="flex gap-1.5">
        {COLORS.map(c => (
          <button key={c} onClick={() => setColor(c)}
            className={`w-5 h-5 rounded-full transition-transform ${color === c ? 'scale-125 ring-2 ring-offset-1 ring-gray-400' : 'hover:scale-110'}`}
            style={{ backgroundColor: c }} />
        ))}
      </div>

      <div className="flex gap-2">
        <button
          disabled={!name.trim() || !hasFilters}
          onClick={() => onSave(name.trim(), color)}
          className="flex-1 py-1.5 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700 disabled:opacity-40 transition-colors">
          Save
        </button>
        <button onClick={onCancel}
          className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
          <X className="w-3 h-3" />
        </button>
      </div>
    </div>
  )
}

export default function SavedSearches({ onRun, activeId, currentFilters }) {
  const [searches, setSearches] = useState([])
  const [showSave, setShowSave]  = useState(false)

  const load = () => {
    api.getSavedSearches()
      .then(d => setSearches(d.searches || []))
      .catch(console.error)
  }

  useEffect(() => { load() }, [])

  const handleSave = async (name, color) => {
    await api.createSavedSearch({
      name,
      color,
      query:           currentFilters?.query || null,
      sender:          currentFilters?.sender || null,
      date_from:       currentFilters?.dateFrom || null,
      date_to:         currentFilters?.dateTo || null,
      has_attachments: !!currentFilters?.hasAttach,
      mbox_source:     currentFilters?.mboxSource || null,
    })
    setShowSave(false)
    load()
  }

  const handleDelete = async (id) => {
    await api.deleteSavedSearch(id)
    load()
  }

  const handleRun = async (search) => {
    api.recordSavedSearchRun(search.id).catch(() => {})
    onRun(search)
  }

  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between px-1">
        <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide flex items-center gap-1.5">
          <Bookmark className="w-3 h-3" /> Saved
        </span>
        <button
          onClick={() => setShowSave(s => !s)}
          className="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 hover:text-blue-600 transition-colors"
          title="Save current search">
          <Plus className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Save dialog */}
      {showSave && (
        <SaveDialog
          currentFilters={currentFilters}
          onSave={handleSave}
          onCancel={() => setShowSave(false)}
        />
      )}

      {/* List */}
      {searches.length === 0 && !showSave ? (
        <div className="px-2 py-3 text-center">
          <Search className="w-5 h-5 text-gray-200 mx-auto mb-1" />
          <p className="text-xs text-gray-400">No saved searches yet.</p>
          <p className="text-[10px] text-gray-300 mt-0.5">Run a search, then click + to save it.</p>
        </div>
      ) : (
        <div className="space-y-0.5">
          {searches.map(s => (
            <SaveRow
              key={s.id}
              search={s}
              isActive={activeId === s.id}
              onRun={handleRun}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}
    </div>
  )
}
