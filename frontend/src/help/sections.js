// Manual sections in sidebar order. `slug` is the /help/:slug URL; add a page by adding a .md file and a row here.
import gettingStarted from './getting-started.md?raw'
import dashboard from './dashboard.md?raw'
import emails from './emails.md?raw'
import search from './search.md?raw'
import calendar from './calendar.md?raw'
import events from './events.md?raw'
import timeline from './timeline.md?raw'
import threads from './threads.md?raw'
import contacts from './contacts.md?raw'
import network from './network.md?raw'
import mailboxes from './mailboxes.md?raw'
import files from './files.md?raw'
import duplicates from './duplicates.md?raw'
import topics from './topics.md?raw'
import chat from './chat.md?raw'
import cases from './cases.md?raw'

export const sections = [
  { slug: 'getting-started', title: 'Getting started', body: gettingStarted },
  { slug: 'dashboard', title: 'Dashboard', body: dashboard },
  { slug: 'emails', title: 'Emails', body: emails },
  { slug: 'search', title: 'Search', body: search },
  { slug: 'calendar', title: 'Calendar', body: calendar },
  { slug: 'events', title: 'Events', body: events },
  { slug: 'timeline', title: 'Timeline', body: timeline },
  { slug: 'threads', title: 'Threads', body: threads },
  { slug: 'contacts', title: 'Contacts', body: contacts },
  { slug: 'network', title: 'Network', body: network },
  { slug: 'mailboxes', title: 'Mailboxes', body: mailboxes },
  { slug: 'files', title: 'Files', body: files },
  { slug: 'duplicates', title: 'Duplicates', body: duplicates },
  { slug: 'topics', title: 'Topics', body: topics },
  { slug: 'chat', title: 'Chat', body: chat },
  { slug: 'cases', title: 'Cases', body: cases },
]
