# Duplicates

Duplicates finds messages that were imported more than once, for example because the same email sits in two mailboxes, and lets you delete the extra copies.

## Controls

- **Scan for Duplicates** analyzes the archive. Run it again after importing more mail.
- Each group shows the copy that will be kept, marked **KEEP**, and the duplicates below it. Click a group to expand it. The tag says how the match was found:
  - **Exact duplicate**: same message ID.
  - **Same email, different source**: same sender, subject and date.
  - **Near-identical content**: same text.
- **Delete N** in a group removes that group's duplicates after you confirm.
- The **x** button says "these are not duplicates" and removes the group from the list.
- **Delete All Duplicates** removes every group's duplicates.

The oldest copy is always the one kept.

![Duplicate groups with the KEEP copy highlighted](/help/duplicates.png)

> **Careful:** Deleting removes the extra copies from QuackBox's database. It cannot be undone, but your original mail files are not touched, and a full re-scan on [Mailboxes](/help/mailboxes) would bring them back. Duplicates that are used in a [Case](/help/cases) are kept, and QuackBox tells you how many.

## Example

After importing two overlapping exports, click **Scan for Duplicates**, expand a group to check that the **KEEP** copy looks right, then click **Delete All Duplicates**.
