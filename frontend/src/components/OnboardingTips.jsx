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

import { useState } from 'react'
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

export default { OnboardingBanner, resetOnboarding }
