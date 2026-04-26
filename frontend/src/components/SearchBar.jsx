import { useState, useCallback, useRef, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Search, X, Clock, Sparkles, Type, Paperclip, MessageSquare, ArrowRight } from 'lucide-react'
import { api } from '../api/client'

const SAVED_KEY = 'quackbox-saved-searches'
const MAX_SAVED = 15

function loadSaved() {
  try { return JSON.parse(localStorage.getItem(SAVED_KEY) || '[]') } catch { return [] }
}
function saveTerm(q) {
  if (!q.trim()) return
  const saved = loadSaved().filter(s => s !== q)
  saved.unshift(q)
  localStorage.setItem(SAVED_KEY, JSON.stringify(saved.slice(0, MAX_SAVED)))
}

export default function SearchBar({ onSearch, onModeChange, searchMode = 'keyword' }) {
  const [value, setValue] = useState('')
  const [showDropdown, setShowDropdown] = useState(false)
  const [saved, setSaved] = useState(loadSaved)
  const [preview, setPreview] = useState([])
  const [previewLoading, setPreviewLoading] = useState(false)
  const [selectedIdx, setSelectedIdx] = useState(-1)
  const timerRef = useRef(null)
  const previewTimerRef = useRef(null)
  const wrapRef = useRef(null)
  const inputRef = useRef(null)
  const navigate = useNavigate()

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => { if (wrapRef.current && !wrapRef.current.contains(e.target)) setShowDropdown(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Debounced full search (triggers email list update)
  const doSearch = useCallback((query) => {
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => { onSearch(query) }, 300)
  }, [onSearch])

  // Instant preview search (lightweight, fast)
  const doPreview = useCallback((query) => {
    clearTimeout(previewTimerRef.current)
    if (!query.trim() || query.trim().length < 2) {
      setPreview([])
      setPreviewLoading(false)
      return
    }
    setPreviewLoading(true)
    previewTimerRef.current = setTimeout(async () => {
      try {
        const data = await api.instantSearch(query.trim(), 6)
        setPreview(data.results || [])
      } catch { setPreview([]) }
      finally { setPreviewLoading(false) }
    }, 150)
  }, [])

  const handleChange = (e) => {
    const q = e.target.value
    setValue(q)
    setSelectedIdx(-1)
    doSearch(q)
    doPreview(q)
    if (q.trim()) {
      setShowDropdown(true)
    }
  }

  const handleClear = () => {
    setValue('')
    onSearch('')
    setPreview([])
    setShowDropdown(false)
    inputRef.current?.focus()
  }

  const handleFocus = () => {
    if (value.trim() && preview.length > 0) {
      setShowDropdown(true)
    } else if (!value.trim() && saved.length > 0) {
      setShowDropdown(true)
    }
  }

  const handleKeyDown = (e) => {
    const items = value.trim() ? preview : saved
    const maxIdx = items.length - 1

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIdx(prev => Math.min(prev + 1, maxIdx))
      setShowDropdown(true)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIdx(prev => Math.max(prev - 1, -1))
    } else if (e.key === 'Enter') {
      if (selectedIdx >= 0 && selectedIdx < items.length) {
        e.preventDefault()
        if (value.trim()) {
          // Navigate to selected preview result
          navigate(`/email/${items[selectedIdx].id}`)
          setShowDropdown(false)
        } else {
          // Pick saved search
          const q = items[selectedIdx]
          setValue(q)
          onSearch(q)
          doPreview(q)
          setShowDropdown(false)
        }
      } else if (value.trim()) {
        saveTerm(value.trim())
        setSaved(loadSaved())
        setShowDropdown(false)
      }
    } else if (e.key === 'Escape') {
      setShowDropdown(false)
      setSelectedIdx(-1)
    }
  }

  const pickSaved = (q) => { setValue(q); onSearch(q); doPreview(q); setShowDropdown(false) }
  const clearSaved = () => { localStorage.removeItem(SAVED_KEY); setSaved([]) }

  const showPreview = showDropdown && value.trim() && (preview.length > 0 || previewLoading)
  const showHistory = showDropdown && !value.trim() && saved.length > 0

  return (
    <div ref={wrapRef} className="relative">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input ref={inputRef} type="text" value={value} onChange={handleChange} onKeyDown={handleKeyDown}
            onFocus={handleFocus}
            placeholder={searchMode === 'smart' ? 'Smart search — describe what you\'re looking for...' : 'Search emails — subjects, senders, body text...'}
            className="w-full pl-10 pr-10 py-3 bg-white dark:bg-gray-800 dark:text-white dark:placeholder-gray-500 border border-gray-200 dark:border-gray-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
          {value && <button onClick={handleClear} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"><X className="w-4 h-4" /></button>}
        </div>
        {onModeChange && (
          <button onClick={() => onModeChange(searchMode === 'keyword' ? 'smart' : 'keyword')}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium border transition-colors ${searchMode === 'smart' ? 'bg-purple-50 dark:bg-purple-900/40 border-purple-200 dark:border-purple-800 text-purple-700 dark:text-purple-300' : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800/50'}`}
            title={searchMode === 'smart' ? 'Using AI-powered semantic search' : 'Using keyword search'}>
            {searchMode === 'smart' ? <><Sparkles className="w-3.5 h-3.5" />Smart</> : <><Type className="w-3.5 h-3.5" />Keyword</>}
          </button>
        )}
      </div>

      {/* Instant preview dropdown */}
      {showPreview && (
        <div className="absolute z-30 top-full left-0 right-0 mt-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl shadow-xl overflow-hidden">
          {previewLoading && preview.length === 0 ? (
            <div className="px-4 py-3 text-sm text-gray-400 flex items-center gap-2">
              <div className="w-3 h-3 border-2 border-gray-300 dark:border-gray-600 border-t-blue-500 rounded-full animate-spin" />
              Searching...
            </div>
          ) : (
            <>
              <div className="divide-y divide-gray-100 dark:divide-gray-800">
                {preview.map((item, i) => (
                  <Link key={item.id} to={`/email/${item.id}`}
                    onClick={() => setShowDropdown(false)}
                    className={`block px-4 py-2.5 transition-colors ${i === selectedIdx ? 'bg-blue-50 dark:bg-blue-900/40' : 'hover:bg-gray-50 dark:hover:bg-gray-800/50'}`}>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
                          {item.subject || '(no subject)'}
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-xs text-gray-500 truncate">
                            {item.sender_name || item.sender_email}
                          </span>
                          {item.date_sent && (
                            <span className="text-xs text-gray-400 flex-shrink-0">
                              {new Date(item.date_sent).toLocaleDateString()}
                            </span>
                          )}
                          {item.has_attachments && <Paperclip className="w-3 h-3 text-gray-300 dark:text-gray-600 flex-shrink-0" />}
                          {item.thread_group_id && <MessageSquare className="w-3 h-3 text-blue-400 flex-shrink-0" />}
                        </div>
                        {item.body_highlight && (
                          <div className="text-xs text-gray-400 mt-0.5 truncate search-preview-hl"
                            dangerouslySetInnerHTML={{ __html: item.body_highlight }} />
                        )}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
              {preview.length > 0 && (
                <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-100 dark:border-gray-800 flex items-center justify-between">
                  <span className="text-xs text-gray-400">
                    Press Enter to search all · ↑↓ to navigate
                  </span>
                  <span className="text-xs text-gray-400 flex items-center gap-1">
                    <ArrowRight className="w-3 h-3" /> Full results below
                  </span>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Saved searches dropdown */}
      {showHistory && (
        <div className="absolute z-30 top-full left-0 right-0 mt-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl shadow-xl overflow-hidden">
          <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100 dark:border-gray-800">
            <span className="text-xs text-gray-400 flex items-center gap-1"><Clock className="w-3 h-3" />Recent searches</span>
            <button onClick={clearSaved} className="text-xs text-gray-400 hover:text-red-500">Clear all</button>
          </div>
          {saved.map((q, i) => (
            <button key={i} onClick={() => pickSaved(q)}
              className={`w-full text-left px-3 py-2 text-sm text-gray-700 dark:text-gray-300 flex items-center gap-2 transition-colors ${i === selectedIdx ? 'bg-blue-50 dark:bg-blue-900/40' : 'hover:bg-gray-50 dark:hover:bg-gray-800/50'}`}>
              <Clock className="w-3 h-3 text-gray-300 dark:text-gray-600" />{q}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
