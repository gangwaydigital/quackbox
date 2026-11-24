# Getting started

QuackBox turns your mailbox exports into a private, searchable archive on your own computer. This page covers your first import and gives you a map of the sidebar.

## Import your mail

The first time you open QuackBox with an empty archive, a welcome screen walks you through it.

1. Click **Choose a folder…** and pick the folder that holds your mail.
2. Check what QuackBox found (Apple Mail mailboxes, `.mbox` files) and click **Import All Email Data**.
3. Watch the progress bar. When it says **Import Complete!**, the app opens on the Dashboard.

QuackBox understands Apple Mail `.emlx` folders (pick `~/Library/Mail/V10`), standard `.mbox` files (Google Takeout, Thunderbird) and Apple Mail `.mbox` bundles. If you prefer, drop the files into the data folder shown on the welcome screen and click **Scan Again**.

> **Tip:** Your original files are only read, never changed. You can import the same folder again later and only the new mail is processed.

To add more mail later, or to check for new messages, go to [Mailboxes](/help/mailboxes).

## What is in the sidebar

| Page | What it is for |
|---|---|
| [Dashboard](/help/dashboard) | Totals and charts for the whole archive |
| [Emails](/help/emails) | Browse, filter and read messages |
| [Search](/help/search) | Advanced search with operators and saved searches |
| [Calendar](/help/calendar) | A month grid showing how busy each day was |
| [Events](/help/events) | Meeting invites found in your mail |
| [Timeline](/help/timeline) | Milestones: first email, busiest days, big threads |
| [Threads](/help/threads) | Conversations rebuilt from replies |
| [Contacts](/help/contacts) | Everyone you exchanged mail with |
| [Network](/help/network) | A graph of who appears in threads together |
| [Mailboxes](/help/mailboxes) | Import sources and per-mailbox statistics |
| [Files](/help/files) | Attachments, including text inside PDFs and Word files |
| [Duplicates](/help/duplicates) | Find and remove repeated messages |
| [Topics](/help/topics) | Automatic grouping of emails by subject matter |
| [Chat](/help/chat) | Ask questions about your archive in plain language |
| [Cases](/help/cases) | Research workspaces that gather and export evidence |

On a phone, the bottom bar shows the most used pages. Tap **More** for the rest.

## AI and privacy

Everything runs on your own machine. Your emails are stored in a local database, and the AI features (Chat, summaries, Topics, Smart search, Cases) talk to a model that you run yourself, by default through Ollama or oMLX. Nothing is sent to an outside service unless you deliberately point the AI settings at one.

The AI provider and models are set in the `.env` file next to `docker-compose.yml` (see the README). Features that need a model show an error or an "offline" label if it is not running.

> **Tip:** Press `?` anywhere to see the keyboard shortcuts. Every page also has a small **?** icon next to its title that opens its section of this manual.
