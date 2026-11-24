# Search

Advanced Search combines words with filters, and results update as you type.

## Controls

- **Keywords**: the words to find in subject, sender and body. Supported:
  - `budget review` finds emails with both words (they are combined with AND).
  - `AND`, `OR`, `NOT` in capitals, for example `budget OR forecast`.
  - `"exact phrase"` in quotes.
  - The last word also matches longer words, so `proj` finds `project`.
- **Sender**: part of a name or email address.
- **From** and **To**: date range.
- **Attachments** checkbox: only emails that have files.
- **Clear** empties everything.
- **Saved** panel (left on a desktop, a button on a phone): click the bookmark icon to save the current search under a name and a color, click a saved search to run it again, and use the bin icon to delete it. Saved searches also appear in the left sidebar with live counts.

Click a result to read it in the pane beside the list. **Prev** and **Next** page through results.

![Advanced Search with filters and a saved search](/help/search.png)

## Example

To find mail from Jordan about the budget but not about travel: type `budget NOT travel` in Keywords, `Jordan` in Sender, then click the bookmark icon and save it as "Jordan budget".

> **Careful:** Words are matched after stemming, so `offices` also finds `office`. A word shorter than two letters is ignored, and punctuation such as `:` is dropped.

> **Tip:** This page uses operators. Cases do not: each Case search term is one phrase, with no AND or OR. See [Cases](/help/cases).
