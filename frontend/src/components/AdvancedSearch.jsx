import { useState, useEffect, useRef, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Search, Calendar, User, Paperclip, X, Bookmark } from 'lucide-react'
import { api } from '../api/client'
import SavedSearches from './SavedSearches'
import EmailPane from './EmailPane'

export default function AdvancedSearch() {
  const [query, setQuery]       = useState('')
  const [sender, setSender]     = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo]     = useState('')
  const [hasAttach, setHasAttach] = useState(false)
  const [results, setResults]   = useState(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const [page, setPage]         = useState(1)
  const [activeSavedId, setActiveSavedId] = useState(null)
  const [selectedId, setSelectedId]       = useState(null)
  const timerRef = useRef(null)

  const hasFilters = query.trim() || sender.trim() || dateFrom || dateTo || hasAttach

  const doSearch = useCallback(async (p = 1) => {
    const params = { page: p, page_size: 50 }
    if (query.trim())  params.q = query.trim()
    if (sender.trim()) params.sender = sender.trim()
    if (dateFrom)      params.date_from = dateFrom
    if (dateTo)        params.date_to = dateTo
    if (hasAttach)     params.has_attachments = true

    if (!params.q && !params.sender && !params.date_from && !params.date_to && !params.has_attachments) {
      setResults(null)
      return
    }
    setLoading(true); setError(null)
    try {
      const data = await api.advancedSearch(params)
      setResults(data); setPage(p)
    } catch (err) {
      setError(String(err.message || err))
    } finally { setLoading(false) }
  }, [query, sender, dateFrom, dateTo, hasAttach])

  useEffect(() => {
    clearTimeout(timerRef.current)
    if (!hasFilters) { setResults(null); return }
    timerRef.current = setTimeout(() => doSearch(1), 350)
    return () => clearTimeout(timerRef.current)
  }, [query, sender, dateFrom, dateTo, hasAttach, doSearch])

  const clear = () => {
    setQuery(''); setSender(''); setDateFrom(''); setDateTo('')
    setHasAttach(false); setResults(null); setError(null)
    setActiveSavedId(null); setSelectedId(null)
  }

  // Load a saved search into the filter fields
  const runSavedSearch = (s) => {
    setQuery(s.query || '')
    setSender(s.sender || '')
    setDateFrom(s.date_from || '')
    setDateTo(s.date_to || '')
    setHasAttach(!!s.has_attachments)
    setActiveSavedId(s.id)
    setSelectedId(null)
  }

  // If the URL is /search?saved=<id>, load that saved search on mount/change.
  // Lets the sidebar smart folders link directly to a configured search.
  const [searchParams] = useSearchParams()
  const savedFromUrl = searchParams.get('saved')
  useEffect(() => {
    if (!savedFromUrl) return
    const id = Number(savedFromUrl)
    if (!id || activeSavedId === id) return
    api.getSavedSearches().then(d => {
      const match = (d.searches || []).find(s => s.id === id)
      if (match) {
        runSavedSearch(match)
        api.recordSavedSearchRun(id).catch(() => {})
      }
    }).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [savedFromUrl])

  const currentFilters = { query, sender, dateFrom, dateTo, hasAttach }

  return (
    <div className="flex gap-6">
      {/* ── Saved searches sidebar ─────────────────────────────────────── */}
      <div className="w-48 lg:w-56 flex-shrink-0 hidden sm:block">
        <div className="sticky top-4 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-3">
          <SavedSearches
            onRun={runSavedSearch}
            activeId={activeSavedId}
            currentFilters={currentFilters} />
        </div>
      </div>

      {/* ── Main search area ───────────────────────────────────────────── */}
      <div className="flex-1 min-w-0 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Search className="w-5 h-5 text-blue-600" /> Advanced Search
          </h2>
          {/* Save current search shortcut on mobile */}
          <div className="sm:hidden">
            <SavedSearches
              onRun={runSavedSearch}
              activeId={activeSavedId}
              currentFilters={currentFilters} />
          </div>
        </div>

        {/* Filter fields */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-4 space-y-3">
          <div className="text-[10px] text-gray-400">
            Results update as you type · AND, OR, NOT · "quoted phrases" · prefix* matching
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-gray-500 mb-1 flex items-center gap-1">
                <Search className="w-3 h-3" /> Keywords
              </label>
              <input value={query} onChange={e => setQuery(e.target.value)}
                placeholder='e.g. budget AND review'
                className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-white" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 flex items-center gap-1">
                <User className="w-3 h-3" /> Sender
              </label>
              <input value={sender} onChange={e => setSender(e.target.value)}
                placeholder='Name or email'
                className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-white" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 flex items-center gap-1">
                <Calendar className="w-3 h-3" /> From
              </label>
              <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-white" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 flex items-center gap-1">
                <Calendar className="w-3 h-3" /> To
              </label>
              <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-white" />
            </div>
            <div className="flex items-end gap-2 flex-wrap">
              <label className="flex items-center gap-1.5 text-xs cursor-pointer px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800">
                <input type="checkbox" checked={hasAttach} onChange={e => setHasAttach(e.target.checked)} className="rounded" />
                <Paperclip className="w-3 h-3" /> Attachments
              </label>
              {hasFilters && (
                <button onClick={clear}
                  className="flex items-center gap-1 px-3 py-2 text-xs text-gray-500 hover:text-gray-700 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800">
                  <X className="w-3 h-3" /> Clear
                </button>
              )}
            </div>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 dark:bg-red-900/40 border border-red-200 dark:border-red-800 rounded-lg p-3 text-sm text-red-700 dark:text-red-300">{error}</div>
        )}

        {loading && (
          <div className="text-center py-4 text-sm text-gray-400">Searching…</div>
        )}

        {/* Results with inline reading pane */}
        {results && !loading && (
          <div className="flex gap-4">
            {/* Result list */}
            <div className={selectedId ? 'w-72 flex-shrink-0' : 'flex-1'}>
              <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2 border-b border-gray-100 dark:border-gray-800">
                  <span className="text-xs text-gray-500">{(results.total || 0).toLocaleString()} results</span>
                  <span className="text-xs text-gray-400">Page {results.page || 1} of {results.total_pages || 1}</span>
                </div>
                {!results.items?.length ? (
                  <div className="p-8 text-center text-gray-400 text-sm">No results found.</div>
                ) : (
                  <div className="divide-y divide-gray-100 dark:divide-gray-800">
                    {results.items.map(e => {
                      const isActive = String(e.id) === String(selectedId)
                      return (
                        <button key={e.id}
                          onClick={() => setSelectedId(prev => String(prev) === String(e.id) ? null : String(e.id))}
                          className={`w-full text-left flex items-center gap-3 px-4 py-2.5 transition-colors border-l-2 ${
                            isActive
                              ? 'bg-blue-50 dark:bg-blue-900/30 border-blue-500'
                              : 'hover:bg-gray-50 dark:hover:bg-gray-800 border-transparent'
                          }`}>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-gray-800 dark:text-gray-100 truncate">
                              {e.highlight_subject
                                ? <span dangerouslySetInnerHTML={{ __html: e.highlight_subject }} />
                                : (e.subject || '(no subject)')}
                            </div>
                            <div className="text-xs text-gray-400 truncate">
                              {e.sender_name || e.sender_email}
                              {e.date_sent ? ' · ' + new Date(e.date_sent).toLocaleDateString() : ''}
                              {e.mbox_source ? ' · ' + e.mbox_source : ''}
                            </div>
                            {e.highlight_body && (
                              <div className="text-xs text-gray-400 mt-0.5 truncate search-preview-hl"
                                dangerouslySetInnerHTML={{ __html: e.highlight_body }} />
                            )}
                          </div>
                          {e.has_attachments && <Paperclip className="w-3 h-3 text-gray-300 dark:text-gray-600 flex-shrink-0" />}
                        </button>
                      )
                    })}
                  </div>
                )}
                {(results.total_pages || 1) > 1 && (
                  <div className="flex justify-between px-4 py-2 border-t border-gray-100 dark:border-gray-800">
                    <button onClick={() => doSearch(page - 1)} disabled={page <= 1}
                      className="px-3 py-1 rounded border text-sm text-gray-500 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800 dark:border-gray-700">Prev</button>
                    <button onClick={() => doSearch(page + 1)} disabled={page >= (results.total_pages || 1)}
                      className="px-3 py-1 rounded border text-sm text-gray-500 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800 dark:border-gray-700">Next</button>
                  </div>
                )}
              </div>
            </div>

            {/* Inline reading pane */}
            {selectedId && (
              <div className="flex-1 min-w-0 border border-gray-100 dark:border-gray-800 rounded-xl bg-white dark:bg-gray-950 overflow-y-auto"
                style={{ maxHeight: 'calc(100vh - 200px)' }}>
                <EmailPane emailId={selectedId} onClose={() => setSelectedId(null)} compact />
              </div>
            )}
          </div>
        )}

        {!results && !error && !loading && (
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-12 text-center">
            <Search className="w-10 h-10 text-gray-200 mx-auto mb-3" />
            <p className="text-sm text-gray-400">Start typing to search your archive.</p>
            <p className="text-xs text-gray-300 mt-1">Or pick a saved search from the sidebar.</p>
          </div>
        )}
      </div>
    </div>
  )
}
