import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  Paperclip, Search, FileText, Image, Film, Music, Archive, File, Code,
  Download, Eye, X, Loader, BookOpen, RefreshCw, AlignLeft
} from 'lucide-react'
import { api } from '../api/client'
import { OnboardingBanner } from './OnboardingTips'

const EXT_ICONS = {
  pdf: FileText, doc: FileText, docx: FileText, txt: FileText, rtf: FileText,
  xls: FileText, xlsx: FileText, csv: FileText, ppt: FileText, pptx: FileText,
  jpg: Image, jpeg: Image, png: Image, gif: Image, bmp: Image, tiff: Image,
  svg: Image, webp: Image, heic: Image,
  mp4: Film, mov: Film, avi: Film, mkv: Film, wmv: Film, m4v: Film,
  mp3: Music, wav: Music, aac: Music, flac: Music, m4a: Music,
  zip: Archive, rar: Archive, gz: Archive, tar: Archive, '7z': Archive, dmg: Archive,
  js: Code, py: Code, html: Code, css: Code, json: Code, xml: Code, sh: Code,
}
const getIcon = (ext) => EXT_ICONS[ext] || File

const EXT_COLORS = {
  pdf: '#ef4444', doc: '#2563eb', docx: '#2563eb', xls: '#16a34a', xlsx: '#16a34a',
  ppt: '#ea580c', pptx: '#ea580c',
  jpg: '#8b5cf6', jpeg: '#8b5cf6', png: '#8b5cf6', gif: '#8b5cf6',
  mp4: '#ec4899', mov: '#ec4899', mp3: '#f59e0b', zip: '#6366f1',
}
const getColor = (ext) => EXT_COLORS[ext] || '#6b7280'
const PREVIEWABLE = new Set(['pdf', 'doc', 'docx'])

// ── Preview Modal ──────────────────────────────────────────────────────────

function PreviewModal({ attachment, onClose }) {
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true); setError(null)
    api.getAttachmentPreview(attachment.email_id, attachment.filename)
      .then(data => { setPreview(data); setLoading(false) })
      .catch(err => { setError(String(err.message || err)); setLoading(false) })
  }, [attachment])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.5)' }}
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col overflow-hidden">
        <div className="flex items-center gap-3 px-5 py-4 border-b border-gray-100 dark:border-gray-800">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
            style={{ backgroundColor: getColor(attachment.extension) + '18' }}>
            <FileText className="w-4 h-4" style={{ color: getColor(attachment.extension) }} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-semibold text-gray-900 dark:text-white text-sm truncate">{attachment.filename}</div>
            <div className="text-xs text-gray-400 truncate">{attachment.subject}</div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <a href={api.downloadAttachmentUrl(attachment.email_id, attachment.filename)} download
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-blue-50 text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors">
              <Download className="w-3.5 h-3.5" /> Download
            </a>
            <button onClick={onClose}
              className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors text-gray-400">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-auto p-5">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-16 text-gray-400 gap-3">
              <Loader className="w-8 h-8 animate-spin text-blue-400" />
              <span className="text-sm">Extracting text…</span>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-16 text-gray-400 gap-3">
              <FileText className="w-8 h-8" />
              <p className="text-sm font-medium text-gray-600">Could not extract text</p>
              <p className="text-xs text-gray-400">{error}</p>
            </div>
          ) : preview?.extraction_status === 'unsupported' ? (
            <div className="flex flex-col items-center justify-center py-16 text-gray-400 gap-3">
              <File className="w-8 h-8" />
              <p className="text-sm text-gray-500">Preview not available for this file type.</p>
            </div>
          ) : preview?.text ? (
            <>
              <div className="flex items-center gap-4 mb-4 text-xs text-gray-400 border-b border-gray-100 pb-3">
                {preview.page_count > 0 && (
                  <span className="flex items-center gap-1">
                    <BookOpen className="w-3.5 h-3.5" /> {preview.page_count} page{preview.page_count !== 1 ? 's' : ''}
                  </span>
                )}
                {preview.word_count > 0 && (
                  <span className="flex items-center gap-1">
                    <AlignLeft className="w-3.5 h-3.5" /> {preview.word_count.toLocaleString()} words
                  </span>
                )}
              </div>
              <pre className="whitespace-pre-wrap font-sans text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                {preview.text}
              </pre>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-gray-400 gap-3">
              <FileText className="w-8 h-8" />
              <p className="text-sm text-gray-500">No text could be extracted from this file.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Content Search Tab ─────────────────────────────────────────────────────

function ContentSearch() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [indexing, setIndexing] = useState(false)

  const search = async (q = query, p = 1) => {
    if (!q.trim()) return
    setLoading(true)
    try {
      const data = await api.searchAttachmentContent(q, p)
      setResults(data); setPage(p)
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  const triggerIndex = async () => {
    setIndexing(true)
    await api.triggerAttachmentIndexing()
    setTimeout(() => setIndexing(false), 2000)
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input type="text" value={query} onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && search()}
            placeholder="Search inside PDF & DOCX attachments…"
            className="w-full pl-10 pr-4 py-2.5 text-sm border border-gray-200 dark:border-gray-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-white" />
        </div>
        <button onClick={() => search()} disabled={loading || !query.trim()}
          className="px-4 py-2.5 bg-blue-600 text-white text-sm rounded-xl hover:bg-blue-700 disabled:opacity-40 transition-colors">
          Search
        </button>
        <button onClick={triggerIndex} disabled={indexing} title="Re-index PDF/DOCX attachments"
          className="px-3 py-2.5 border border-gray-200 dark:border-gray-700 text-gray-500 text-sm rounded-xl hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-40 transition-colors">
          <RefreshCw className={`w-4 h-4 ${indexing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {indexing && (
        <div className="text-xs text-blue-600 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2">
          Indexing started — large archives may take a few minutes.
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 py-6 justify-center text-gray-400 text-sm">
          <Loader className="w-4 h-4 animate-spin" /> Searching…
        </div>
      )}

      {results && !loading && (
        <>
          <div className="text-xs text-gray-400">
            {results.total} result{results.total !== 1 ? 's' : ''} for "{query}"
          </div>
          {results.results.length === 0 ? (
            <div className="py-10 text-center text-gray-400 text-sm">No attachment content matches your query.</div>
          ) : (
            <div className="space-y-2">
              {results.results.map((r, i) => (
                <div key={i} className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <FileText className="w-4 h-4 text-red-400 flex-shrink-0" />
                        <span className="text-sm font-semibold text-gray-800 dark:text-white truncate">{r.filename}</span>
                        {r.page_count > 0 && <span className="text-xs text-gray-400">{r.page_count}p</span>}
                      </div>
                      <Link to={`/email/${r.email_id}`}
                        className="text-xs text-gray-500 hover:text-blue-600 truncate block">
                        {r.subject || '(no subject)'} — {r.sender_name || r.sender_email}
                      </Link>
                    </div>
                    <span className="text-xs text-gray-400 flex-shrink-0">{r.date_sent?.slice(0, 10)}</span>
                  </div>
                  {r.snippet && (
                    <p className="mt-2 text-xs text-gray-600 dark:text-gray-400 leading-relaxed border-l-2 border-blue-200 pl-3"
                      dangerouslySetInnerHTML={{ __html: r.snippet }} />
                  )}
                </div>
              ))}
            </div>
          )}
          {results.total_pages > 1 && (
            <div className="flex items-center justify-center gap-3">
              <button disabled={page <= 1} onClick={() => search(query, page - 1)}
                className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-gray-50">Previous</button>
              <span className="text-sm text-gray-500">{page} / {results.total_pages}</span>
              <button disabled={page >= results.total_pages} onClick={() => search(query, page + 1)}
                className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-gray-50">Next</button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ── Main Component ─────────────────────────────────────────────────────────

export default function AttachmentIndex() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [sortBy, setSortBy] = useState('date')
  const [page, setPage] = useState(1)
  const [tab, setTab] = useState('browse')
  const [previewAttachment, setPreviewAttachment] = useState(null)

  const load = async (p = 1) => {
    setLoading(true); setError(null)
    try {
      const result = await api.getAttachments({ search: search || undefined, sort_by: sortBy, page: p, page_size: 50 })
      setData(result); setPage(p)
    } catch (err) {
      setError(String(err.message || err)); setData(null)
    } finally { setLoading(false) }
  }

  useEffect(() => { load(1) }, [sortBy])
  useEffect(() => { const t = setTimeout(() => load(1), 300); return () => clearTimeout(t) }, [search])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <Paperclip className="w-5 h-5 text-blue-600" /> Attachments
          {data && tab === 'browse' && (
            <span className="text-sm font-normal text-gray-400">({(data.total || 0).toLocaleString()})</span>
          )}
        </h2>
        <div className="flex bg-gray-100 dark:bg-gray-800 rounded-lg p-0.5 gap-0.5">
          <button onClick={() => setTab('browse')}
            className={`px-3 py-1.5 text-xs rounded-md font-medium transition-colors ${tab === 'browse' ? 'bg-white dark:bg-gray-700 text-gray-800 dark:text-white shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
            Browse
          </button>
          <button onClick={() => setTab('search')}
            className={`px-3 py-1.5 text-xs rounded-md font-medium transition-colors flex items-center gap-1 ${tab === 'search' ? 'bg-white dark:bg-gray-700 text-gray-800 dark:text-white shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
            <Eye className="w-3 h-3" /> Content Search
          </button>
        </div>
      </div>

      {tab === 'search' ? (
        <>
          <OnboardingBanner id="attachment-content-search">
            Content Search lets you search <strong>inside</strong> PDF and DOCX files —
            not just by filename. QuackBox extracts text automatically after each import.
          </OnboardingBanner>
          <ContentSearch />
        </>
      ) : (
        <>
          <div className="flex items-center gap-3 flex-wrap">
            <div className="relative flex-1 min-w-[180px]">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
              <input type="text" value={search} onChange={e => setSearch(e.target.value)}
                placeholder="Search filenames…"
                className="w-full pl-8 pr-3 py-1.5 text-xs border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-white" />
            </div>
            <select value={sortBy} onChange={e => setSortBy(e.target.value)}
              className="text-xs border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1.5 dark:bg-gray-800 dark:text-white">
              <option value="date">By Date</option>
              <option value="name">By Name</option>
              <option value="type">By Type</option>
            </select>
          </div>

          {error && <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">{error}</div>}

          {data?.top_extensions?.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {data.top_extensions.slice(0, 12).map(({ ext, count }) => {
                const Icon = getIcon(ext)
                return (
                  <button key={ext} onClick={() => setSearch(`.${ext}`)}
                    className="inline-flex items-center gap-1 px-2.5 py-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-xs hover:border-blue-300 transition-colors">
                    <Icon className="w-3 h-3" style={{ color: getColor(ext) }} />
                    <span className="font-medium text-gray-700 dark:text-gray-300">.{ext}</span>
                    <span className="text-gray-400">{count}</span>
                  </button>
                )
              })}
            </div>
          )}

          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 divide-y divide-gray-100 dark:divide-gray-800">
            {loading ? (
              <div className="p-4 space-y-2">
                {Array.from({ length: 8 }, (_, i) => (
                  <div key={i} className="h-12 bg-gray-100 dark:bg-gray-800 animate-pulse rounded-lg" />
                ))}
              </div>
            ) : !data?.items?.length ? (
              <div className="p-8 text-center text-gray-400 text-sm">
                {data?.total === 0 ? 'No attachments found in your archive.' : 'No attachments match your search.'}
              </div>
            ) : data.items.map((a, i) => {
              const Icon = getIcon(a.extension)
              const canPreview = PREVIEWABLE.has(a.extension)
              return (
                <div key={`${a.email_id}-${i}`}
                  className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                    style={{ backgroundColor: getColor(a.extension) + '18' }}>
                    <Icon className="w-4 h-4" style={{ color: getColor(a.extension) }} />
                  </div>
                  <Link to={`/email/${a.email_id}`} className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate hover:text-blue-600 transition-colors">
                      {a.filename}
                    </div>
                    <div className="text-xs text-gray-400 truncate">
                      {a.subject || '(no subject)'} — {a.sender_name || a.sender_email}
                    </div>
                  </Link>
                  <div className="text-xs text-gray-400 flex-shrink-0 text-right">
                    <div>{a.date_sent ? new Date(a.date_sent).toLocaleDateString() : ''}</div>
                    {a.extension && (
                      <div className="text-[10px] uppercase font-medium" style={{ color: getColor(a.extension) }}>
                        {a.extension}
                      </div>
                    )}
                  </div>
                  {canPreview && (
                    <button onClick={() => setPreviewAttachment(a)} title={`Preview ${a.filename}`}
                      className="flex-shrink-0 p-1.5 rounded-lg hover:bg-purple-50 text-gray-400 hover:text-purple-600 transition-colors">
                      <Eye className="w-4 h-4" />
                    </button>
                  )}
                  <a href={api.downloadAttachmentUrl(a.email_id, a.filename)} download
                    className="flex-shrink-0 p-1.5 rounded-lg hover:bg-blue-50 text-gray-400 hover:text-blue-600 transition-colors"
                    title={`Download ${a.filename}`} onClick={e => e.stopPropagation()}>
                    <Download className="w-4 h-4" />
                  </a>
                </div>
              )
            })}
          </div>

          {data && (data.total_pages || 1) > 1 && (
            <div className="flex items-center justify-between text-sm text-gray-500">
              <span>Page {data.page} of {data.total_pages}</span>
              <div className="flex gap-2">
                <button onClick={() => load(page - 1)} disabled={page <= 1}
                  className="px-3 py-1 rounded border disabled:opacity-40 hover:bg-gray-50">Prev</button>
                <button onClick={() => load(page + 1)} disabled={page >= data.total_pages}
                  className="px-3 py-1 rounded border disabled:opacity-40 hover:bg-gray-50">Next</button>
              </div>
            </div>
          )}
        </>
      )}

      {previewAttachment && (
        <PreviewModal attachment={previewAttachment} onClose={() => setPreviewAttachment(null)} />
      )}
    </div>
  )
}
