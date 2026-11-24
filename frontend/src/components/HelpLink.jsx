import { Link } from 'react-router-dom'
import { HelpCircle } from 'lucide-react'

// Small "?" icon for a page title: jumps to that page's section of the in-app manual.
export default function HelpLink({ section }) {
  return (
    <Link to={`/help/${section}`} title="Help for this page" aria-label="Help for this page"
      className="text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors">
      <HelpCircle className="w-4 h-4" />
    </Link>
  )
}
