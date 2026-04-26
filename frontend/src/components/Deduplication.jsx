import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Copy, Trash2, CheckCircle, ChevronDown, ChevronRight, AlertTriangle, RefreshCw, X } from 'lucide-react'
import { api } from '../api/client'
import { OnboardingBanner } from './OnboardingTips'

const METHOD_LABELS = {
  message_id:        { label: 'Exact duplicate', color: 'bg-red-100 text-red-700 border-red-200' },
  sender_subject_date: { label: 'Same email, different source', color: 'bg-orange-100 text-orange-700 border-orange-200' },
  content_hash:      { label: 'Near-identical content', color: 'bg-yellow-100 text-yellow-700 border-yellow-200' },
}

function MethodBadge({ method }) {
  const m = METHOD_LABELS[method] || { label: method, color: 'bg-gray-100 text-gray-600 border-gray-200' }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full border ${m.color}`}>
      {m.label}
    </span>
  )
}

function EmailRow({ email, isCanonical }) {
  return (
    <div className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm ${isCanonical ? 'bg-green-50 dark:bg-green-900/40 border border-green-200 dark:border-green-800' : 'bg-gray-50 dark:bg-gray-800/50'}`}>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          {isCanonical && (
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-green-700 dark:text-green-300 bg-green-100 dark:bg-green-900/40 px-1.5 py-0.5 rounded">
              <CheckCircle className="w-2.5 h-2.5" /> KEEP
            </span>
          )}
          <Link to={`/email/${email.id}`}
            className="font-medium text-gray-800 dark:text-gray-200 hover:text-blue-600 truncate">
            {email.subject || '(no subject)'}
          </Link>
        </div>
        <div className="text-xs text-gray-400 mt-0.5 truncate">
          {email.sender_name || email.sender_email} · {email.date_sent?.slice(0, 10)} · <span className="font-mono">{email.mbox_source}</span>
        </div>
      </div>
      {!isCanonical && email.similarity_score != null && (
        <span className="text-[10px] text-gray-400 flex-shrink-0">
          {Math.round(email.similarity_score * 100)}% match
        </span>
      )}
    </div>
  )
}

function DuplicateGroup({ group, onDelete, onDismiss }) {
  const [expanded, setExpanded] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const handleDelete = async (e) => {
    e.stopPropagation()
    if (!confirm(`Delete ${group.duplicates.length} duplicate(s), keeping the original?`)) return
    setDeleting(true)
    try {
      await onDelete([group.group_id])
    } finally {
      setDeleting(false)
    }
  }

  const handleDismiss = async (e) => {
    e.stopPropagation()
    await onDismiss(group.group_id)
  }

  return (
    <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors text-left">
        <div className="flex-shrink-0 text-gray-400">
          {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-gray-800 dark:text-gray-200 truncate text-sm">
              {group.canonical.subject || '(no subject)'}
            </span>
            <MethodBadge method={group.detection_method} />
          </div>
          <div className="text-xs text-gray-400 mt-0.5">
            {group.canonical.sender_name || group.canonical.sender_email} ·{' '}
            <span className="text-red-500 font-medium">{group.duplicates.length} duplicate{group.duplicates.length !== 1 ? 's' : ''}</span>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={handleDismiss}
            title="Not duplicates — dismiss"
            className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors">
            <X className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-red-50 dark:bg-red-900/40 text-red-600 dark:text-red-300 text-xs font-medium rounded-lg hover:bg-red-100 border border-red-200 dark:border-red-800 transition-colors disabled:opacity-50">
            {deleting ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
            Delete {group.duplicates.length}
          </button>
        </div>
      </button>

      {expanded && (
        <div className="border-t border-gray-100 dark:border-gray-800 p-3 space-y-1.5 bg-gray-50/50 dark:bg-gray-800/30">
          <EmailRow email={group.canonical} isCanonical />
          {group.duplicates.map(dup => (
            <EmailRow key={dup.id} email={dup} isCanonical={false} />
          ))}
        </div>
      )}
    </div>
  )
}

export default function Deduplication() {
  const [data, setData] = useState(null)
  const [scanning, setScanning] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  const load = async (p = 1) => {
    setLoading(true)
    try {
      const result = await api.getDuplicates(p)
      setData(result)
      setPage(p)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const scan = async () => {
    setScanning(true)
    try {
      await api.scanDuplicates()
      await load(1)
    } catch (err) {
      console.error(err)
    } finally {
      setScanning(false)
    }
  }

  const handleDelete = async (groupIds) => {
    await api.deleteDuplicates({ group_ids: groupIds })
    await load(page)
  }

  const handleDeleteAll = async () => {
    if (!confirm(`Delete all duplicates across ${data?.total} groups? Canonical (oldest) copies will be kept.`)) return
    setDeleting(true)
    try {
      await api.deleteDuplicates({ delete_all: true })
      await load(1)
    } finally {
      setDeleting(false)
    }
  }

  const handleDismiss = async (groupId) => {
    await api.dismissDuplicate(groupId)
    await load(page)
  }

  const hasGroups = data?.total > 0

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <Copy className="w-5 h-5 text-purple-600" />
          Deduplication
          {data && (
            <span className="text-sm font-normal text-gray-400">
              ({data.total} group{data.total !== 1 ? 's' : ''} found)
            </span>
          )}
        </h2>
        <div className="flex items-center gap-2">
          {hasGroups && (
            <button
              onClick={handleDeleteAll}
              disabled={deleting}
              className="flex items-center gap-2 px-3 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50">
              {deleting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
              Delete All Duplicates
            </button>
          )}
          <button
            onClick={scan}
            disabled={scanning}
            className="flex items-center gap-2 px-3 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50">
            {scanning ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Copy className="w-4 h-4" />}
            {scanning ? 'Scanning…' : 'Scan for Duplicates'}
          </button>
        </div>
      </div>

      <OnboardingBanner id="dedup-intro">
        QuackBox scans your archive for exact duplicates (same Message-ID from different mailboxes),
        near-exact matches (same sender/subject/date), and content-identical emails.
        The <strong>canonical</strong> (oldest) copy is always kept — only duplicates are deleted.
      </OnboardingBanner>

      {/* Detection method legend */}
      <div className="flex flex-wrap gap-2">
        {Object.entries(METHOD_LABELS).map(([key, { label, color }]) => (
          <span key={key} className={`inline-flex items-center px-2.5 py-1 text-xs rounded-full border ${color}`}>
            {label}
          </span>
        ))}
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }, (_, i) => (
            <div key={i} className="h-16 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : !hasGroups ? (
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl p-12 text-center">
          <CheckCircle className="w-10 h-10 text-green-400 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-gray-700 dark:text-gray-300 mb-1">
            {data === null ? 'No scan run yet' : 'No duplicates found'}
          </h3>
          <p className="text-sm text-gray-400 max-w-xs mx-auto">
            {data === null
              ? 'Click "Scan for Duplicates" to analyze your archive.'
              : 'Your archive looks clean! Run a new scan if you recently imported more emails.'}
          </p>
        </div>
      ) : (
        <>
          <div className="space-y-2">
            {data.groups.map(group => (
              <DuplicateGroup
                key={group.group_id}
                group={group}
                onDelete={handleDelete}
                onDismiss={handleDismiss}
              />
            ))}
          </div>

          {/* Pagination */}
          {data.total_pages > 1 && (
            <div className="flex items-center justify-center gap-3">
              <button
                disabled={page <= 1}
                onClick={() => load(page - 1)}
                className="px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                Previous
              </button>
              <span className="text-sm text-gray-500">
                {page} / {data.total_pages}
              </span>
              <button
                disabled={page >= data.total_pages}
                onClick={() => load(page + 1)}
                className="px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
