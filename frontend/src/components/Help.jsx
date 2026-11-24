import { useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { HelpCircle } from 'lucide-react'
import Markdown from '../help/Markdown'
import { sections } from '../help/sections'

export default function Help() {
  const { section } = useParams()
  const current = sections.find(s => s.slug === section) || sections[0]

  useEffect(() => { document.querySelector('main')?.scrollTo(0, 0) }, [current.slug])

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
        <HelpCircle className="w-5 h-5 text-blue-600" /> Help
      </h2>
      <div className="flex flex-col md:flex-row gap-4 md:gap-6">
        <nav className="md:w-48 flex-shrink-0 flex md:flex-col gap-1 overflow-x-auto md:overflow-visible pb-1 md:pb-0 md:sticky md:top-4 md:self-start">
          {sections.map(s => (
            <Link key={s.slug} to={`/help/${s.slug}`}
              className={`px-3 py-1.5 rounded-lg text-sm whitespace-nowrap transition-colors ${s.slug === current.slug
                ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium'
                : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'}`}>
              {s.title}
            </Link>
          ))}
        </nav>
        <article className="flex-1 min-w-0 max-w-3xl bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-5 sm:p-6">
          <Markdown source={current.body} />
        </article>
      </div>
    </div>
  )
}
