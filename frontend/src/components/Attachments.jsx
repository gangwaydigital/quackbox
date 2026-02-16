import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Paperclip, Search, FileText, Image, Film, Music, Archive, File, Code } from 'lucide-react'
import { api } from '../api/client'

const EXT_ICONS = {
  pdf: FileText, doc: FileText, docx: FileText, txt: FileText, rtf: FileText, xls: FileText, xlsx: FileText, csv: FileText, ppt: FileText, pptx: FileText,
  jpg: Image, jpeg: Image, png: Image, gif: Image, bmp: Image, tiff: Image, svg: Image, webp: Image, heic: Image,
  mp4: Film, mov: Film, avi: Film, mkv: Film, wmv: Film, m4v: Film,
  mp3: Music, wav: Music, aac: Music, flac: Music, m4a: Music,
  zip: Archive, rar: Archive, gz: Archive, tar: Archive, '7z': Archive, dmg: Archive,
  js: Code, py: Code, html: Code, css: Code, json: Code, xml: Code, sh: Code,
}
const getIcon = (ext) => EXT_ICONS[ext] || File

const EXT_COLORS = {
  pdf: '#ef4444', doc: '#2563eb', docx: '#2563eb', xls: '#16a34a', xlsx: '#16a34a', ppt: '#ea580c', pptx: '#ea580c',
  jpg: '#8b5cf6', jpeg: '#8b5cf6', png: '#8b5cf6', gif: '#8b5cf6',
  mp4: '#ec4899', mov: '#ec4899', mp3: '#f59e0b', zip: '#6366f1',
}
const getColor = (ext) => EXT_COLORS[ext] || '#6b7280'

export default function AttachmentIndex() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [sortBy, setSortBy] = useState('date')
  const [page, setPage] = useState(1)

  const load = async (p = 1) => {
    setLoading(true)
    try {
      const result = await api.getAttachments({ search: search || undefined, sort_by: sortBy, page: p, page_size: 50 })
      setData(result)
      setPage(p)
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  useEffect(() => { load(1) }, [sortBy])
  useEffect(() => { const t = setTimeout(() => load(1), 300); return () => clearTimeout(t) }, [search])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Paperclip className="w-5 h-5 text-blue-600" /> Attachments
          {data && <span className="text-sm font-normal text-gray-400">({data.total.toLocaleString()})</span>}
        </h2>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
            <input type="text" value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Search filenames..." className="pl-8 pr-3 py-1.5 text-xs border border-gray-200 rounded-lg w-48 focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <select value={sortBy} onChange={e => setSortBy(e.target.value)} className="text-xs border border-gray-200 rounded-lg px-2 py-1.5">
            <option value="date">By Date</option>
            <option value="name">By Name</option>
            <option value="type">By Type</option>
          </select>
        </div>
      </div>

      {/* Extension summary */}
      {data?.top_extensions?.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {data.top_extensions.slice(0, 12).map(({ ext, count }) => {
            const Icon = getIcon(ext)
            return (
              <button key={ext} onClick={() => setSearch(`.${ext}`)}
                className="inline-flex items-center gap-1 px-2.5 py-1 bg-white border border-gray-200 rounded-lg text-xs hover:border-blue-300 transition-colors">
                <Icon className="w-3 h-3" style={{ color: getColor(ext) }} />
                <span className="font-medium text-gray-700">.{ext}</span>
                <span className="text-gray-400">{count}</span>
              </button>
            )
          })}
        </div>
      )}

      {/* Attachment list */}
      <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
        {loading ? (
          <div className="p-4 space-y-2">{Array.from({length:8},(_,i)=><div key={i} className="skeleton h-12 rounded-lg" />)}</div>
        ) : !data?.items?.length ? (
          <div className="p-8 text-center text-gray-400">No attachments found</div>
        ) : data.items.map((a, i) => {
          const Icon = getIcon(a.extension)
          return (
            <Link key={`${a.email_id}-${i}`} to={`/email/${a.email_id}`}
              className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 transition-colors">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{ backgroundColor: getColor(a.extension) + '18' }}>
                <Icon className="w-4 h-4" style={{ color: getColor(a.extension) }} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-800 truncate">{a.filename}</div>
                <div className="text-xs text-gray-400 truncate">{a.subject || '(no subject)'} — {a.sender_name || a.sender_email}</div>
              </div>
              <div className="text-xs text-gray-400 flex-shrink-0 text-right">
                <div>{a.date_sent ? new Date(a.date_sent).toLocaleDateString() : ''}</div>
                {a.extension && <div className="text-[10px] uppercase font-medium" style={{ color: getColor(a.extension) }}>{a.extension}</div>}
              </div>
            </Link>
          )
        })}
      </div>

      {data && data.total_pages > 1 && (
        <div className="flex items-center justify-between text-sm text-gray-500">
          <span>Page {data.page} of {data.total_pages}</span>
          <div className="flex gap-2">
            <button onClick={() => load(page - 1)} disabled={page <= 1} className="px-3 py-1 rounded border disabled:opacity-40 hover:bg-gray-50">Prev</button>
            <button onClick={() => load(page + 1)} disabled={page >= data.total_pages} className="px-3 py-1 rounded border disabled:opacity-40 hover:bg-gray-50">Next</button>
          </div>
        </div>
      )}
    </div>
  )
}
