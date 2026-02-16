import { useState, useRef, useEffect } from 'react'
import { api } from '../api/client'

const cache = {}

export function ContactHover({ email, children }) {
  const [show, setShow] = useState(false)
  const [data, setData] = useState(null)
  const timerRef = useRef(null)

  const handleEnter = () => {
    timerRef.current = setTimeout(async () => {
      setShow(true)
      if (cache[email]) { setData(cache[email]); return }
      try {
        const d = await api.getContact(email)
        cache[email] = d
        setData(d)
      } catch {}
    }, 400)
  }

  const handleLeave = () => {
    clearTimeout(timerRef.current)
    setShow(false)
  }

  return (
    <span className="relative inline-block" onMouseEnter={handleEnter} onMouseLeave={handleLeave}>
      {children}
      {show && data && (
        <div className="absolute z-50 bottom-full left-0 mb-2 w-64 bg-white/95 backdrop-blur-sm rounded-lg border border-gray-200 shadow-lg p-3 pointer-events-none">
          <div className="text-sm font-semibold text-gray-800 truncate">{data.sender_name || email}</div>
          <div className="text-xs text-gray-400 truncate">{email}</div>
          <div className="grid grid-cols-3 gap-2 mt-2 text-center">
            <div><div className="text-sm font-bold text-gray-700">{data.total_emails?.toLocaleString()}</div><div className="text-[9px] text-gray-400">emails</div></div>
            <div><div className="text-sm font-bold text-gray-700">{data.thread_count || 0}</div><div className="text-[9px] text-gray-400">threads</div></div>
            <div><div className="text-sm font-bold text-blue-600">{data.relationship_score?.score || 0}</div><div className="text-[9px] text-gray-400">score</div></div>
          </div>
          {data.relationship_score?.label && (
            <div className="text-[10px] text-center mt-1.5 px-2 py-0.5 rounded-full bg-blue-50 text-blue-600">{data.relationship_score.label}</div>
          )}
        </div>
      )}
    </span>
  )
}
