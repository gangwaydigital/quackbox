import AppKit
import Foundation

enum SystemMailbox: String, CaseIterable, Identifiable {
    case inbox = "Inbox"
    case sent = "Sent"
    case drafts = "Drafts"
    case archive = "Archive"
    case trash = "Trash"
    case all = "All Mail"
    case custom = "Custom"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .inbox: return "tray"
        case .sent: return "paperplane"
        case .drafts: return "doc"
        case .archive: return "archivebox"
        case .trash: return "trash"
        case .all: return "tray.full"
        case .custom: return "folder"
        }
    }
}

enum AppSection: String, CaseIterable, Identifiable {
    case dashboard = "Dashboard"
    case emails = "Emails"
    case search = "Search"
    case calendar = "Calendar"
    case timeline = "Timeline"
    case threads = "Threads"
    case contacts = "Contacts"
    case mailboxes = "Mailboxes"
    case files = "Files"
    case duplicates = "Duplicates"
    case topics = "Topics"
    case chat = "Chat"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .dashboard: return "chart.bar.xaxis"
        case .emails: return "envelope"
        case .search: return "line.3.horizontal.decrease.circle"
        case .calendar: return "calendar"
        case .timeline: return "clock"
        case .threads: return "text.bubble"
        case .contacts: return "person.2"
        case .mailboxes: return "square.stack.3d.down.right"
        case .files: return "paperclip"
        case .duplicates: return "doc.on.doc"
        case .topics: return "tag"
        case .chat: return "message"
        }
    }

    var webPath: String {
        switch self {
        case .dashboard: return "/"
        case .emails: return "/emails"
        case .search: return "/search"
        case .calendar: return "/calendar"
        case .timeline: return "/timeline"
        case .threads: return "/threads"
        case .contacts: return "/contacts"
        case .mailboxes: return "/mailboxes"
        case .files: return "/attachments"
        case .duplicates: return "/duplicates"
        case .topics: return "/topics"
        case .chat: return "/chat"
        }
    }
}

struct ThreadedEmailGroup: Identifiable, Hashable {
    let id: String
    let messages: [EmailListItem]

    var subject: String { messages.first?.subject ?? "(No Subject)" }
    var primary: EmailListItem? { messages.first }
    var count: Int { messages.count }
}

@MainActor
final class MailAppState: ObservableObject {
    @Published var selectedSection: AppSection = .emails
    @Published var mode: MailNavigationMode = .emails
    @Published var searchText: String = ""
    @Published var serverURLString: String
    @Published var webBaseURLString: String

    @Published var stats: StatsResponse?
    @Published var mailboxes: [MailboxItem] = []
    @Published var selectedMailbox: String?
    @Published var selectedSystemMailbox: SystemMailbox = .inbox

    @Published var accounts: [MailAccount] = []
    @Published var selectedAccountID: Int?
    @Published var accountForm = CreateAccountRequest(
        displayName: "",
        emailAddress: "",
        imapHost: "",
        imapPort: 993,
        imapSecurity: "ssl",
        imapUsername: "",
        imapPassword: nil,
        smtpHost: "",
        smtpPort: 587,
        smtpSecurity: "starttls",
        smtpUsername: "",
        smtpPassword: nil,
        oauthProvider: nil,
        oauthClientID: nil,
        oauthClientSecret: nil,
        oauthRefreshToken: nil,
        oauthAccessToken: nil,
        oauthTokenURL: nil,
        oauthExpiresAt: nil,
        enabled: true
    )

    @Published var emails: [EmailListItem] = []
    @Published var selectedEmailID: Int?
    @Published var selectedEmailDetail: EmailDetail?

    @Published var threads: [ThreadListItem] = []
    @Published var filteredThreads: [ThreadListItem] = []
    @Published var selectedThreadID: Int?
    @Published var selectedThreadDetail: ThreadDetail?

    @Published var showThreadedList = true
    @Published var sidebarColumnWidth: CGFloat = 260
    @Published var listColumnWidth: CGFloat = 430
    @Published var preferences = AppPreferences()

    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var composeDraft: ComposeDraft?

    private var searchTask: Task<Void, Never>?
    private var archivedEmailIDs = Set<Int>()
    private var seenEmailIDs = Set<Int>()
    private var unreadEmailIDs = Set<Int>()
    private var forcedJunkEmailIDs = Set<Int>()
    private var collapsedThreadKeys = Set<String>()
    private var allFetchedEmails: [EmailListItem] = []
    private let localStore = LocalStore()

    init() {
        self.serverURLString = UserDefaults.standard.string(forKey: Self.serverURLKey) ?? Self.defaultURLString
        self.webBaseURLString = UserDefaults.standard.string(forKey: Self.webBaseURLKey) ?? Self.defaultWebURLString
        self.preferences = Self.loadPreferences()
        if preferences.defaultSignatureID == nil {
            self.preferences.defaultSignatureID = preferences.signatures.first?.id
            Self.savePreferences(self.preferences)
        }
        self.showThreadedList = preferences.useThreadedViewByDefault
        loadCachedState()
    }

    func loadInitialData() async {
        if preferences.allowNotifications {
            await NotificationService.shared.requestAuthorizationIfNeeded()
        }
        await refreshAll()
    }

    func refreshAll() async {
        isLoading = true
        defer { isLoading = false }

        do {
            async let statsCall = api.fetchStats()
            async let mailboxesCall = api.fetchMailboxes()
            async let emailsCall = api.fetchEmails(search: searchText, mailbox: serverMailboxFilter)
            async let threadsCall = api.fetchThreads()

            stats = try await statsCall
            mailboxes = try await mailboxesCall
            do {
                accounts = try await api.fetchAccounts()
                if selectedAccountID == nil {
                    selectedAccountID = accounts.first?.id
                }
            } catch {
                // Keep mail UX available even if account endpoint has bad payloads.
                accounts = []
            }

            let emailPage = try await emailsCall
            allFetchedEmails = emailPage.items
            applyEmailVisibility(emailPage.items)
            if selectedEmailID == nil {
                selectedEmailID = visibleEmailSequence().first?.id
            }
            if let selectedEmailID {
                await loadEmailDetail(id: selectedEmailID)
            }

            let threadPage = try await threadsCall
            threads = threadPage.items
            applyThreadSearchFilter()
            if selectedThreadID == nil {
                selectedThreadID = filteredThreads.first?.id
            }
            if mode == .threads, let selectedThreadID {
                await loadThreadDetail(id: selectedThreadID)
            }

            detectAndNotifyNewMessages(from: emailPage.items)
            persistState()
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
            if stats == nil {
                loadCachedState()
            }
        }
    }

    func setServerURL(_ input: String) async {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard URL(string: trimmed) != nil else {
            errorMessage = "Invalid server URL. Use something like http://127.0.0.1:8000"
            return
        }

        serverURLString = trimmed
        UserDefaults.standard.set(trimmed, forKey: Self.serverURLKey)
        await refreshAll()
    }

    func setWebBaseURL(_ input: String) {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard URL(string: trimmed) != nil else {
            errorMessage = "Invalid web URL. Use something like http://127.0.0.1:5173"
            return
        }
        webBaseURLString = trimmed
        UserDefaults.standard.set(trimmed, forKey: Self.webBaseURLKey)
    }

    func setPreferences(_ updated: AppPreferences) {
        preferences = updated
        savePreferences()
        if !updated.rulesEnabled {
            forcedJunkEmailIDs.removeAll()
        }
        showThreadedList = updated.useThreadedViewByDefault
        applyEmailVisibility(allFetchedEmails)
    }

    func selectSection(_ section: AppSection) {
        selectedSection = section
        switch section {
        case .emails:
            mode = .emails
        case .threads:
            mode = .threads
        default:
            break
        }
    }

    func onSearchChanged() {
        searchTask?.cancel()
        searchTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 280_000_000)
            guard !Task.isCancelled else { return }
            await self?.reloadForCurrentMode()
        }
    }

    func reloadForCurrentMode() async {
        isLoading = true
        defer { isLoading = false }

        do {
            switch mode {
            case .emails:
                let page = try await api.fetchEmails(search: searchText, mailbox: serverMailboxFilter)
                allFetchedEmails = page.items
                applyEmailVisibility(page.items)
                let nextSelection = selectedEmailID.flatMap { id in
                    visibleEmailSequence().contains(where: { $0.id == id }) ? id : nil
                } ?? visibleEmailSequence().first?.id
                selectedEmailID = nextSelection
                if let nextSelection {
                    await loadEmailDetail(id: nextSelection)
                } else {
                    selectedEmailDetail = nil
                }

            case .threads:
                let page = try await api.fetchThreads()
                threads = page.items
                applyThreadSearchFilter()
                let nextSelection = selectedThreadID.flatMap { id in
                    filteredThreads.contains(where: { $0.id == id }) ? id : nil
                } ?? filteredThreads.first?.id
                selectedThreadID = nextSelection
                if let nextSelection {
                    await loadThreadDetail(id: nextSelection)
                } else {
                    selectedThreadDetail = nil
                }
            }
            persistState()
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func selectSystemMailbox(_ mailbox: SystemMailbox) {
        selectedSystemMailbox = mailbox
        if mailbox != .custom {
            selectedMailbox = nil
        }
        Task { await reloadForCurrentMode() }
    }

    func selectCustomMailbox(_ mailbox: String) {
        selectedSystemMailbox = .custom
        selectedMailbox = mailbox
        Task { await reloadForCurrentMode() }
    }

    func selectEmail(_ email: EmailListItem?) {
        guard let email else {
            selectedEmailID = nil
            selectedEmailDetail = nil
            return
        }

        selectedEmailID = email.id
        unreadEmailIDs.remove(email.id)
        Task { await loadEmailDetail(id: email.id) }
    }

    func selectThread(_ thread: ThreadListItem?) {
        guard let thread else {
            selectedThreadID = nil
            selectedThreadDetail = nil
            return
        }

        selectedThreadID = thread.id
        Task { await loadThreadDetail(id: thread.id) }
    }

    func composeNew() {
        var draft = ComposeDraft(accountID: selectedAccountID)
        if preferences.includeSignatureOnNew {
            draft = appendSignature(to: draft, isReply: false)
        }
        composeDraft = draft
    }

    func replyToCurrentEmail() {
        guard let detail = selectedEmailDetail else { return }
        var draft = ComposeDraft(accountID: selectedAccountID)
        draft.to = detail.senderEmail ?? ""
        draft.subject = replySubject(from: detail.subject)
        draft.body = "\n\nOn \(detail.dateSent ?? ""), \(detail.senderName ?? detail.senderEmail ?? "") wrote:\n\(detail.bodyText ?? "")"
        if preferences.includeSignatureOnReply {
            draft = appendSignature(to: draft, isReply: true)
        }
        composeDraft = draft
    }

    func forwardCurrentEmail() {
        guard let detail = selectedEmailDetail else { return }
        var draft = ComposeDraft(accountID: selectedAccountID)
        draft.subject = forwardSubject(from: detail.subject)
        draft.body = "\n\n---------- Forwarded message ----------\nFrom: \(detail.senderName ?? detail.senderEmail ?? "")\nDate: \(detail.dateSent ?? "")\nSubject: \(detail.subject ?? "")\n\n\(detail.bodyText ?? "")"
        if preferences.includeSignatureOnReply {
            draft = appendSignature(to: draft, isReply: true)
        }
        composeDraft = draft
    }

    func archiveCurrentEmail() {
        guard let id = selectedEmailID else { return }
        archivedEmailIDs.insert(id)
        applyEmailVisibility(allFetchedEmails)
        if selectedEmailID == id {
            selectedEmailID = visibleEmailSequence().first?.id
            if let next = selectedEmailID {
                Task { await loadEmailDetail(id: next) }
            } else {
                selectedEmailDetail = nil
            }
        }
        persistState()
    }

    func syncSelectedAccount() async {
        guard let accountID = selectedAccountID else {
            errorMessage = "Select an account to sync."
            return
        }

        isLoading = true
        defer { isLoading = false }

        do {
            _ = try await api.syncAccount(accountID: accountID, folder: "INBOX", limit: 250)
            await refreshAll()
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func addAccount() async {
        isLoading = true
        defer { isLoading = false }

        do {
            let created = try await api.createAccount(accountForm)
            accounts.insert(created, at: 0)
            selectedAccountID = created.id
            clearAccountForm()
            persistState()
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func updateAccount(accountID: Int, form: CreateAccountRequest) async {
        isLoading = true
        defer { isLoading = false }

        let patch = AccountPatchRequest(
            displayName: form.displayName,
            emailAddress: form.emailAddress,
            imapHost: form.imapHost,
            imapPort: form.imapPort,
            imapSecurity: form.imapSecurity,
            imapUsername: form.imapUsername,
            imapPassword: form.imapPassword?.isEmpty == true ? nil : form.imapPassword,
            smtpHost: form.smtpHost,
            smtpPort: form.smtpPort,
            smtpSecurity: form.smtpSecurity,
            smtpUsername: form.smtpUsername,
            smtpPassword: form.smtpPassword?.isEmpty == true ? nil : form.smtpPassword,
            oauthProvider: form.oauthProvider,
            oauthClientID: form.oauthClientID,
            oauthClientSecret: form.oauthClientSecret,
            oauthRefreshToken: form.oauthRefreshToken,
            oauthAccessToken: form.oauthAccessToken,
            oauthTokenURL: form.oauthTokenURL,
            oauthExpiresAt: form.oauthExpiresAt,
            enabled: form.enabled
        )

        do {
            let updated = try await api.updateAccount(accountID: accountID, request: patch)
            if let idx = accounts.firstIndex(where: { $0.id == accountID }) {
                accounts[idx] = updated
            } else {
                accounts.insert(updated, at: 0)
            }
            selectedAccountID = updated.id
            persistState()
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func deleteAccount(accountID: Int) async {
        isLoading = true
        defer { isLoading = false }

        do {
            try await api.deleteAccount(accountID: accountID)
            accounts.removeAll { $0.id == accountID }
            if selectedAccountID == accountID {
                selectedAccountID = accounts.first?.id
            }
            persistState()
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func sendDraft(_ draft: ComposeDraft) async {
        guard let accountID = draft.accountID ?? selectedAccountID else {
            errorMessage = "Select an account before sending."
            return
        }

        let to = splitEmails(draft.to)
        let cc = splitEmails(draft.cc)
        let bcc = splitEmails(draft.bcc)
        if to.isEmpty {
            errorMessage = "Recipient is required."
            return
        }

        isLoading = true
        defer { isLoading = false }

        do {
            _ = try await api.sendEmail(
                accountID: accountID,
                request: SendEmailRequest(
                    to: to,
                    cc: cc,
                    bcc: bcc,
                    subject: draft.subject,
                    bodyText: draft.body,
                    bodyHTML: preferences.composeInRichText ? draft.bodyHTML : nil
                )
            )
            composeDraft = nil
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func saveAttachmentFromSelectedEmail(filename: String) {
        guard let detail = selectedEmailDetail,
              let url = api.attachmentDownloadURL(emailID: detail.id, filename: filename)
        else {
            errorMessage = "Attachment URL unavailable."
            return
        }

        let panel = NSSavePanel()
        panel.nameFieldStringValue = filename
        panel.canCreateDirectories = true
        if panel.runModal() != .OK || panel.url == nil {
            return
        }
        guard let destination = panel.url else { return }

        Task {
            do {
                let (tempURL, response) = try await URLSession.shared.download(from: url)
                guard let http = response as? HTTPURLResponse, (200 ..< 300).contains(http.statusCode) else {
                    throw NSError(domain: "QuackBoxNative", code: 1, userInfo: [NSLocalizedDescriptionKey: "Download failed"])
                }
                try? FileManager.default.removeItem(at: destination)
                try FileManager.default.moveItem(at: tempURL, to: destination)
                NSWorkspace.shared.activateFileViewerSelecting([destination])
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }

    // MARK: - Mail-like list behavior

    func toggleThreadedList() {
        showThreadedList.toggle()
    }

    func threadedGroups() -> [ThreadedEmailGroup] {
        var grouped = [String: [EmailListItem]]()
        var order = [String]()

        for email in emails {
            let key = threadKey(for: email)
            if grouped[key] == nil {
                grouped[key] = []
                order.append(key)
            }
            grouped[key]?.append(email)
        }

        return order.compactMap { key in
            guard let messages = grouped[key], !messages.isEmpty else { return nil }
            return ThreadedEmailGroup(id: key, messages: messages)
        }
    }

    func isThreadCollapsed(_ key: String) -> Bool {
        collapsedThreadKeys.contains(key)
    }

    func toggleThreadCollapse(_ key: String) {
        if collapsedThreadKeys.contains(key) {
            collapsedThreadKeys.remove(key)
        } else {
            collapsedThreadKeys.insert(key)
        }
    }

    func unreadCount(for mailbox: SystemMailbox) -> Int {
        filteredEmails(for: mailbox, mailboxName: nil)
            .filter { unreadEmailIDs.contains($0.id) && !archivedEmailIDs.contains($0.id) }
            .count
    }

    func unreadCount(in group: ThreadedEmailGroup) -> Int {
        group.messages.filter { unreadEmailIDs.contains($0.id) }.count
    }

    func isUnread(_ emailID: Int) -> Bool {
        unreadEmailIDs.contains(emailID)
    }

    func displayDate(for raw: String?) -> String {
        guard let raw else { return "" }
        let formatter = ISO8601DateFormatter()
        guard let dt = formatter.date(from: raw) else { return raw }

        if Calendar.current.isDateInToday(dt) {
            let time = DateFormatter()
            time.dateStyle = .none
            time.timeStyle = .short
            return time.string(from: dt)
        }

        let date = DateFormatter()
        date.dateStyle = .short
        date.timeStyle = .none
        return date.string(from: dt)
    }

    func selectNextMessage() {
        selectRelativeMessage(step: 1)
    }

    func selectPreviousMessage() {
        selectRelativeMessage(step: -1)
    }

    func selectNextConversation() {
        if mode == .threads {
            selectRelativeThread(step: 1)
            return
        }
        selectRelativeConversation(step: 1)
    }

    func selectPreviousConversation() {
        if mode == .threads {
            selectRelativeThread(step: -1)
            return
        }
        selectRelativeConversation(step: -1)
    }

    func widenMessageList() {
        listColumnWidth = min(760, listColumnWidth + 30)
    }

    func narrowMessageList() {
        listColumnWidth = max(320, listColumnWidth - 30)
    }

    func widenSidebar() {
        sidebarColumnWidth = min(420, sidebarColumnWidth + 20)
    }

    func narrowSidebar() {
        sidebarColumnWidth = max(200, sidebarColumnWidth - 20)
    }

    private func selectRelativeMessage(step: Int) {
        let visible = visibleEmailSequence()
        guard !visible.isEmpty else { return }

        if selectedEmailID == nil {
            selectEmail(visible.first)
            return
        }

        guard let currentID = selectedEmailID,
              let index = visible.firstIndex(where: { $0.id == currentID }) else {
            selectEmail(visible.first)
            return
        }

        let target = max(0, min(visible.count - 1, index + step))
        if target != index {
            selectEmail(visible[target])
        }
    }

    private func selectRelativeConversation(step: Int) {
        let groups = threadedGroups()
        guard !groups.isEmpty else { return }

        let selectedKey = selectedEmailID.flatMap { id in
            emails.first(where: { $0.id == id }).map(threadKey)
        }

        let currentIndex = selectedKey.flatMap { key in groups.firstIndex(where: { $0.id == key }) } ?? 0
        let target = max(0, min(groups.count - 1, currentIndex + step))
        if let email = groups[target].primary {
            selectEmail(email)
        }
    }

    private func selectRelativeThread(step: Int) {
        guard !filteredThreads.isEmpty else { return }
        if selectedThreadID == nil {
            selectThread(filteredThreads.first)
            return
        }
        guard let currentID = selectedThreadID,
              let index = filteredThreads.firstIndex(where: { $0.id == currentID }) else {
            selectThread(filteredThreads.first)
            return
        }
        let target = max(0, min(filteredThreads.count - 1, index + step))
        if target != index {
            selectThread(filteredThreads[target])
        }
    }

    private func visibleEmailSequence() -> [EmailListItem] {
        if !showThreadedList {
            return emails
        }

        var visible = [EmailListItem]()
        for group in threadedGroups() {
            if let first = group.primary {
                visible.append(first)
            }
            if !isThreadCollapsed(group.id), group.messages.count > 1 {
                visible.append(contentsOf: group.messages.dropFirst())
            }
        }
        return visible
    }

    private func threadKey(for email: EmailListItem) -> String {
        if let threadID = email.threadGroupID {
            return "thread:\(threadID)"
        }
        return "single:\(email.id)"
    }

    private func loadEmailDetail(id: Int) async {
        do {
            selectedEmailDetail = try await api.fetchEmailDetail(id: id)
            persistState()
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func loadThreadDetail(id: Int) async {
        do {
            selectedThreadDetail = try await api.fetchThreadDetail(id: id)
            persistState()
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func applyThreadSearchFilter() {
        let q = searchText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty else {
            filteredThreads = threads
            return
        }

        let lowered = q.lowercased()
        filteredThreads = threads.filter {
            let subject = ($0.originalSubject ?? $0.subjectNormalized ?? "").lowercased()
            return subject.contains(lowered)
        }
    }

    private func applyEmailVisibility(_ source: [EmailListItem]) {
        applyRules(to: source)
        emails = filteredEmails(for: selectedSystemMailbox, mailboxName: selectedMailbox).filter {
            !archivedEmailIDs.contains($0.id)
        }
    }

    private func filteredEmails(for mailbox: SystemMailbox, mailboxName: String?) -> [EmailListItem] {
        let source = allFetchedEmails
        switch mailbox {
        case .all:
            return source.filter { !preferences.hideJunkFromInbox || !isJunk($0) }
        case .custom:
            guard let mailboxName else { return source }
            return source.filter { ($0.mboxSource ?? "") == mailboxName }
        case .inbox:
            return source.filter {
                sourceName($0).contains("inbox") &&
                (!preferences.hideJunkFromInbox || !isJunk($0))
            }
        case .sent:
            return source.filter { sourceName($0).contains("sent") }
        case .drafts:
            return source.filter { sourceName($0).contains("draft") }
        case .archive:
            return source.filter { sourceName($0).contains("archive") }
        case .trash:
            return source.filter { sourceName($0).contains("trash") || sourceName($0).contains("bin") }
        }
    }

    private func sourceName(_ email: EmailListItem) -> String {
        (email.mboxSource ?? "").lowercased()
    }

    private func detectAndNotifyNewMessages(from source: [EmailListItem]) {
        let incomingIDs = Set(source.map(\.id))
        let new = incomingIDs.subtracting(seenEmailIDs)
        if preferences.allowNotifications, !seenEmailIDs.isEmpty, !new.isEmpty {
            unreadEmailIDs.formUnion(new)
            let latestSubject = source.first(where: { new.contains($0.id) })?.subject
            NotificationService.shared.postNewMailSummary(count: new.count, latestSubject: latestSubject)
        }
        seenEmailIDs.formUnion(incomingIDs)
    }

    private var serverMailboxFilter: String? {
        selectedSystemMailbox == .custom ? selectedMailbox : nil
    }

    private func persistState() {
        let snapshot = CachedSnapshot(
            stats: stats,
            mailboxes: mailboxes,
            emails: allFetchedEmails,
            threads: threads,
            selectedEmailDetail: selectedEmailDetail,
            selectedThreadDetail: selectedThreadDetail,
            accounts: accounts,
            archivedEmailIDs: Array(archivedEmailIDs),
            seenEmailIDs: Array(seenEmailIDs),
            unreadEmailIDs: Array(unreadEmailIDs),
            savedAt: ISO8601DateFormatter().string(from: Date())
        )
        localStore.save(snapshot)
    }

    private func loadCachedState() {
        guard let snapshot = localStore.load() else { return }
        stats = snapshot.stats
        mailboxes = snapshot.mailboxes
        allFetchedEmails = snapshot.emails
        emails = snapshot.emails
        threads = snapshot.threads
        selectedEmailDetail = snapshot.selectedEmailDetail
        selectedThreadDetail = snapshot.selectedThreadDetail
        accounts = snapshot.accounts
        archivedEmailIDs = Set(snapshot.archivedEmailIDs)
        seenEmailIDs = Set(snapshot.seenEmailIDs)
        unreadEmailIDs = Set(snapshot.unreadEmailIDs)
        selectedEmailID = snapshot.selectedEmailDetail?.id ?? snapshot.emails.first?.id
        selectedThreadID = snapshot.selectedThreadDetail?.id ?? snapshot.threads.first?.id
        filteredThreads = threads
    }

    private func splitEmails(_ raw: String) -> [String] {
        raw
            .split(whereSeparator: { $0 == "," || $0 == ";" || $0 == " " || $0 == "\n" || $0 == "\t" })
            .map { String($0).trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }

    private func clearAccountForm() {
        accountForm = CreateAccountRequest(
            displayName: "",
            emailAddress: "",
            imapHost: "",
            imapPort: 993,
            imapSecurity: "ssl",
            imapUsername: "",
            imapPassword: nil,
            smtpHost: "",
            smtpPort: 587,
            smtpSecurity: "starttls",
            smtpUsername: "",
            smtpPassword: nil,
            oauthProvider: nil,
            oauthClientID: nil,
            oauthClientSecret: nil,
            oauthRefreshToken: nil,
            oauthAccessToken: nil,
            oauthTokenURL: nil,
            oauthExpiresAt: nil,
            enabled: true
        )
    }

    private func replySubject(from original: String?) -> String {
        let subject = (original ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        if subject.lowercased().hasPrefix("re:") { return subject }
        return "Re: \(subject.isEmpty ? "(No Subject)" : subject)"
    }

    private func forwardSubject(from original: String?) -> String {
        let subject = (original ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        if subject.lowercased().hasPrefix("fwd:") || subject.lowercased().hasPrefix("fw:") { return subject }
        return "Fwd: \(subject.isEmpty ? "(No Subject)" : subject)"
    }

    private var api: QuackBoxAPI {
        QuackBoxAPI(baseURL: URL(string: serverURLString) ?? URL(string: Self.defaultURLString)!)
    }

    private func appendSignature(to draft: ComposeDraft, isReply: Bool) -> ComposeDraft {
        guard let signature = activeSignature else { return draft }
        var next = draft
        if signature.isHTML {
            let existing = draft.bodyHTML ?? draft.body
            let separator = isReply ? "<br><br>" : "<br><br>"
            next.bodyHTML = existing + separator + signature.body
            next.body = NSAttributedString.fromHTMLString(next.bodyHTML ?? "").string
        } else {
            next.body += "\n\n" + signature.body
        }
        return next
    }

    var activeSignature: SignatureItem? {
        if let id = preferences.defaultSignatureID,
           let sig = preferences.signatures.first(where: { $0.id == id }) {
            return sig
        }
        return preferences.signatures.first
    }

    func addSignature(name: String, body: String, isHTML: Bool) {
        var updated = preferences
        let item = SignatureItem(name: name, body: body, isHTML: isHTML)
        updated.signatures.append(item)
        if updated.defaultSignatureID == nil {
            updated.defaultSignatureID = item.id
        }
        setPreferences(updated)
    }

    func updateSignature(_ item: SignatureItem) {
        var updated = preferences
        guard let idx = updated.signatures.firstIndex(where: { $0.id == item.id }) else { return }
        updated.signatures[idx] = item
        setPreferences(updated)
    }

    func deleteSignature(id: UUID) {
        var updated = preferences
        updated.signatures.removeAll { $0.id == id }
        if updated.defaultSignatureID == id {
            updated.defaultSignatureID = updated.signatures.first?.id
        }
        setPreferences(updated)
    }

    func addRule(name: String, field: RuleField, contains: String, action: RuleAction) {
        var updated = preferences
        updated.rules.append(MailRule(name: name, field: field, contains: contains, action: action))
        setPreferences(updated)
    }

    func updateRule(_ rule: MailRule) {
        var updated = preferences
        guard let idx = updated.rules.firstIndex(where: { $0.id == rule.id }) else { return }
        updated.rules[idx] = rule
        setPreferences(updated)
    }

    func deleteRule(id: UUID) {
        var updated = preferences
        updated.rules.removeAll { $0.id == id }
        setPreferences(updated)
    }

    func isJunk(_ email: EmailListItem) -> Bool {
        if forcedJunkEmailIDs.contains(email.id) { return true }
        let source = sourceName(email)
        if source.contains("junk") || source.contains("spam") { return true }
        guard preferences.junkFilterEnabled else { return false }
        let sender = (email.senderEmail ?? "").lowercased()
        let subject = (email.subject ?? "").lowercased()
        let snippet = (email.snippet ?? "").lowercased()
        let blocked = csvList(from: preferences.blockedSendersRaw)
        if blocked.contains(where: { token in !token.isEmpty && sender.contains(token) }) {
            return true
        }
        let keywords = csvList(from: preferences.junkKeywordsRaw)
        if keywords.contains(where: { token in
            !token.isEmpty && (subject.contains(token) || snippet.contains(token))
        }) {
            return true
        }
        return false
    }

    private func applyRules(to source: [EmailListItem]) {
        guard preferences.rulesEnabled else { return }
        for email in source {
            for rule in preferences.rules where rule.enabled {
                if !ruleMatches(rule, email: email) {
                    continue
                }
                switch rule.action {
                case .archive:
                    archivedEmailIDs.insert(email.id)
                case .markRead:
                    unreadEmailIDs.remove(email.id)
                case .markUnread:
                    unreadEmailIDs.insert(email.id)
                case .markJunk:
                    forcedJunkEmailIDs.insert(email.id)
                }
                if !rule.continueEvaluating {
                    break
                }
            }
        }
    }

    private func ruleMatches(_ rule: MailRule, email: EmailListItem) -> Bool {
        let needle = rule.contains.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !needle.isEmpty else { return false }
        let haystack: String
        switch rule.field {
        case .sender:
            haystack = (email.senderEmail ?? email.senderName ?? "").lowercased()
        case .subject:
            haystack = (email.subject ?? "").lowercased()
        case .snippet:
            haystack = (email.snippet ?? "").lowercased()
        }
        return haystack.contains(needle)
    }

    private func csvList(from raw: String) -> [String] {
        raw.split(whereSeparator: { $0 == "," || $0 == ";" || $0 == "\n" })
            .map { String($0).trimmingCharacters(in: .whitespacesAndNewlines).lowercased() }
            .filter { !$0.isEmpty }
    }

    private func savePreferences() {
        Self.savePreferences(preferences)
    }

    private static func loadPreferences() -> AppPreferences {
        guard let data = UserDefaults.standard.data(forKey: preferencesKey),
              let decoded = try? JSONDecoder().decode(AppPreferences.self, from: data) else {
            return AppPreferences()
        }
        return decoded
    }

    private static func savePreferences(_ preferences: AppPreferences) {
        guard let data = try? JSONEncoder().encode(preferences) else { return }
        UserDefaults.standard.set(data, forKey: preferencesKey)
    }

    private static let defaultURLString = "http://127.0.0.1:8000"
    private static let serverURLKey = "quackbox.macos.server_url"
    private static let defaultWebURLString = "http://127.0.0.1:5173"
    private static let webBaseURLKey = "quackbox.macos.web_url"
    private static let preferencesKey = "quackbox.macos.preferences"
}
