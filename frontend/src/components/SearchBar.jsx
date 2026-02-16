import { useState, useCallback, useRef, useEffect } from 'react'
import { Search, X, Clock, Sparkles, Type } from 'lucide-react'

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
  const [showHistory, setShowHistory] = useState(false)
  const [saved, setSaved] = useState(loadSaved)
  const timerRef = useRef(null)
  const wrapRef = useRef(null)

  // Close history on outside click
  useEffect(() => {
    const handler = (e) => { if (wrapRef.current && !wrapRef.current.contains(e.target)) setShowHistory(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const doSearch = useCallback((query) => {
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => { onSearch(query) }, 300)
  }, [onSearch])

  const handleChange = (e) => { setValue(e.target.value); doSearch(e.target.value) }
  const handleClear = () => { setValue(''); onSearch(''); setShowHistory(false) }
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && value.trim()) { saveTerm(value.trim()); setSaved(loadSaved()); setShowHistory(false) }
  }
  const pickSaved = (q) => { setValue(q); onSearch(q); setShowHistory(false) }
  const clearSaved = () => { localStorage.removeItem(SAVED_KEY); setSaved([]) }

  return (
    <div ref={wrapRef} className="relative">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input type="text" value={value} onChange={handleChange} onKeyDown={handleKeyDown}
            onFocus={() => saved.length > 0 && setShowHistory(true)}
            placeholder={searchMode === 'smart' ? 'Smart search — describe what you\'re looking for...' : 'Search emails — subjects, senders, body text...'}
            className="w-full pl-10 pr-10 py-3 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
          {value && <button onClick={handleClear} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"><X className="w-4 h-4" /></button>}
        </div>
        {onModeChange && (
          <button onClick={() => onModeChange(searchMode === 'keyword' ? 'smart' : 'keyword')}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium border transition-colors ${searchMode === 'smart' ? 'bg-purple-50 border-purple-200 text-purple-700' : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'}`}
            title={searchMode === 'smart' ? 'Using AI-powered semantic search' : 'Using keyword search'}>
            {searchMode === 'smart' ? <><Sparkles className="w-3.5 h-3.5" />Smart</> : <><Type className="w-3.5 h-3.5" />Keyword</>}
          </button>
        )}
      </div>
      {/* Saved searches dropdown */}
      {showHistory && saved.length > 0 && (
        <div className="absolute z-20 top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden">
          <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100">
            <span className="text-xs text-gray-400 flex items-center gap-1"><Clock className="w-3 h-3" />Recent searches</span>
            <button onClick={clearSaved} className="text-xs text-gray-400 hover:text-red-500">Clear all</button>
          </div>
          {saved.map((q, i) => (
            <button key={i} onClick={() => pickSaved(q)}
              className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2">
              <Clock className="w-3 h-3 text-gray-300" />{q}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
