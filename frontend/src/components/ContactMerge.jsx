import { useState, useEffect } from 'react'
import { GitMerge, Check, AlertTriangle } from 'lucide-react'
import { api } from '../api/client'

export default function ContactMerge() {
  const [candidates, setCandidates] = useState(null)
  const [loading, setLoading] = useState(true)
  const [merging, setMerging] = useState(null)
  const [mergeResult, setMergeResult] = useState(null)

  useEffect(() => {
    setLoading(true)
    api.getMergeCandidates().then(d => setCandidates(d.candidates || []))
      .catch(console.error).finally(() => setLoading(false))
  }, [])

  const handleMerge = async (group) => {
    const primary = group.contacts.reduce((a, b) => a.count > b.count ? a : b)
    const secondary = group.contacts.filter(c => c.email !== primary.email).map(c => c.email)
    if (!confirm(`Merge ${secondary.length} contact(s) into ${primary.email}?\n\nThis will update all emails from the secondary addresses to show under the primary contact. This cannot be undone.`)) return
    setMerging(group.match_key)
    try {
      const result = await api.mergeContacts(primary.email, secondary)
      setMergeResult({ key: group.match_key, ...result })
      setCandidates(prev => prev.filter(c => c.match_key !== group.match_key))
    } catch (err) {
      setMergeResult({ key: group.match_key, error: err.message })
    } finally { setMerging(null) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <GitMerge className="w-5 h-5 text-blue-600" /> Contact Merge
          {candidates && <span className="text-sm font-normal text-gray-400">({candidates.length} groups found)</span>}
        </h2>
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm text-amber-700 flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
        Merging contacts modifies the database. The most-emailed address becomes the primary. This action cannot be undone.
      </div>

      {mergeResult && (
        <div className={`rounded-xl p-3 text-sm flex items-start gap-2 ${mergeResult.error ? 'bg-red-50 border-red-200 text-red-700' : 'bg-green-50 border-green-200 text-green-700'} border`}>
          <Check className="w-4 h-4 flex-shrink-0 mt-0.5" />
          {mergeResult.error || `Merged ${mergeResult.merged?.length} contacts into ${mergeResult.primary}. ${mergeResult.updated_records} records updated.`}
        </div>
      )}

      {loading ? (
        <div className="space-y-3">{Array.from({length:4},(_,i)=><div key={i} className="skeleton h-20 rounded-xl" />)}</div>
      ) : !candidates?.length ? (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400">No merge candidates found. Your contacts look clean!</div>
      ) : (
        <div className="space-y-3">{candidates.slice(0, 30).map(group => (
          <div key={group.match_key} className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs text-gray-400">
                Matched by <span className="font-medium">{group.match_type === 'name' ? 'name' : 'email pattern'}</span>:
                <span className="ml-1 text-gray-500">{group.match_key}</span>
              </div>
              <button onClick={() => handleMerge(group)} disabled={merging === group.match_key}
                className="flex items-center gap-1 px-3 py-1 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
                <GitMerge className="w-3 h-3" />{merging === group.match_key ? 'Merging...' : 'Merge'}
              </button>
            </div>
            <div className="space-y-1">{group.contacts.map(c => (
              <div key={c.email} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-gray-700">{c.name}</span>
                  <span className="text-xs text-gray-400">{c.email}</span>
                </div>
                <span className="text-xs text-gray-400">{c.count} emails</span>
              </div>
            ))}</div>
          </div>
        ))}</div>
      )}
    </div>
  )
}
