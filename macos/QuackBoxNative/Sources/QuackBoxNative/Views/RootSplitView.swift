import SwiftUI

struct RootSplitView: View {
    @EnvironmentObject private var state: MailAppState

    private var isNativeMailSection: Bool {
        state.selectedSection == .emails || state.selectedSection == .threads
    }

    var body: some View {
        Group {
            if isNativeMailSection {
                NavigationSplitView {
                    SidebarView()
                        .navigationSplitViewColumnWidth(min: 200, ideal: state.sidebarColumnWidth, max: 420)
                } content: {
                    ContentListView()
                        .navigationSplitViewColumnWidth(min: 320, ideal: state.listColumnWidth, max: 760)
                } detail: {
                    DetailPaneView()
                }
            } else {
                NavigationSplitView {
                    SidebarView()
                        .navigationSplitViewColumnWidth(min: 200, ideal: state.sidebarColumnWidth, max: 420)
                } detail: {
                    WebModuleView(baseURLString: state.webBaseURLString, path: state.selectedSection.webPath)
                }
            }
        }
        .searchable(text: $state.searchText, placement: .toolbar, prompt: state.mode == .emails ? "Search Mail" : "Search Threads")
        .onChange(of: state.searchText) { _, _ in
            if isNativeMailSection {
                state.onSearchChanged()
            }
        }
        .toolbar {
            ToolbarItemGroup(placement: .navigation) {
                if isNativeMailSection {
                    Picker("Mode", selection: $state.mode) {
                        ForEach(MailNavigationMode.allCases) { mode in
                            Text(mode.rawValue).tag(mode)
                        }
                    }
                    .pickerStyle(.segmented)
                    .frame(width: 180)
                    .onChange(of: state.mode) { _, mode in
                        state.selectSection(mode == .emails ? .emails : .threads)
                        Task { await state.reloadForCurrentMode() }
                    }

                    if state.mode == .emails {
                        Toggle("Threads", isOn: $state.showThreadedList)
                            .toggleStyle(.switch)
                            .frame(width: 108)
                    }
                } else {
                    Label(state.selectedSection.rawValue, systemImage: state.selectedSection.icon)
                }
            }

            ToolbarItemGroup {
                if isNativeMailSection {
                    Button { state.composeNew() } label: {
                        Label("Compose", systemImage: "square.and.pencil")
                    }

                    Button { Task { await state.syncSelectedAccount() } } label: {
                        Label("Get Mail", systemImage: "arrow.clockwise.circle")
                    }
                }

                Button { Task { await state.reloadForCurrentMode() } } label: {
                    Label("Refresh", systemImage: "arrow.clockwise")
                }
                .keyboardShortcut("r", modifiers: [.command])
            }
        }
        .overlay(alignment: .bottomLeading) {
            if let errorMessage = state.errorMessage {
                Text(errorMessage)
                    .font(.caption)
                    .foregroundStyle(.red)
                    .padding(10)
                    .background(.ultraThinMaterial)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    .padding()
            }
        }
        .sheet(item: $state.composeDraft) { _ in
            ComposeView()
                .environmentObject(state)
                .frame(minWidth: 760, minHeight: 620)
        }
    }
}

private struct SidebarView: View {
    @EnvironmentObject private var state: MailAppState

    var body: some View {
        List {
            Section("App") {
                ForEach(AppSection.allCases) { section in
                    Button {
                        state.selectSection(section)
                    } label: {
                        Label(section.rawValue, systemImage: section.icon)
                            .font(state.selectedSection == section ? .headline : .body)
                    }
                    .buttonStyle(.plain)
                }
            }

            if state.selectedSection == .emails {
                Section("Accounts") {
                    Picker("Active Account", selection: Binding(
                        get: { state.selectedAccountID },
                        set: { state.selectedAccountID = $0 }
                    )) {
                        Text("None").tag(Optional<Int>.none)
                        ForEach(state.accounts) { account in
                            Text(account.emailAddress).tag(Optional(account.id))
                        }
                    }
                    .pickerStyle(.menu)
                }

                Section("Favorites") {
                    ForEach([SystemMailbox.inbox, .sent, .drafts, .archive, .trash, .all], id: \.self) { mailbox in
                        Button {
                            state.selectSystemMailbox(mailbox)
                        } label: {
                            HStack {
                                Label(mailbox.rawValue, systemImage: mailbox.icon)
                                Spacer()
                                let unread = state.unreadCount(for: mailbox)
                                if unread > 0 {
                                    Text("\(unread)")
                                        .font(.caption2)
                                        .padding(.horizontal, 6)
                                        .padding(.vertical, 2)
                                        .background(Capsule().fill(Color.blue.opacity(0.18)))
                                }
                            }
                        }
                        .buttonStyle(.plain)
                        .font(state.selectedSystemMailbox == mailbox ? .headline : .body)
                    }
                }

                Section("Folders") {
                    ForEach(state.mailboxes) { mailbox in
                        Button {
                            state.selectCustomMailbox(mailbox.mboxSource)
                        } label: {
                            HStack {
                                Label(mailbox.mboxSource, systemImage: "folder")
                                Spacer()
                                Text("\(mailbox.count)")
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .buttonStyle(.plain)
                        .font(state.selectedMailbox == mailbox.mboxSource && state.selectedSystemMailbox == .custom ? .headline : .body)
                    }
                }
            }
        }
        .listStyle(.sidebar)
    }
}

private struct ContentListView: View {
    @EnvironmentObject private var state: MailAppState

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(headerTitle)
                    .font(.title3)
                    .fontWeight(.semibold)
                Spacer()
                Text("\(countValue)")
                    .foregroundStyle(.secondary)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(.bar)

            Group {
                if state.selectedSection == .emails {
                    if state.showThreadedList {
                        ThreadedEmailList()
                    } else {
                        FlatEmailList()
                    }
                } else {
                    ThreadList()
                }
            }
        }
        .overlay {
            if state.isLoading {
                ProgressView()
                    .controlSize(.large)
            }
        }
    }

    private var headerTitle: String {
        if state.selectedSection == .threads { return "Threads" }
        if state.selectedSystemMailbox == .custom {
            return state.selectedMailbox ?? "Mailbox"
        }
        return state.selectedSystemMailbox.rawValue
    }

    private var countValue: Int {
        if state.selectedSection == .emails { return state.emails.count }
        return state.filteredThreads.count
    }
}

private struct FlatEmailList: View {
    @EnvironmentObject private var state: MailAppState

    var body: some View {
        List(selection: Binding(
            get: { state.selectedEmailID },
            set: { next in
                guard let next else {
                    state.selectEmail(nil)
                    return
                }
                state.selectEmail(state.emails.first(where: { $0.id == next }))
            }
        )) {
            ForEach(state.emails) { email in
                EmailRow(email: email)
                    .tag(email.id)
            }
        }
        .listStyle(.inset)
    }
}

private struct ThreadedEmailList: View {
    @EnvironmentObject private var state: MailAppState

    var body: some View {
        List(selection: Binding(
            get: { state.selectedEmailID },
            set: { next in
                guard let next else {
                    state.selectEmail(nil)
                    return
                }
                let groups = state.threadedGroups()
                let email = groups.flatMap(\.messages).first(where: { $0.id == next })
                state.selectEmail(email)
            }
        )) {
            ForEach(state.threadedGroups()) { group in
                if let primary = group.primary {
                    ThreadSummaryRow(group: group, primary: primary)
                        .tag(primary.id)

                    if !state.isThreadCollapsed(group.id) {
                        ForEach(Array(group.messages.dropFirst())) { email in
                            HStack(spacing: 10) {
                                Image(systemName: "arrow.turn.down.right")
                                    .font(.caption)
                                    .foregroundStyle(.tertiary)
                                EmailRow(email: email)
                            }
                            .padding(.leading, 16)
                            .tag(email.id)
                        }
                    }
                }
            }
        }
        .listStyle(.inset)
    }
}

private struct ThreadSummaryRow: View {
    @EnvironmentObject private var state: MailAppState
    let group: ThreadedEmailGroup
    let primary: EmailListItem

    var body: some View {
        HStack(spacing: 8) {
            Button {
                state.toggleThreadCollapse(group.id)
            } label: {
                Image(systemName: state.isThreadCollapsed(group.id) ? "chevron.right" : "chevron.down")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .buttonStyle(.plain)

            EmailRow(email: primary)

            if group.count > 1 {
                Text("\(group.count)")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Capsule().fill(Color.secondary.opacity(0.15)))
            }

            let unread = state.unreadCount(in: group)
            if unread > 0 {
                Text("\(unread)")
                    .font(.caption2)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Capsule().fill(Color.blue))
            }
        }
    }
}

private struct ThreadList: View {
    @EnvironmentObject private var state: MailAppState

    var body: some View {
        List(selection: Binding(
            get: { state.selectedThreadID },
            set: { next in
                guard let next else {
                    state.selectThread(nil)
                    return
                }
                state.selectThread(state.filteredThreads.first(where: { $0.id == next }))
            }
        )) {
            ForEach(state.filteredThreads) { thread in
                ThreadRow(thread: thread)
                    .tag(thread.id)
            }
        }
        .listStyle(.inset)
    }
}

private struct EmailRow: View {
    @EnvironmentObject private var state: MailAppState
    let email: EmailListItem

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            if state.preferences.showSenderAvatars {
                Circle()
                    .fill(Color.accentColor.opacity(0.16))
                    .frame(width: 26, height: 26)
                    .overlay(
                        Text(String((email.senderName ?? email.senderEmail ?? "?").prefix(1)).uppercased())
                            .font(.caption2)
                            .fontWeight(.bold)
                    )
            } else {
                Circle()
                    .fill(state.isUnread(email.id) ? Color.blue : Color.clear)
                    .frame(width: 8, height: 8)
                    .padding(.top, 7)
            }

            VStack(alignment: .leading, spacing: 4) {
                HStack(alignment: .firstTextBaseline) {
                    Text(email.senderName ?? email.senderEmail ?? "Unknown Sender")
                        .font(state.isUnread(email.id) ? .headline : .body)
                        .lineLimit(1)
                    Spacer()
                    Text(state.displayDate(for: email.dateSent))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                HStack(spacing: 6) {
                    Text(email.subject ?? "(No Subject)")
                        .font(state.isUnread(email.id) ? .headline : .subheadline)
                        .lineLimit(1)
                    if email.hasAttachments {
                        Image(systemName: "paperclip")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    if state.isJunk(email) {
                        Text("Junk")
                            .font(.caption2)
                            .foregroundStyle(.orange)
                    }
                }

                if state.preferences.showMessagePreview {
                    Text(email.snippet ?? (email.mboxSource ?? ""))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(state.preferences.compactListDensity ? 1 : 2)
                }
            }
        }
        .padding(.vertical, state.preferences.compactListDensity ? 2 : 4)
    }
}

private struct ThreadRow: View {
    @EnvironmentObject private var state: MailAppState
    let thread: ThreadListItem

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(thread.originalSubject ?? thread.subjectNormalized ?? "(Untitled Thread)")
                .lineLimit(1)
                .font(.headline)
            HStack {
                Text("\(thread.messageCount) messages")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text("•")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
                Text("\(thread.participantCount) participants")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                Text(state.displayDate(for: thread.lastDate))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 4)
    }
}

private struct DetailPaneView: View {
    @EnvironmentObject private var state: MailAppState

    var body: some View {
        Group {
            if state.selectedSection == .emails {
                EmailDetailView(detail: state.selectedEmailDetail)
            } else {
                ThreadDetailView(detail: state.selectedThreadDetail)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(nsColor: .textBackgroundColor))
    }
}
