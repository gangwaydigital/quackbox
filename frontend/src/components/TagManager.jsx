import { useState, useEffect } from 'react'
import { Tag, Plus, Trash2 } from 'lucide-react'
import { api } from '../api/client'

const TAG_COLORS = ['#3b82f6','#8b5cf6','#ec4899','#f59e0b','#10b981','#ef4444','#6366f1','#14b8a6']

export default function TagManager() {
  const [tags, setTags] = useState([])
  const [newName, setNewName] = useState('')
  const [newColor, setNewColor] = useState(TAG_COLORS[0])
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    api.getTags().then(d => setTags(d.tags || [])).catch(console.error).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const create = async () => {
    if (!newName.trim()) return
    await api.createTag(newName.trim(), newColor)
    setNewName('')
    load()
  }

  const del = async (id, name) => {
    if (!confirm(`Delete tag "${name}"? This will untag all emails.`)) return
    await api.deleteTag(id)
    load()
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
        <Tag className="w-4 h-4 text-blue-600" /> Tags
      </h3>

      {/* Create new */}
      <div className="flex gap-2">
        <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="New tag name..."
          onKeyDown={e => e.key === 'Enter' && create()}
          className="flex-1 px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
        <div className="flex gap-1">{TAG_COLORS.map(c => (
          <button key={c} onClick={() => setNewColor(c)}
            className={`w-6 h-6 rounded-full ${newColor === c ? 'ring-2 ring-offset-1 ring-gray-400' : ''}`}
            style={{ backgroundColor: c }} />
        ))}</div>
        <button onClick={create} className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
          <Plus className="w-4 h-4" />
        </button>
      </div>

      {/* Tag list */}
      {loading ? (
        <div className="space-y-2">{Array.from({length:3},(_,i)=><div key={i} className="skeleton h-10 rounded-lg" />)}</div>
      ) : tags.length === 0 ? (
        <div className="text-sm text-gray-400 text-center py-4">No tags yet. Create one above.</div>
      ) : (
        <div className="space-y-1.5">
          {tags.map(t => (
            <div key={t.id} className="flex items-center justify-between bg-white rounded-lg border border-gray-200 px-3 py-2">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: t.color }} />
                <span className="text-sm font-medium text-gray-700">{t.name}</span>
                <span className="text-xs text-gray-400">{t.email_count} emails</span>
              </div>
              <button onClick={() => del(t.id, t.name)} className="text-gray-300 hover:text-red-500">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
