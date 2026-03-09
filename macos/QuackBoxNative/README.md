# QuackBox Native (macOS)

Native SwiftUI macOS client for QuackBox.

## What it includes

- Native three-pane mail UI (`NavigationSplitView`)
- Live backend-driven email search and mailbox filtering
- Native thread list and thread detail view
- Message detail view with recipients and attachment list
- Native app settings for backend URL switching
- Account management (IMAP/SMTP + optional OAuth refresh settings)
- One-click IMAP sync for selected account
- Native compose/send via backend SMTP endpoint
- Offline cache of mailbox/message/thread snapshots
- Native notifications for newly synced messages
- Message actions: reply, forward, archive (local hide)
- Attachment save flow (`Save As…`) from message detail

## Run

1. Install backend dependencies once:

```bash
cd /Users/marc/Desktop/003-AI/07-home_project/git/quackbox/backend
python3 -m pip install -r requirements.txt
```

2. Open the Swift package in Xcode:

- File > Open
- Select `/Users/marc/Desktop/003-AI/07-home_project/git/quackbox/macos/QuackBoxNative/Package.swift`
- Choose the `QuackBoxNative` run target
- Run

The app auto-starts the local backend on `http://127.0.0.1:8000` when launching.

## Notes

- The app is optimized for macOS 26+.
- The native client uses your existing FastAPI API; no schema changes required.
- IMAP sync currently pulls recent messages from `INBOX` and ingests them into the existing `emails` table.
