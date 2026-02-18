/**
 * Onboarding tooltip system.
 *
 * Shows contextual hints on first visit to each section.
 * Uses localStorage to track which tips have been seen.
 *
 * Usage:
 *   const { Tooltip, markSeen } = useOnboarding('dashboard')
 *   <Tooltip id="stat-cards">Click any card to filter emails by date range</Tooltip>
 */

import { useState, useEffect, useRef } from 'react'
import { X, Lightbulb } from 'lucide-react'

const STORAGE_KEY = 'quackbox-onboarding-seen'

function getSeenTips() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
  } catch {
    return {}
  }
}

function markTipSeen(id) {
  const seen = getSeenTips()
  seen[id] = true
  localStorage.setItem(STORAGE_KEY, JSON.stringify(seen))
}

export function resetOnboarding() {
  localStorage.removeItem(STORAGE_KEY)
  window.location.reload()
}

/**
 * Tooltip component for a single hint bubble.
 * Renders children as the anchor; the tooltip floats above/below.
 */
export function OnboardingTip({ id, children, placement = 'bottom', className = '' }) {
  const seen = getSeenTips()
  const [visible, setVisible] = useState(!seen[id])
  const ref = useRef(null)

  const dismiss = (e) => {
    e.stopPropagation()
    markTipSeen(id)
    setVisible(false)
  }

  if (!visible) return null

  const placementClasses = {
    bottom: 'top-full mt-2 left-1/2 -translate-x-1/2',
    top:    'bottom-full mb-2 left-1/2 -translate-x-1/2',
    right:  'left-full ml-2 top-1/2 -translate-y-1/2',
    left:   'right-full mr-2 top-1/2 -translate-y-1/2',
  }[placement] || 'top-full mt-2 left-1/2 -translate-x-1/2'

  const arrowClasses = {
    bottom: 'bottom-full left-1/2 -translate-x-1/2 border-b-amber-400 border-l-transparent border-r-transparent border-t-transparent',
    top:    'top-full left-1/2 -translate-x-1/2 border-t-amber-400 border-l-transparent border-r-transparent border-b-transparent',
    right:  'right-full top-1/2 -translate-y-1/2 border-r-amber-400 border-t-transparent border-b-transparent border-l-transparent',
    left:   'left-full top-1/2 -translate-y-1/2 border-l-amber-400 border-t-transparent border-b-transparent border-r-transparent',
  }[placement] || 'bottom-full left-1/2 -translate-x-1/2 border-b-amber-400 border-l-transparent border-r-transparent border-t-transparent'

  return (
    <div ref={ref} className={`relative z-50 inline-block ${className}`}>
      {/* Arrow */}
      <div className={`absolute w-0 h-0 border-4 ${arrowClasses}`} style={{ zIndex: 51 }} />

      {/* Bubble */}
      <div className={`absolute ${placementClasses} w-56 bg-amber-400 text-amber-950 text-xs rounded-xl shadow-lg px-3 py-2.5`}
           style={{ zIndex: 50 }}>
        <div className="flex items-start gap-2">
          <Lightbulb className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 opacity-70" />
          <span className="leading-relaxed flex-1">{children}</span>
          <button onClick={dismiss}
            className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity -mr-1 -mt-0.5">
            <X className="w-3 h-3" />
          </button>
        </div>
      </div>
    </div>
  )
}

/**
 * Inline tip banner (not anchored to a specific element).
 * Good for page-level hints at the top of a view.
 */
export function OnboardingBanner({ id, children }) {
  const seen = getSeenTips()
  const [visible, setVisible] = useState(!seen[id])

  const dismiss = () => {
    markTipSeen(id)
    setVisible(false)
  }

  if (!visible) return null

  return (
    <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-800 dark:bg-amber-950/30 dark:border-amber-800 dark:text-amber-200">
      <Lightbulb className="w-4 h-4 flex-shrink-0 mt-0.5 text-amber-500" />
      <span className="flex-1 leading-relaxed">{children}</span>
      <button onClick={dismiss}
        className="flex-shrink-0 text-amber-500 hover:text-amber-700 transition-colors">
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}

export default { OnboardingTip, OnboardingBanner, resetOnboarding }
