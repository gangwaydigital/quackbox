# Cases

A case is a research workspace for one question, such as "everything about the office move" or "every mention of one person on one subject". You tell QuackBox what to look for, it gathers candidate emails, an AI helps put the likeliest ones first, and **you** decide which emails count as evidence. At the end you export the evidence as a ZIP.

The AI never decides anything. It suggests search terms and sorts the review queue, nothing more.

## Create a case

Open **Cases** in the sidebar. The form at the top has:

- **Name**: anything you like.
- **Describe the issue to research**: a few sentences about what you are looking for.
- **From** and **To**: an optional date range.

Click **Create case** and you land on the case page. Existing cases are listed underneath with their number of candidates and evidence emails.

![Cases list with the new case form](/help/cases-list.png)

> **Careful:** Write the issue text properly. The AI reads it for every email when it triages, and uses it to suggest terms. If the topics you care about are not in the issue text, the AI cannot judge relevance.

The dates are a hint, not a filter. Emails outside the range are still found, but they are flagged **outside dates** and sorted lower. Emails with no date are kept.

If you see "Attachment text isn't indexed yet" at the top of a case, attachments were not searched. Open [Files](/help/files), go to **Content Search** and index them first.

## The case page

From top to bottom: **People**, **Search terms**, **Search log**, **Triage**, **Review queue** and **Find more**. **Export ZIP** is at the top right. The usual workflow is the same order: add people and terms, run, check the log, triage, review, find more, export.

## People

![People card with contact suggestions](/help/case-people.png)

Type a name in **Name**. After two letters, matching contacts from your archive appear below with their address and email count. Click one to fill in the full name and add their address to **Emails**. You can also type addresses yourself, separated by commas. Click **Add**.

Adding a person automatically creates search terms: their name, and each address as its own term. A person is not a filter. It is simply a shortcut for adding those terms, and the list of people is also shown to the AI as context.

## Search terms

![Search terms card with Run and Run all](/help/case-terms.png)

This is where most of the thinking happens, so read this part carefully.

**Each term runs on its own.** There is no AND and no OR. A term is searched as one phrase, and every email it finds is added to the same pool of candidates. Ten terms mean ten separate searches.

How a term is matched:

- It is a **phrase**: the words must appear next to each other, in that order. `office move` finds "the office move" but not "moving the office".
- Words are matched by their stem, so `offices` also finds `office`, and capitalization does not matter.
- A trailing `*` makes a prefix match. Keep the prefix short, because it is matched against word stems: `reloc*` finds relocate and relocation, but `relocat*` misses relocation.
- Punctuation is ignored, so `jordan.avery@harborlane.example` is searched as those words in a row.

Each term is searched in four **channels**:

| Channel | What it looks at |
|---|---|
| keyword | Subject, sender name and address, and the email text. |
| recipients | Any part of the sender and the To, Cc and Bcc names and addresses. This is a plain "contains" match, so a short term such as `Jo` matches Joe, John and Jordan. |
| attachments | Text inside indexed PDF and Word files. |
| semantic | Emails with a similar meaning, the best 50 per term. Needs the embeddings that [Topics](/help/topics) creates. |

An email found only by the semantic channel is marked **semantic only**, which means lower confidence.

Controls:

- **Add a search term** box and **Add** for your own terms.
- **Run** next to a term runs just that term. **Run all** runs every term in turn.
- The pencil edits a term. This saves a new version (v2, v3, ...) and retires the old one, and the log keeps both.
- The bin retires a term so it no longer runs. Its past runs stay in the log.
- A small tag shows where a term came from: `owner` (you or a person), `model` (Suggest terms) or `find_more`.
- **Suggest terms** asks the AI for extra names, nicknames, misspellings and keywords based on your issue text and people. You tick the ones you want and click **Add selected**. Nothing is added automatically.

> **Tip:** Running a term again is safe. It only adds new emails, and it never changes a review decision you already made.

## Search log

![Search log with per-channel counts](/help/case-log.png)

Every run adds a row: the term, its version, the time, a status and one count per channel (Keyword, Recipients, Attach., Semantic). The same email can be counted in several channels.

Read the status column:

- **ok**: all four channels ran.
- **error: ...** names the channel that failed, for example `semantic: no embeddings indexed` or `semantic: query embedding failed` (the AI model is not running). The other channels' results are still saved, but this run may be incomplete.
- **running / did not finish**: the run was interrupted.
- **semantic capped at 50**: the semantic channel found at least 50 matches and QuackBox kept the top 50, so there may be more.

Retired terms are marked `(retired)`.

## Triage

![Triage card while running](/help/case-triage.png)

Triage uses your AI model (the same provider as Chat, by default running locally) to read each candidate and give a first opinion. For every email it receives the issue text and the start of the email (the first 6,000 characters), and returns:

- a label: **relevant**, **maybe** or **not**,
- a one-sentence reason,
- a short quote from the email as support.

QuackBox checks the quote against the real text. If the quote is not really in the email, it is shown crossed out as **quote not found** and is never trusted.

Triage only orders the queue. Relevant emails move up, then maybe, then untriaged, then not. It never marks evidence and never hides an email.

How it works in practice:

- Click **Start triage**. It shows progress as `done/total` and handles one email after another. Speed depends on your model and machine. On a fast Mac with a local model it handled about 40 emails a minute, so 500 emails take around 12 minutes.
- **Cancel** stops after the current email. What was finished keeps its label.
- Only one triage runs at a time, across all cases.
- **Start triage** only picks up untriaged emails, so run it again after adding more terms. Emails that failed with an error are tried again too.

## Review queue

![Review queue filtered to Relevant](/help/case-queue.png)

The queue is the list of all candidates. The title shows how many match the filters.

Filter with the two menus: **review** (All reviews, Unreviewed, Evidence, Not relevant) and **triage** (All triage, Relevant, Maybe, Not, Untriaged).

The order is: emails found by keyword, recipients or attachments before semantic-only ones, then emails inside the date range before those outside, then relevant, maybe, untriaged, not, and then newest first.

Each email shows its subject, date and sender, badges, the AI's reason and quote, and these controls:

- **Open** shows the full email.
- **Evidence** marks it as evidence. **Not relevant** sets it aside. **Reset** puts it back to unreviewed.
- **Note** and **Save note** attach your own comment. The note field saves only when you click the button.
- **Set quote**: paste a sentence copied from the email and click the button. It is saved only if that text really appears in the email (capitalization, spacing, curly quotes and reply markers `>` are ignored). Otherwise you see "That text isn't in the email." Your quote is used in the export in preference to the AI's.

Marking an email does not remove it from the list, so use the **Unreviewed** filter to see what is left. Use **Prev** and **Next** at the bottom for more pages (50 per page).

### Badges

| Badge | What it means |
|---|---|
| semantic only | Found only by meaning, not by any of your words. Lower confidence. |
| outside dates | Dated outside the case's From and To. |
| partial text | Longer than 6,000 characters, so the AI only read the start. |
| triage error: ... | The AI could not judge this email (for example the model was offline). It stays untriaged. Run triage again. |
| quote not found | The AI's quote is not in the email. Ignore it. |

## Find more

![Find more suggestions from your evidence](/help/case-find-more.png)

After you have marked some emails as **Evidence**, click **Find more from evidence**. The AI reads those emails and proposes new terms. It also lists people who appear in the evidence emails and are not yet in the case, with how many evidence emails they are on.

Tick the terms you want and click **Add selected**. Click **Add as person** next to a person to add them (this also adds their terms). Nothing is saved until you click, and added terms are not run until you click **Run** or **Run all**.

## Export ZIP

**Export ZIP** (top right) downloads `case-ID-DATE.zip` with only the emails you marked as **Evidence**:

- `README.md` explains how the search was done, so a reader can judge it. It lists counts (terms, runs, candidates, evidence, not yet triaged) and the method: what each search looked at, that semantic matches are the top 50 per term and lower confidence, that dates and people are hints and never filters, that AI triage only ordered the queue, and what `owner` and `model` quotes mean. When something went wrong it adds warnings: attachment text not indexed, search errors, runs that did not finish, semantic results capped, or originals unavailable.
- `evidence.csv` has one row per evidence email: date, from, to_cc, subject, quote, quote_source, note, found_by_terms, mailbox, email_id and eml_file.
- `timeline.html` is a printable timeline sorted by date.
- `eml/` holds the original messages exactly as stored.
- `search_log.csv` lists every search run, including retired terms.

> **Tip:** The export is a snapshot of the case right now. Export again after you change anything.

## Worked example A: one person, three topics

**Goal:** "Find every mention of Jordan Avery (nickname Jo) about performance, 1:1s or missed deadlines." (A made-up person at Harbor Lane Studios, whose addresses end in `harborlane.example`.)

1. **Create the case.** Name: `Jordan Avery follow-up`. Issue text: `Every mention of Jordan Avery (nickname Jo) at Harbor Lane Studios in connection with performance, one-on-one meetings (1:1s) or missed deadlines.` The topics go here, in the issue text, because triage reads it.
2. **Add the person.** In **People**, type `Jordan`, click Jordan Avery in the suggestions, then **Add**. QuackBox creates two terms: `Jordan Avery` and the email address.
3. **Add a few extra terms**, one at a time: `Avery`, `Jo Avery` and `Jordon` (a likely misspelling). `Avery` catches "Jordan M. Avery" and "Avery, Jordan", which the phrase `Jordan Avery` misses.
4. **Do not add** `performance`, `1:1` or `Jordan` on its own. Because each term runs alone, `performance` returns every email about anyone's performance, including server performance and box-office performance, and `1:1` returns every meeting invite. `Jordan` alone returns every Jordan. These would flood the queue. You cannot write "Avery AND performance". Instead, the topics are judged by triage from your issue text.
5. **Click Run all.** Look at the **Search log**: every row should say **ok**. Check the counts per channel. If the semantic column says `error`, open [Topics](/help/topics) and run clustering. If it says "semantic capped at 50", that is fine, just remember there may be more.
6. **Check the total** in the title of the **Review queue**.
7. **Click Start triage** and let it finish.
8. **Review.** Filter **triage** to **Relevant** and **review** to **Unreviewed**. Read the reason and the green verified quote, click **Open** if you need the whole email, then click **Evidence** or **Not relevant**. For the key emails, copy the exact sentence into **Set quote**. When done, repeat with **Maybe**.
9. **Click Find more from evidence** and add anything sensible, run it, triage again and review the new emails.
10. **Click Export ZIP** and read `README.md` first.

## Worked example B: a topic

**Goal:** "everything about the office move."

1. **Create the case.** Name: `Office move`. Issue: `All emails about Harbor Lane Studios moving offices: dates, movers, floor plans, desk assignments and announcements to staff.` Set **From** and **To** around the move period if you know it.
2. **Add specific terms** (no people needed yet): `office move`, `moving day`, `floor plan`, `desk assignments` and `reloc*`. Add `new office` as well, because `office move` will not match the words in the other order.
3. **Do not add** `office` or `move` alone. In a company almost every email contains them.
4. Click **Run all**, check the **Search log**, **Start triage** and review as in example A.
5. Use **Find more from evidence** to find the facilities manager and the movers' address, and add them with **Add as person**.

## Gotchas

- Many specific terms beat a few broad ones.
- Every term is a separate search with no AND or OR, unlike [Search](/help/search).
- No embeddings means no semantic results. Run [Topics](/help/topics) once.
- Index attachments in [Files](/help/files) or attachments are not searched.
- Duplicates that are used in a case are never deleted by [Duplicates](/help/duplicates).
