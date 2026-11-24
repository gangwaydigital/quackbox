import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Briefcase, Plus } from 'lucide-react'
import { api } from '../api/client'
import HelpLink from './HelpLink'

const input = 'w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-white'

export default function Cases() {
  const navigate = useNavigate()
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [form, setForm] = useState({ name: '', issue: '', date_from: '', date_to: '' })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.getCases().then(setCases).catch(e => setError(e.message)).finally(() => setLoading(false))
  }, [])

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))

  const create = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const { id } = await api.createCase({
        name: form.name.trim(), issue: form.issue.trim(),
        date_from: form.date_from || null, date_to: form.date_to || null,
      })
      navigate(`/case/${id}`)
    } catch (err) {
      setError(err.message)
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
        <Briefcase className="w-5 h-5 text-blue-600" />
        Cases
        <HelpLink section="cases" />
      </h2>
      {error && <div className="text-sm text-red-600 dark:text-red-400">{error}</div>}

      <form onSubmit={create} className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 space-y-3">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-1.5"><Plus className="w-4 h-4" />New case</h3>
        <input className={input} placeholder="Name" value={form.name} onChange={set('name')} required />
        <textarea className={input} rows={3} placeholder="Describe the issue to research" value={form.issue} onChange={set('issue')} required />
        <div className="flex gap-3 flex-wrap">
          <label className="text-xs text-gray-500 dark:text-gray-400">From
            <input type="date" className={`${input} mt-1`} value={form.date_from} onChange={set('date_from')} />
          </label>
          <label className="text-xs text-gray-500 dark:text-gray-400">To
            <input type="date" className={`${input} mt-1`} value={form.date_to} onChange={set('date_to')} />
          </label>
        </div>
        <button disabled={saving || !form.name.trim() || !form.issue.trim()}
          className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">
          {saving ? 'Creating…' : 'Create case'}
        </button>
      </form>

      {loading ? <div className="text-sm text-gray-500">Loading…</div> : cases.length === 0 ? (
        <div className="text-sm text-gray-500">No cases yet.</div>
      ) : (
        <div className="grid gap-3">
          {cases.map(c => (
            <Link key={c.id} to={`/case/${c.id}`}
              className="block bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 hover:border-blue-500">
              <div className="font-medium text-gray-900 dark:text-white">{c.name}</div>
              <div className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2">{c.issue}</div>
              <div className="text-xs text-gray-500 mt-2">
                {c.candidate_count} candidates · {c.evidence_count} evidence
                {(c.date_from || c.date_to) && ` · ${c.date_from || '…'} to ${c.date_to || '…'}`}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
