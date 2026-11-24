import { useState, useEffect, useRef, useCallback } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Briefcase, Loader2, Play, Pencil, Trash2, Download, AlertTriangle, Sparkles, UserPlus, ExternalLink } from 'lucide-react'
import { api } from '../api/client'

const input = 'px-3 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-white'
const card = 'bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 space-y-3'
const btn = 'px-3 py-1.5 text-xs rounded-lg border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-50 inline-flex items-center gap-1'
const btnPrimary = 'px-3 py-1.5 text-xs rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 inline-flex items-center gap-1'
const badge = 'px-1.5 py-0.5 text-[10px] rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300'
const warnBadge = 'px-1.5 py-0.5 text-[10px] rounded bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300'
const PAGE = 50

const Spin = () => <Loader2 className="w-3.5 h-3.5 animate-spin" />

// Proposal picker shared by "Suggest terms" and "Find more". Never auto-saves.
function Proposals({ terms, picked, setPicked, onAdd, adding }) {
  if (!terms.length) return <div className="text-xs text-gray-500">No new terms proposed.</div>
  return (
    <div className="space-y-1">
      {terms.map(t => (
        <label key={t.text} className="flex items-start gap-2 text-sm text-gray-800 dark:text-gray-200">
          <input type="checkbox" className="mt-1" checked={!!picked[t.text]}
            onChange={e => setPicked(p => ({ ...p, [t.text]: e.target.checked }))} />
          <span><b>{t.text}</b>{t.reason && <span className="text-gray-500"> — {t.reason}</span>}</span>
        </label>
      ))}
      <button className={btnPrimary} disabled={adding || !terms.some(t => picked[t.text])} onClick={onAdd}>
        {adding && <Spin />}Add selected
      </button>
    </div>
  )
}

export default function CaseView() {
  const { id } = useParams()
  const [c, setC] = useState(null)
  const [error, setError] = useState(null)
  const [runs, setRuns] = useState([])
  const [cands, setCands] = useState({ items: [], total: 0 })
  const [filters, setFilters] = useState({ review: '', triage: '' })
  const [page, setPage] = useState(1)
  const [busy, setBusy] = useState({})   // key -> true while a slow call runs
  const [person, setPerson] = useState({ name: '', emails: '' })
  const [personQ, setPersonQ] = useState('')          // text being typed in Name or Emails
  const [contactHits, setContactHits] = useState([])          // matching contacts from the archive
  const [newTerm, setNewTerm] = useState('')
  const [editing, setEditing] = useState(null) // { id, text }
  const [proposals, setProposals] = useState(null)   // { terms, error }
  const [picked, setPicked] = useState({})
  const [more, setMore] = useState(null)             // { terms, people, error }
  const [morePicked, setMorePicked] = useState({})
  const [triage, setTriage] = useState({ running: false })
  const [quoteDrafts, setQuoteDrafts] = useState({})
  const [quoteErrors, setQuoteErrors] = useState({})
  const [noteDrafts, setNoteDrafts] = useState({})
  const pollRef = useRef(null)

  const run = (key, fn) => async (...a) => {
    setBusy(b => ({ ...b, [key]: true }))
    setError(null)
    try { return await fn(...a) } catch (e) { setError(e.message) } finally { setBusy(b => ({ ...b, [key]: false })) }
  }

  const loadCase = useCallback(() => api.getCase(id).then(setC).catch(e => setError(e.message)), [id])
  const loadRuns = useCallback(() => api.getCaseRuns(id).then(setRuns).catch(() => {}), [id])
  const loadCands = useCallback(
    () => api.getCaseCandidates(id, { ...filters, page, pageSize: PAGE }).then(setCands).catch(e => setError(e.message)),
    [id, filters, page])

  useEffect(() => { loadCase(); loadRuns() }, [loadCase, loadRuns])
  useEffect(() => { loadCands() }, [loadCands])

  const stopPoll = () => { clearInterval(pollRef.current); pollRef.current = null }
  const startPoll = useCallback(() => {
    if (pollRef.current) return
    pollRef.current = setInterval(async () => {
      try {
        const s = await api.getCaseTriageStatus()
        setTriage(s)
        if (!s.running) { stopPoll(); loadCands() }
      } catch { /* network blip: keep polling */ }
    }, 2000)
  }, [loadCands])
  useEffect(() => {
    api.getCaseTriageStatus().then(s => { setTriage(s); if (s.running) startPoll() }).catch(() => {})
    return stopPoll
  }, [startPoll])

  const after = () => { loadCase(); loadRuns(); loadCands() }

  const addPerson = run('person', async (e) => {
    e.preventDefault()
    const emails = person.emails.split(/[,\s]+/).filter(Boolean)
    await api.addCasePerson(id, person.name.trim(), emails)
    setPerson({ name: '', emails: '' })
    setPersonQ('')
    loadCase()
  })

  useEffect(() => {
    if (personQ.trim().length < 2) { setContactHits([]); return }
    const t = setTimeout(() => {
      api.getContacts({ search: personQ.trim(), page_size: 8 }).then(r => setContactHits(r.items || [])).catch(() => setContactHits([]))
    }, 250)
    return () => clearTimeout(t)
  }, [personQ])

  const pickContact = (s) => {
    setPerson(p => {
      const kept = p.emails.split(/[,\s]+/).filter(x => x && x !== personQ.trim())
      // A name typed only to search gets replaced by the contact's full name.
      const name = !p.name.trim() || p.name === personQ ? (s.display_name || p.name) : p.name
      return { name, emails: [...new Set([...kept, s.sender_email])].join(', ') }
    })
    setPersonQ('')
  }
  const addTerm = run('term', async (e) => {
    e.preventDefault()
    await api.addCaseTerm(id, newTerm)
    setNewTerm('')
    loadCase()
  })
  const saveEdit = run('edit', async () => { await api.editCaseTerm(editing.id, editing.text); setEditing(null); loadCase() })
  const retire = run('retire', async (tid) => { await api.retireCaseTerm(tid); loadCase() })
  const runTerm = run('runterm', async (tid) => { await api.runCaseTerm(id, tid); after() })
  const runAll = run('runall', async () => { await api.runAllCaseTerms(id); after() })
  const suggest = run('suggest', async () => {
    const r = await api.proposeCaseTerms(id)
    setProposals(r)
    setPicked({})
  })
  const addPicked = (src, list, sel, reset) => run('add' + src, async () => {
    for (const t of list.filter(t => sel[t.text])) await api.addCaseTerm(id, t.text, src)
    reset()
    loadCase()
  })
  const findMore = run('more', async () => { setMore(await api.caseFindMore(id)); setMorePicked({}) })
  const addAsPerson = run('addperson', async (p) => { await api.addCasePerson(id, p.name || p.email, [p.email]); loadCase() })

  const setReview = run('review', async (emailId, review) => {
    await api.updateCaseCandidate(id, emailId, { review })
    loadCands(); loadCase()
  })
  const saveNote = run('note', async (emailId) => {
    const v = noteDrafts[emailId].trim()
    await api.updateCaseCandidate(id, emailId, { note: v || null })
    loadCands()
  })
  const saveQuote = async (emailId) => {
    setQuoteErrors(q => ({ ...q, [emailId]: null }))
    try {
      await api.updateCaseCandidate(id, emailId, { owner_quote: quoteDrafts[emailId] })
      loadCands()
    } catch (e) {
      setQuoteErrors(q => ({ ...q, [emailId]: e.status === 400 ? "That text isn't in the email." : e.message }))
    }
  }

  const startTriage = run('triage', async () => {
    await api.startCaseTriage(id)
    setTriage({ running: true, case_id: Number(id), done: 0, total: 0 })
    startPoll()
  })
  const cancelTriage = run('cancel', () => api.cancelCaseTriage())

  if (!c) return <div className="text-sm text-gray-500">{error || 'Loading…'}</div>
  const triageHere = triage.running && String(triage.case_id) === String(id)
  const pages = Math.max(1, Math.ceil(cands.total / PAGE))

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Link to="/cases" className="text-gray-400 hover:text-blue-600"><Briefcase className="w-5 h-5" /></Link>
            {c.name}
          </h2>
          <a href={api.caseExportUrl(id)} className={btnPrimary}><Download className="w-3.5 h-3.5" />Export ZIP</a>
        </div>
        <p className="text-sm text-gray-700 dark:text-gray-300">{c.issue}</p>
        {(c.date_from || c.date_to) && <div className="text-xs text-gray-500">{c.date_from || '…'} to {c.date_to || '…'}</div>}
        {!c.attachments_indexed && (
          <div className="flex items-center gap-2 text-sm p-2 rounded-lg bg-amber-50 dark:bg-amber-900/20 text-amber-800 dark:text-amber-300">
            <AlertTriangle className="w-4 h-4" />Attachment text isn't indexed yet, so attachments weren't searched.
          </div>
        )}
        {error && <div className="text-sm text-red-600 dark:text-red-400">{error}</div>}
      </div>

      {/* People */}
      <section className={card}>
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">People</h3>
        <ul className="text-sm text-gray-800 dark:text-gray-200 space-y-0.5">
          {c.people.map(p => <li key={p.id}><b>{p.name}</b> <span className="text-gray-500">{p.emails.join(', ')}</span></li>)}
        </ul>
        <form onSubmit={addPerson} className="flex gap-2 flex-wrap">
          <input className={input} placeholder="Name" value={person.name} onChange={e => { const v = e.target.value; setPerson(p => ({ ...p, name: v })); setPersonQ(v) }} />
          <input className={`${input} flex-1 min-w-[12rem]`} placeholder="Emails (comma separated)" value={person.emails} onChange={e => { const v = e.target.value; setPerson(p => ({ ...p, emails: v })); setPersonQ(v.split(/[,\s]+/).pop()) }} />
          <button className={btn} disabled={busy.person || !person.name.trim()}><UserPlus className="w-3.5 h-3.5" />Add</button>
        </form>
        {contactHits.length > 0 && (
          <ul className="border border-gray-200 dark:border-gray-800 rounded-lg divide-y divide-gray-100 dark:divide-gray-800 text-sm">
            {contactHits.map(s => (
              <li key={s.sender_email}>
                <button type="button" onClick={() => pickContact(s)} className="w-full text-left px-3 py-1.5 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-800 dark:text-gray-200">
                  {s.display_name || s.sender_email} <span className="text-xs text-gray-500">{s.sender_email} · {s.total_emails} emails</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Terms */}
      <section className={card}>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Search terms</h3>
          <div className="flex gap-2">
            <button className={btn} disabled={busy.suggest} onClick={suggest}>{busy.suggest ? <Spin /> : <Sparkles className="w-3.5 h-3.5" />}Suggest terms</button>
            <button className={btnPrimary} disabled={busy.runall || !c.terms.length} onClick={runAll}>{busy.runall ? <Spin /> : <Play className="w-3.5 h-3.5" />}Run all</button>
          </div>
        </div>
        <ul className="space-y-1">
          {c.terms.map(t => (
            <li key={t.id} className="flex items-center gap-2 text-sm text-gray-800 dark:text-gray-200">
              {editing?.id === t.id ? (
                <>
                  <input className={`${input} flex-1`} value={editing.text} onChange={e => setEditing({ id: t.id, text: e.target.value })} />
                  <button className={btnPrimary} disabled={busy.edit} onClick={saveEdit}>Save</button>
                  <button className={btn} onClick={() => setEditing(null)}>Cancel</button>
                </>
              ) : (
                <>
                  <span className="flex-1">{t.text} <span className={badge}>{t.source}</span> <span className="text-xs text-gray-500">v{t.version}</span></span>
                  <button className={btn} disabled={busy.runterm} onClick={() => runTerm(t.id)}><Play className="w-3 h-3" />Run</button>
                  <button className={btn} onClick={() => setEditing({ id: t.id, text: t.text })}><Pencil className="w-3 h-3" /></button>
                  <button className={btn} disabled={busy.retire} onClick={() => retire(t.id)}><Trash2 className="w-3 h-3" /></button>
                </>
              )}
            </li>
          ))}
        </ul>
        <form onSubmit={addTerm} className="flex gap-2">
          <input className={`${input} flex-1`} placeholder="Add a search term" value={newTerm} onChange={e => setNewTerm(e.target.value)} />
          <button className={btn} disabled={busy.term || !newTerm.trim()}>Add</button>
        </form>
        {proposals && (
          <div className="border-t border-gray-200 dark:border-gray-800 pt-3 space-y-2">
            {proposals.error && <div className="text-xs text-red-600 dark:text-red-400">{proposals.error}</div>}
            <Proposals terms={proposals.terms} picked={picked} setPicked={setPicked} adding={busy.addmodel}
              onAdd={addPicked('model', proposals.terms, picked, () => { setProposals(null); setPicked({}) })} />
          </div>
        )}
      </section>

      {/* Search log */}
      <section className={card}>
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Search log</h3>
        {runs.length === 0 ? <div className="text-xs text-gray-500">No runs yet.</div> : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left text-gray-800 dark:text-gray-200">
              <thead className="text-gray-500"><tr>
                <th className="pr-3">Term</th><th className="pr-3">Ver</th><th className="pr-3">Time</th><th className="pr-3">Status</th>
                <th className="pr-3">Keyword</th><th className="pr-3">Recipients</th><th className="pr-3">Attach.</th><th className="pr-3">Semantic</th>
              </tr></thead>
              <tbody>
                {runs.map(r => {
                  const n = r.channel_counts || {}
                  return (
                    <tr key={r.id} className="border-t border-gray-100 dark:border-gray-800 align-top">
                      <td className="pr-3 py-1">{r.term_text}</td>
                      <td className="pr-3">{r.term_version ?? ''}{!!r.term_retired && ' (retired)'}</td>
                      <td className="pr-3 whitespace-nowrap">{r.started_at}</td>
                      <td className="pr-3">{r.status === 'ok' ? 'ok' : r.status === 'running' ? <span className="text-amber-700 dark:text-amber-400">running / did not finish</span> : <span className="text-red-600 dark:text-red-400">error: {r.error}</span>}</td>
                      <td className="pr-3">{n.keyword ?? ''}</td>
                      <td className="pr-3">{n.recipients ?? ''}</td>
                      <td className="pr-3">{n.attachments ?? ''}</td>
                      <td className="pr-3">{n.semantic ?? ''}{n.semantic_capped && <span className="ml-1 text-amber-700 dark:text-amber-400">semantic capped at 50</span>}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Triage */}
      <section className={card}>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Triage</h3>
          <div className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
            {triageHere && <span>{triage.done}/{triage.total}</span>}
            {triageHere
              ? <button className={btn} disabled={busy.cancel} onClick={cancelTriage}>Cancel</button>
              : <button className={btnPrimary} disabled={busy.triage || triage.running} onClick={startTriage}>{busy.triage && <Spin />}Start triage</button>}
          </div>
        </div>
        {triage.running && !triageHere && <div className="text-xs text-gray-500">Triage is running for another case.</div>}
        {!triage.running && triage.error && <div className="text-xs text-red-600 dark:text-red-400">error: {triage.error}</div>}
        {!triage.running && triage.cancelled && <div className="text-xs text-gray-500">Last triage was cancelled.</div>}
      </section>

      {/* Review queue */}
      <section className={card}>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Review queue ({cands.total})</h3>
          <div className="flex gap-2">
            <select className={input} value={filters.review} onChange={e => { setPage(1); setFilters(f => ({ ...f, review: e.target.value })) }}>
              <option value="">All reviews</option><option value="unreviewed">Unreviewed</option>
              <option value="evidence">Evidence</option><option value="not_relevant">Not relevant</option>
            </select>
            <select className={input} value={filters.triage} onChange={e => { setPage(1); setFilters(f => ({ ...f, triage: e.target.value })) }}>
              <option value="">All triage</option><option value="relevant">Relevant</option><option value="maybe">Maybe</option>
              <option value="not">Not</option><option value="untriaged">Untriaged</option>
            </select>
          </div>
        </div>
        <ul className="divide-y divide-gray-100 dark:divide-gray-800">
          {cands.items.map(m => (
            <li key={m.email_id} className="py-3 space-y-1.5 text-sm text-gray-800 dark:text-gray-200">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-medium truncate">{m.subject || '(no subject)'}</div>
                  <div className="text-xs text-gray-500">{m.date_sent} · {m.sender_name || m.sender_email}</div>
                </div>
                <Link to={`/email/${m.email_id}`} className={btn}><ExternalLink className="w-3 h-3" />Open</Link>
              </div>
              <div className="flex flex-wrap gap-1 items-center">
                <span className={badge}>{m.review}</span>
                <span className={badge}>triage: {m.triage}</span>
                {!!m.semantic_only && <span className={warnBadge}>semantic only</span>}
                {!!m.out_of_range && <span className={warnBadge}>outside dates</span>}
                {!!m.partial_text && <span className={warnBadge}>partial text</span>}
                {m.triage_error && <span className={warnBadge}>triage error: {m.triage_error}</span>}
              </div>
              {m.triage_reason && <div className="text-xs text-gray-600 dark:text-gray-400">{m.triage_reason}</div>}
              {m.model_quote && (m.model_quote_ok
                ? <div className="text-xs italic border-l-2 border-green-500 pl-2">Verified quote: “{m.model_quote}”</div>
                : <div className="text-xs italic text-gray-400 line-through">“{m.model_quote}” <span className="not-italic no-underline text-amber-700 dark:text-amber-400">(quote not found)</span></div>)}
              {m.owner_quote && <div className="text-xs border-l-2 border-blue-500 pl-2">Your quote: “{m.owner_quote}”</div>}
              <div className="flex gap-1.5 flex-wrap">
                <button className={btnPrimary} disabled={busy.review} onClick={() => setReview(m.email_id, 'evidence')}>Evidence</button>
                <button className={btn} disabled={busy.review} onClick={() => setReview(m.email_id, 'not_relevant')}>Not relevant</button>
                <button className={btn} disabled={busy.review} onClick={() => setReview(m.email_id, 'unreviewed')}>Reset</button>
              </div>
              <div className="flex gap-2 flex-wrap">
                <input className={`${input} flex-1 min-w-[12rem]`} placeholder="Note"
                  value={noteDrafts[m.email_id] ?? m.note ?? ''}
                  onChange={e => setNoteDrafts(d => ({ ...d, [m.email_id]: e.target.value }))} />
                <button className={btn} disabled={busy.note || noteDrafts[m.email_id] === undefined} onClick={() => saveNote(m.email_id)}>Save note</button>
              </div>
              <div className="flex gap-2 flex-wrap items-center">
                <input className={`${input} flex-1 min-w-[12rem]`} placeholder="Set quote (text copied from the email)"
                  value={quoteDrafts[m.email_id] ?? ''}
                  onChange={e => setQuoteDrafts(d => ({ ...d, [m.email_id]: e.target.value }))} />
                <button className={btn} disabled={!quoteDrafts[m.email_id]?.trim()} onClick={() => saveQuote(m.email_id)}>Set quote</button>
                {quoteErrors[m.email_id] && <span className="text-xs text-red-600 dark:text-red-400">{quoteErrors[m.email_id]}</span>}
              </div>
            </li>
          ))}
        </ul>
        {cands.items.length === 0 && <div className="text-xs text-gray-500">Nothing in the queue.</div>}
        {pages > 1 && (
          <div className="flex items-center gap-2 text-xs">
            <button className={btn} disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</button>
            <span>Page {page} of {pages}</span>
            <button className={btn} disabled={page >= pages} onClick={() => setPage(p => p + 1)}>Next</button>
          </div>
        )}
      </section>

      {/* Find more */}
      <section className={card}>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Find more</h3>
          <button className={btn} disabled={busy.more} onClick={findMore}>{busy.more ? <Spin /> : <Sparkles className="w-3.5 h-3.5" />}Find more from evidence</button>
        </div>
        {more && (
          <div className="space-y-3">
            {more.error && <div className="text-xs text-red-600 dark:text-red-400">{more.error}</div>}
            <Proposals terms={more.terms} picked={morePicked} setPicked={setMorePicked} adding={busy.addfind_more}
              onAdd={addPicked('find_more', more.terms, morePicked, () => { setMore(m => ({ ...m, terms: [] })); setMorePicked({}) })} />
            {more.people.length > 0 && (
              <ul className="space-y-1 text-sm text-gray-800 dark:text-gray-200">
                {more.people.map(p => (
                  <li key={p.email} className="flex items-center gap-2">
                    <span className="flex-1">{p.name || p.email} <span className="text-xs text-gray-500">{p.email} · cc'd on {p.count} evidence emails</span></span>
                    <button className={btn} disabled={busy.addperson} onClick={() => addAsPerson(p)}><UserPlus className="w-3 h-3" />Add as person</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>
    </div>
  )
}
