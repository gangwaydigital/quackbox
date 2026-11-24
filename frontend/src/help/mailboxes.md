# Mailboxes

Mailboxes is where you import mail and where you see how much came from each source.

## Import Sources (top of the page)

- **Check** looks for new mail without importing it.
- **Run Import** imports new mail. When new mail is found, the button changes to **Import New Mail**. Sources that did not change are skipped, so it is quick.
- **Full re-scan** re-reads every source. Use it only if you moved or replaced the source files.
- A progress panel shows the source being read and its counts.
- **Add folder** (in the folders box) opens a folder browser so you can register another place to import from. Removing a folder stops scanning it, and mail already imported stays.
- **Auto-import watcher** shows whether QuackBox checks for new mail on a schedule and **Scan now** runs a check immediately. The schedule is set with `WATCH_INTERVAL_MINUTES` in your `.env` file, and it reads "Disabled" until you set it.

## Mailbox list

Below that, each mailbox appears as a card with its email count, senders and year range, and a bar sized by volume.

- **Sort**: Most Emails, Name A-Z or Most Recent.
- **Export All** downloads every email as a CSV file.
- Click a card for that mailbox's page: totals, volume over time, top senders and yearly counts.

![Mailboxes page with import sources and mailbox cards](/help/mailboxes.png)

## Example

You exported new mail from your mail program into a registered folder. Open Mailboxes, click **Check**, and if it reports new mail click **Import New Mail**. Then reload the Dashboard to see the new totals.

> **Tip:** The **Browse emails in this mailbox** button on a mailbox page opens [Emails](/help/emails). It does not filter the list yet, so use the **Mailbox** filter there.
