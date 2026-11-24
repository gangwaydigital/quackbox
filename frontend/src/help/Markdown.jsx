// Tiny markdown renderer for the help manual. Builds React elements only (no raw HTML), so
// anything it does not recognise is shown as plain text.
// Supports: # ## ### headings, paragraphs, **bold**, *italic*, `code`, - and 1. lists (one level),
// [links] (/app-route uses the router, http(s) opens a new tab), > callouts ("> **Careful:**" is amber),
// | tables |, ``` code fences, and ![caption](/help/name.png) images on their own line.
import { useState } from 'react'
import { Link } from 'react-router-dom'

const INLINE = /(`[^`]+`)|(\*\*[^*]+?\*\*)|(\*[^*\s](?:[^*]*[^*\s])?\*)|(\[[^\]]+\]\([^)\s]+\))/

function inline(text, key = '') {
  const out = []
  let rest = text, i = 0
  while (rest) {
    const m = INLINE.exec(rest)
    if (!m) { out.push(rest); break }
    if (m.index) out.push(rest.slice(0, m.index))
    const t = m[0], k = `${key}${i++}`
    if (m[1]) out.push(<code key={k} className="px-1 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[0.85em] font-mono text-gray-800 dark:text-gray-200">{t.slice(1, -1)}</code>)
    else if (m[2]) out.push(<strong key={k} className="font-semibold">{inline(t.slice(2, -2), k)}</strong>)
    else if (m[3]) out.push(<em key={k}>{inline(t.slice(1, -1), k)}</em>)
    else {
      const [, label, href] = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(t)
      const cls = 'text-blue-600 dark:text-blue-400 hover:underline'
      if (href.startsWith('/')) out.push(<Link key={k} to={href} className={cls}>{inline(label, k)}</Link>)
      else if (/^https?:\/\//.test(href)) out.push(<a key={k} href={href} target="_blank" rel="noopener noreferrer" className={cls}>{inline(label, k)}</a>)
      else out.push(t)   // unknown scheme (e.g. javascript:) stays text
    }
    rest = rest.slice(m.index + t.length)
  }
  return out
}

function Figure({ alt, src }) {
  const [broken, setBroken] = useState(false)
  if (broken) return null   // screenshot not added yet: hide the whole figure
  return (
    <figure className="my-4">
      <img src={src} alt={alt} loading="lazy" onError={() => setBroken(true)}
        className="rounded-lg border border-gray-200 dark:border-gray-700 max-w-full" />
      <figcaption className="mt-1.5 text-xs text-gray-500 dark:text-gray-400">{alt}</figcaption>
    </figure>
  )
}

const cells = (line) => line.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim())
const isRule = (l) => /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/.test(l)
const BULLET = /^[-*] +/, NUMBER = /^\d+\. +/
const HEAD = { 1: 'text-2xl font-bold mt-0 mb-3', 2: 'text-lg font-semibold mt-8 mb-2', 3: 'text-base font-semibold mt-5 mb-1.5' }

export default function Markdown({ source }) {
  const lines = source.replace(/\r/g, '').split('\n')
  const blocks = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i], k = blocks.length
    if (!line.trim()) { i++; continue }

    if (line.startsWith('```')) {
      const body = []
      for (i++; i < lines.length && !lines[i].startsWith('```'); i++) body.push(lines[i])
      i++
      blocks.push(<pre key={k} className="my-3 p-3 rounded-lg bg-gray-100 dark:bg-gray-800 text-xs font-mono overflow-x-auto whitespace-pre-wrap">{body.join('\n')}</pre>)
      continue
    }

    const h = /^(#{1,3}) +(.*)$/.exec(line)
    if (h) {
      const Tag = `h${h[1].length}`
      blocks.push(<Tag key={k} className={`${HEAD[h[1].length]} text-gray-900 dark:text-white`}>{inline(h[2], `h${k}`)}</Tag>)
      i++; continue
    }

    const img = /^!\[([^\]]*)\]\((\/help\/[\w.-]+)\)\s*$/.exec(line)
    if (img) { blocks.push(<Figure key={k} alt={img[1]} src={img[2]} />); i++; continue }

    if (line.startsWith('>')) {
      const body = []
      for (; i < lines.length && lines[i].startsWith('>'); i++) body.push(lines[i].replace(/^>\s?/, ''))
      const warn = /^\*\*(Careful|Warning)/.test(body[0])
      blocks.push(
        <div key={k} className={`my-4 px-4 py-3 rounded-lg border-l-4 text-sm ${warn
          ? 'bg-amber-50 dark:bg-amber-900/20 border-amber-400 text-amber-900 dark:text-amber-200'
          : 'bg-blue-50 dark:bg-blue-900/20 border-blue-400 text-blue-900 dark:text-blue-200'}`}>
          {inline(body.join(' '), `q${k}`)}
        </div>)
      continue
    }

    if (line.trim().startsWith('|') && i + 1 < lines.length && isRule(lines[i + 1])) {
      const head = cells(line), rows = []
      for (i += 2; i < lines.length && lines[i].trim().startsWith('|'); i++) rows.push(cells(lines[i]))
      blocks.push(
        <div key={k} className="my-4 overflow-x-auto">
          <table className="w-full text-sm text-left border border-gray-200 dark:border-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-800/60 text-gray-700 dark:text-gray-200">
              <tr>{head.map((c, j) => <th key={j} className="px-3 py-2 font-semibold">{inline(c, `t${k}h${j}`)}</th>)}</tr>
            </thead>
            <tbody className="text-gray-700 dark:text-gray-300">
              {rows.map((r, a) => (
                <tr key={a} className="border-t border-gray-200 dark:border-gray-700 align-top">
                  {r.map((c, b) => <td key={b} className="px-3 py-2">{inline(c, `t${k}${a}${b}`)}</td>)}
                </tr>))}
            </tbody>
          </table>
        </div>)
      continue
    }

    const list = BULLET.test(line) ? BULLET : NUMBER.test(line) ? NUMBER : null
    if (list) {
      const items = []
      for (; i < lines.length && list.test(lines[i]); i++) {
        let text = lines[i].replace(list, '')
        while (i + 1 < lines.length && /^\s+\S/.test(lines[i + 1])) text += ' ' + lines[++i].trim()   // indented continuation
        items.push(text)
      }
      const Tag = list === BULLET ? 'ul' : 'ol'
      blocks.push(
        <Tag key={k} className={`my-3 pl-6 space-y-1.5 ${Tag === 'ul' ? 'list-disc' : 'list-decimal'}`}>
          {items.map((t, j) => <li key={j}>{inline(t, `l${k}${j}`)}</li>)}
        </Tag>)
      continue
    }

    const para = [lines[i++].trim()]   // always consume one line so odd input cannot loop forever
    for (; i < lines.length && lines[i].trim() && !/^(#{1,3} |```|>|!\[)/.test(lines[i]) && !BULLET.test(lines[i]) && !NUMBER.test(lines[i])
           && !lines[i].trim().startsWith('|'); i++) para.push(lines[i].trim())
    blocks.push(<p key={k} className="my-3">{inline(para.join(' '), `p${k}`)}</p>)
  }
  return <div className="text-sm leading-relaxed text-gray-700 dark:text-gray-300">{blocks}</div>
}
