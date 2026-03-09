import AppKit
import SwiftUI

private enum PreferencesSection: String, CaseIterable, Identifiable {
    case general = "General"
    case accounts = "Accounts"
    case junk = "Junk Mail"
    case fonts = "Fonts & Colors"
    case viewing = "Viewing"
    case composing = "Composing"
    case signatures = "Signatures"
    case rules = "Rules"
    case privacy = "Privacy"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .general: return "gearshape"
        case .accounts: return "at"
        case .junk: return "trash"
        case .fonts: return "textformat"
        case .viewing: return "eyeglasses"
        case .composing: return "square.and.pencil"
        case .signatures: return "signature"
        case .rules: return "line.3.horizontal.decrease.circle"
        case .privacy: return "hand.raised"
        }
    }
}

private enum AccountDetailTab: String, CaseIterable, Identifiable {
    case info = "Account Information"
    case mailbox = "Mailbox Behaviors"
    case server = "Server Settings"

    var id: String { rawValue }
}

struct SettingsView: View {
    @EnvironmentObject private var state: MailAppState

    @State private var section: PreferencesSection = .accounts
    @State private var accountTab: AccountDetailTab = .info
    @State private var selectedAccountID: Int?

    @State private var serverURLInput: String = ""
    @State private var webURLInput: String = ""
    @State private var accountDraft = SettingsView.emptyAccountForm()
    @State private var accountFolderOverrideRaw: String = ""

    @State private var prefsDraft = AppPreferences()

    @State private var selectedSignatureID: UUID?
    @State private var signatureName: String = ""
    @State private var signatureBody: String = ""
    @State private var signatureIsHTML = false

    @State private var selectedRuleID: UUID?
    @State private var ruleName: String = ""
    @State private var ruleField: RuleField = .subject
    @State private var ruleContains: String = ""
    @State private var ruleAction: RuleAction = .markJunk
    @State private var ruleEnabled = true
    @State private var ruleContinue = false

    private let fontChoices = ["Helvetica Neue", "San Francisco", "Arial", "Georgia", "Menlo", "Times New Roman"]

    var body: some View {
        VStack(spacing: 0) {
            Text(section.rawValue)
                .font(.title)
                .fontWeight(.semibold)
                .padding(.top, 10)

            HStack(spacing: 14) {
                ForEach(PreferencesSection.allCases) { item in
                    Button {
                        section = item
                    } label: {
                        VStack(spacing: 5) {
                            Image(systemName: item.icon)
                                .font(.system(size: 28, weight: .regular))
                            Text(item.rawValue)
                                .font(.system(size: 12))
                        }
                        .frame(width: 105, height: 74)
                        .background(
                            RoundedRectangle(cornerRadius: 12)
                                .fill(section == item ? Color.accentColor.opacity(0.16) : Color.clear)
                        )
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(section == item ? Color.accentColor : .primary)
                }
            }
            .padding(.horizontal, 18)
            .padding(.vertical, 8)

            Divider()

            Group {
                switch section {
                case .accounts:
                    accountsPane
                case .general:
                    generalPane
                case .composing:
                    composingPane
                case .signatures:
                    signaturesPane
                case .fonts:
                    fontsPane
                case .viewing:
                    viewingPane
                case .junk:
                    junkPane
                case .rules:
                    rulesPane
                case .privacy:
                    privacyPane
                }
            }
            .padding(16)
        }
        .onAppear {
            serverURLInput = state.serverURLString
            webURLInput = state.webBaseURLString
            prefsDraft = state.preferences
            if selectedAccountID == nil {
                selectedAccountID = state.selectedAccountID ?? state.accounts.first?.id
            }
            accountFolderOverrideRaw = state.autoSyncFoldersText(for: selectedAccountID)
            selectedSignatureID = prefsDraft.defaultSignatureID ?? prefsDraft.signatures.first?.id
            loadDraftFromSelection()
            loadSignatureEditor()
            loadRuleEditor()
        }
        .onChange(of: selectedAccountID) { _, _ in
            loadDraftFromSelection()
            accountFolderOverrideRaw = state.autoSyncFoldersText(for: selectedAccountID)
        }
        .onChange(of: selectedSignatureID) { _, _ in
            loadSignatureEditor()
        }
        .onChange(of: selectedRuleID) { _, _ in
            loadRuleEditor()
        }
    }

    private var accountsPane: some View {
        HStack(spacing: 14) {
            VStack(spacing: 10) {
                List(selection: Binding(
                    get: { selectedAccountID },
                    set: { selectedAccountID = $0 }
                )) {
                    ForEach(state.accounts) { account in
                        HStack(spacing: 10) {
                            Image(systemName: "at.circle.fill")
                                .font(.title2)
                                .foregroundStyle(.blue)
                            VStack(alignment: .leading, spacing: 1) {
                                Text(account.displayName)
                                Text("IMAP")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .padding(.vertical, 4)
                        .tag(Optional(account.id))
                    }
                }
                .listStyle(.inset)

                HStack(spacing: 8) {
                    Button {
                        selectedAccountID = nil
                        accountDraft = Self.emptyAccountForm()
                    } label: {
                        Image(systemName: "plus")
                    }

                    Button {
                        guard let selectedAccountID else { return }
                        Task {
                            await state.deleteAccount(accountID: selectedAccountID)
                            self.selectedAccountID = state.accounts.first?.id
                            loadDraftFromSelection()
                        }
                    } label: {
                        Image(systemName: "minus")
                    }
                    .disabled(selectedAccountID == nil)
                }
                .buttonStyle(.bordered)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(width: 290)

            VStack(alignment: .leading, spacing: 14) {
                Picker("Tab", selection: $accountTab) {
                    ForEach(AccountDetailTab.allCases) { tab in
                        Text(tab.rawValue).tag(tab)
                    }
                }
                .labelsHidden()
                .pickerStyle(.segmented)
                .frame(maxWidth: 560)

                switch accountTab {
                case .info:
                    accountInfoPane
                case .mailbox:
                    mailboxPane
                case .server:
                    serverPane
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .padding(16)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(Color(nsColor: .controlBackgroundColor))
            )
        }
    }

    private var accountInfoPane: some View {
        VStack(alignment: .leading, spacing: 14) {
            Toggle("Enable this account", isOn: $accountDraft.enabled)

            HStack(spacing: 12) {
                Text("Status:")
                    .frame(width: 110, alignment: .trailing)
                Text(accountDraft.enabled ? "Online" : "Disabled")
                Circle()
                    .fill(accountDraft.enabled ? Color.green : .secondary)
                    .frame(width: 12, height: 12)
            }

            HStack(spacing: 12) {
                Text("Description:")
                    .frame(width: 110, alignment: .trailing)
                TextField("Description", text: $accountDraft.displayName)
            }

            HStack(spacing: 12) {
                Text("Email Address:")
                    .frame(width: 110, alignment: .trailing)
                TextField("user@example.com", text: $accountDraft.emailAddress)
            }

            actionRow
        }
    }

    private var mailboxPane: some View {
        VStack(alignment: .leading, spacing: 12) {
            Toggle("Use threaded view by default", isOn: prefBinding(\.useThreadedViewByDefault))
            Toggle("Show preview snippets", isOn: prefBinding(\.showMessagePreview))
            Toggle("Compact list density", isOn: prefBinding(\.compactListDensity))
            Toggle("Hide junk from Inbox", isOn: prefBinding(\.hideJunkFromInbox))

            Divider()

            Toggle("Automatically sync mail", isOn: prefBinding(\.autoSyncEnabled))
            Toggle("Sync automatically at launch", isOn: prefBinding(\.autoSyncOnLaunch))
            HStack {
                Text("Sync every")
                Stepper(value: prefBinding(\.autoSyncIntervalMinutes), in: 1 ... 60, step: 1) {
                    Text("\(Int(prefsDraft.autoSyncIntervalMinutes)) minutes")
                }
            }
            HStack {
                Text("Fetch limit per folder")
                Stepper(value: prefBinding(\.autoSyncFetchLimit), in: 50 ... 1000, step: 50) {
                    Text("\(prefsDraft.autoSyncFetchLimit)")
                }
            }
            TextField("Default sync folders (comma separated)", text: Binding(
                get: { prefsDraft.autoSyncDefaultFoldersRaw },
                set: {
                    prefsDraft.autoSyncDefaultFoldersRaw = $0
                    applyPrefs()
                }
            ))
            .textFieldStyle(.roundedBorder)

            TextField("Selected account folders (override)", text: $accountFolderOverrideRaw)
                .textFieldStyle(.roundedBorder)

            HStack {
                Button("Apply Account Override") {
                    state.setAutoSyncFoldersText(accountFolderOverrideRaw, for: selectedAccountID)
                    prefsDraft = state.preferences
                }
                .disabled(selectedAccountID == nil)

                Button("Clear Override") {
                    guard selectedAccountID != nil else { return }
                    state.setAutoSyncFoldersText("", for: selectedAccountID)
                    prefsDraft = state.preferences
                    accountFolderOverrideRaw = state.autoSyncFoldersText(for: selectedAccountID)
                }
                .disabled(selectedAccountID == nil)

                Spacer()
                Button("Sync Now") {
                    Task { await state.syncSelectedAccount() }
                }
                .disabled(selectedAccountID == nil)
            }

            if let last = state.lastAutoSyncAt {
                Text("Last auto sync: \(last.formatted(date: .abbreviated, time: .shortened))")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Text(state.lastAutoSyncSummary)
                .font(.caption)
                .foregroundStyle(.secondary)

            Divider()

            HStack {
                Text("Outbox Queue")
                    .font(.headline)
                Spacer()
                Text("\(state.outboxItems.filter { $0.status != "sent" }.count) pending")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            HStack {
                Button("Flush Outbox") {
                    Task { await state.flushOutboxQueue() }
                }
                .disabled(state.outboxItems.isEmpty)
                Spacer()
            }

            if !state.outboxItems.isEmpty {
                List(state.outboxItems.prefix(8)) { item in
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(item.subject ?? "(No Subject)")
                                .lineLimit(1)
                            Text("Status: \(item.status) • Attempts: \(item.attemptCount)")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        Button("Retry") {
                            Task { await state.retryOutboxItem(item.id) }
                        }
                        .disabled(item.status == "sent")
                        Button("Delete") {
                            Task { await state.deleteOutboxItem(item.id) }
                        }
                    }
                }
                .frame(minHeight: 120, maxHeight: 180)
            }
        }
    }

    private var serverPane: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Incoming Mail Server (IMAP)")
                .font(.headline)
            HStack {
                TextField("imap.example.com", text: $accountDraft.imapHost)
                TextField("Port", value: $accountDraft.imapPort, format: .number)
                    .frame(width: 90)
            }
            HStack {
                Picker("Security", selection: $accountDraft.imapSecurity) {
                    Text("SSL").tag("ssl")
                    Text("STARTTLS").tag("starttls")
                    Text("Plain").tag("plain")
                }
                TextField("Username", text: $accountDraft.imapUsername)
            }
            SecureField("Password (leave blank to keep unchanged)", text: Binding(
                get: { accountDraft.imapPassword ?? "" },
                set: { accountDraft.imapPassword = $0.isEmpty ? nil : $0 }
            ))

            Divider()

            Text("Outgoing Mail Server (SMTP)")
                .font(.headline)
            HStack {
                TextField("smtp.example.com", text: $accountDraft.smtpHost)
                TextField("Port", value: $accountDraft.smtpPort, format: .number)
                    .frame(width: 90)
            }
            HStack {
                Picker("Security", selection: $accountDraft.smtpSecurity) {
                    Text("SSL").tag("ssl")
                    Text("STARTTLS").tag("starttls")
                    Text("Plain").tag("plain")
                }
                TextField("Username", text: $accountDraft.smtpUsername)
            }
            SecureField("Password (leave blank to keep unchanged)", text: Binding(
                get: { accountDraft.smtpPassword ?? "" },
                set: { accountDraft.smtpPassword = $0.isEmpty ? nil : $0 }
            ))

            actionRow
        }
    }

    private var actionRow: some View {
        HStack {
            Spacer()
            Button("Cancel") {
                loadDraftFromSelection()
            }
            Button(selectedAccountID == nil ? "Add Account" : "Save Changes") {
                Task {
                    if let accountID = selectedAccountID {
                        await state.updateAccount(accountID: accountID, form: accountDraft)
                    } else {
                        state.accountForm = accountDraft
                        await state.addAccount()
                        selectedAccountID = state.selectedAccountID ?? state.accounts.first?.id
                    }
                    loadDraftFromSelection()
                }
            }
            .keyboardShortcut(.defaultAction)
            .disabled(accountDraft.displayName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || accountDraft.emailAddress.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        }
    }

    private var generalPane: some View {
        VStack(alignment: .leading, spacing: 16) {
            GroupBox("About") {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Quackbox is project concieved by Duck.")
                    Text("Duck made this a reality and the world is a better place for it.")
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }

            GroupBox("Backend") {
                VStack(alignment: .leading, spacing: 10) {
                    TextField("http://127.0.0.1:8000", text: $serverURLInput)
                        .textFieldStyle(.roundedBorder)
                    HStack {
                        Button("Apply Backend URL") {
                            Task { await state.setServerURL(serverURLInput) }
                        }
                        Spacer()
                        if let stats = state.stats {
                            Text("\(stats.totalEmails) emails indexed")
                                .foregroundStyle(.secondary)
                                .font(.caption)
                        }
                    }
                }
            }

            GroupBox("Web Modules") {
                VStack(alignment: .leading, spacing: 10) {
                    TextField("http://127.0.0.1:8000", text: $webURLInput)
                        .textFieldStyle(.roundedBorder)
                    HStack {
                        Button("Apply Web URL") {
                            state.setWebBaseURL(webURLInput)
                        }
                        Spacer()
                    }
                }
            }
            Spacer()
        }
    }

    private var composingPane: some View {
        VStack(alignment: .leading, spacing: 12) {
            Toggle("Compose messages in rich text", isOn: prefBinding(\.composeInRichText))
            Toggle("Check spelling while typing", isOn: prefBinding(\.spellCheckWhileTyping))
            Toggle("Automatically detect links", isOn: prefBinding(\.autoDetectLinks))
            Toggle("Use smart quotes", isOn: prefBinding(\.smartQuotes))
            Toggle("Use smart dashes", isOn: prefBinding(\.smartDashes))
            Toggle("Append signature to new message", isOn: prefBinding(\.includeSignatureOnNew))
            Toggle("Append signature to replies/forwards", isOn: prefBinding(\.includeSignatureOnReply))
            Spacer()
        }
    }

    private var junkPane: some View {
        VStack(alignment: .leading, spacing: 12) {
            Toggle("Enable junk filtering", isOn: prefBinding(\.junkFilterEnabled))
            Toggle("Hide junk messages from Inbox", isOn: prefBinding(\.hideJunkFromInbox))
            TextField("Junk keywords (comma separated)", text: prefBinding(\.junkKeywordsRaw))
                .textFieldStyle(.roundedBorder)
            TextField("Blocked senders/domains (comma separated)", text: prefBinding(\.blockedSendersRaw))
                .textFieldStyle(.roundedBorder)
            Text("Rules and junk filters apply when mail refreshes.")
                .font(.caption)
                .foregroundStyle(.secondary)
            Spacer()
        }
    }

    private var fontsPane: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Compose Font")
                Picker("Font", selection: prefBinding(\.composeFontName)) {
                    ForEach(fontChoices, id: \.self) { name in
                        Text(name).tag(name)
                    }
                }
                .frame(width: 220)
            }
            HStack {
                Text("Compose Size")
                Stepper(value: prefBinding(\.composeFontSize), in: 11 ... 28, step: 1) {
                    Text("\(Int(prefsDraft.composeFontSize)) pt")
                }
            }
            HStack {
                Text("Text Color")
                TextField("#RRGGBB", text: prefBinding(\.composeTextColorHex))
                    .frame(width: 120)
            }
            Divider()
            HStack {
                Text("Reading Size")
                Stepper(value: prefBinding(\.readingFontSize), in: 11 ... 28, step: 1) {
                    Text("\(Int(prefsDraft.readingFontSize)) pt")
                }
            }
            Spacer()
        }
    }

    private var viewingPane: some View {
        VStack(alignment: .leading, spacing: 12) {
            Toggle("Show sender avatars", isOn: prefBinding(\.showSenderAvatars))
            Toggle("Show message preview snippets", isOn: prefBinding(\.showMessagePreview))
            Toggle("Use compact message list density", isOn: prefBinding(\.compactListDensity))
            Toggle("Prefer plain text when reading", isOn: prefBinding(\.preferPlainTextReading))
            Toggle("Use threaded conversations by default", isOn: prefBinding(\.useThreadedViewByDefault))
            Spacer()
        }
    }

    private var signaturesPane: some View {
        HStack(spacing: 12) {
            VStack {
                List(selection: Binding(
                    get: { selectedSignatureID },
                    set: { selectedSignatureID = $0 }
                )) {
                    ForEach(prefsDraft.signatures) { signature in
                        Text(signature.name)
                            .tag(Optional(signature.id))
                    }
                }
                HStack {
                    Button {
                        let new = SignatureItem(name: "New Signature", body: "", isHTML: false)
                        prefsDraft.signatures.append(new)
                        prefsDraft.defaultSignatureID = prefsDraft.defaultSignatureID ?? new.id
                        selectedSignatureID = new.id
                        applyPrefs()
                    } label: { Image(systemName: "plus") }
                    Button {
                        guard let selectedSignatureID else { return }
                        prefsDraft.signatures.removeAll { $0.id == selectedSignatureID }
                        if prefsDraft.defaultSignatureID == selectedSignatureID {
                            prefsDraft.defaultSignatureID = prefsDraft.signatures.first?.id
                        }
                        self.selectedSignatureID = prefsDraft.signatures.first?.id
                        applyPrefs()
                    } label: { Image(systemName: "minus") }
                    .disabled(selectedSignatureID == nil)
                }
                .buttonStyle(.bordered)
            }
            .frame(width: 260)

            VStack(alignment: .leading, spacing: 10) {
                TextField("Signature Name", text: $signatureName)
                Toggle("HTML Signature", isOn: $signatureIsHTML)
                TextEditor(text: $signatureBody)
                    .frame(minHeight: 180)
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color.secondary.opacity(0.2)))
                Picker("Default Signature", selection: Binding(
                    get: { prefsDraft.defaultSignatureID ?? UUID() },
                    set: {
                        prefsDraft.defaultSignatureID = $0
                        applyPrefs()
                    }
                )) {
                    ForEach(prefsDraft.signatures) { signature in
                        Text(signature.name).tag(signature.id)
                    }
                }
                HStack {
                    Spacer()
                    Button("Save Signature") {
                        saveSignatureEditor()
                    }
                    .disabled(selectedSignatureID == nil)
                }
            }
        }
    }

    private var rulesPane: some View {
        HStack(spacing: 12) {
            VStack {
                Toggle("Enable Rules", isOn: prefBinding(\.rulesEnabled))
                List(selection: Binding(
                    get: { selectedRuleID },
                    set: { selectedRuleID = $0 }
                )) {
                    ForEach(prefsDraft.rules) { rule in
                        HStack {
                            Image(systemName: rule.enabled ? "checkmark.circle.fill" : "circle")
                                .foregroundStyle(rule.enabled ? .green : .secondary)
                            Text(rule.name)
                        }
                        .tag(Optional(rule.id))
                    }
                }
                HStack {
                    Button {
                        let new = MailRule(name: "New Rule", field: .subject, contains: "", action: .markJunk)
                        prefsDraft.rules.append(new)
                        selectedRuleID = new.id
                        applyPrefs()
                    } label: { Image(systemName: "plus") }
                    Button {
                        guard let selectedRuleID else { return }
                        prefsDraft.rules.removeAll { $0.id == selectedRuleID }
                        self.selectedRuleID = prefsDraft.rules.first?.id
                        applyPrefs()
                    } label: { Image(systemName: "minus") }
                    .disabled(selectedRuleID == nil)
                }
                .buttonStyle(.bordered)
            }
            .frame(width: 300)

            VStack(alignment: .leading, spacing: 10) {
                Toggle("Rule enabled", isOn: $ruleEnabled)
                TextField("Rule Name", text: $ruleName)
                Picker("When Field", selection: $ruleField) {
                    ForEach(RuleField.allCases) { field in
                        Text(field.rawValue.capitalized).tag(field)
                    }
                }
                TextField("Contains", text: $ruleContains)
                Picker("Then Action", selection: $ruleAction) {
                    ForEach(RuleAction.allCases) { action in
                        Text(actionLabel(action)).tag(action)
                    }
                }
                Toggle("Continue evaluating later rules", isOn: $ruleContinue)
                HStack {
                    Spacer()
                    Button("Save Rule") { saveRuleEditor() }
                        .disabled(selectedRuleID == nil)
                }
            }
        }
    }

    private var privacyPane: some View {
        VStack(alignment: .leading, spacing: 12) {
            Toggle("Allow desktop notifications", isOn: prefBinding(\.allowNotifications))
            Toggle("Load remote content in messages", isOn: prefBinding(\.loadRemoteContent))
            Toggle("Protect Mail Activity", isOn: prefBinding(\.protectMailActivity))
            Text("When remote content is disabled, the app prefers local/plain content rendering.")
                .font(.caption)
                .foregroundStyle(.secondary)
            Spacer()
        }
    }

    private func prefBinding<Value>(_ keyPath: WritableKeyPath<AppPreferences, Value>) -> Binding<Value> {
        Binding(
            get: { prefsDraft[keyPath: keyPath] },
            set: { newValue in
                prefsDraft[keyPath: keyPath] = newValue
                applyPrefs()
            }
        )
    }

    private func applyPrefs() {
        state.setPreferences(prefsDraft)
    }

    private func loadDraftFromSelection() {
        guard let selectedAccountID,
              let account = state.accounts.first(where: { $0.id == selectedAccountID })
        else {
            accountDraft = Self.emptyAccountForm()
            return
        }
        accountDraft = Self.form(from: account)
    }

    private func loadSignatureEditor() {
        guard let selectedSignatureID,
              let signature = prefsDraft.signatures.first(where: { $0.id == selectedSignatureID }) else {
            signatureName = ""
            signatureBody = ""
            signatureIsHTML = false
            return
        }
        signatureName = signature.name
        signatureBody = signature.body
        signatureIsHTML = signature.isHTML
    }

    private func saveSignatureEditor() {
        guard let selectedSignatureID,
              let idx = prefsDraft.signatures.firstIndex(where: { $0.id == selectedSignatureID }) else {
            return
        }
        prefsDraft.signatures[idx].name = signatureName
        prefsDraft.signatures[idx].body = signatureBody
        prefsDraft.signatures[idx].isHTML = signatureIsHTML
        applyPrefs()
    }

    private func loadRuleEditor() {
        guard let selectedRuleID,
              let rule = prefsDraft.rules.first(where: { $0.id == selectedRuleID }) else {
            ruleName = ""
            ruleField = .subject
            ruleContains = ""
            ruleAction = .markJunk
            ruleEnabled = true
            ruleContinue = false
            return
        }
        ruleName = rule.name
        ruleField = rule.field
        ruleContains = rule.contains
        ruleAction = rule.action
        ruleEnabled = rule.enabled
        ruleContinue = rule.continueEvaluating
    }

    private func saveRuleEditor() {
        guard let selectedRuleID,
              let idx = prefsDraft.rules.firstIndex(where: { $0.id == selectedRuleID }) else {
            return
        }
        prefsDraft.rules[idx].name = ruleName
        prefsDraft.rules[idx].field = ruleField
        prefsDraft.rules[idx].contains = ruleContains
        prefsDraft.rules[idx].action = ruleAction
        prefsDraft.rules[idx].enabled = ruleEnabled
        prefsDraft.rules[idx].continueEvaluating = ruleContinue
        applyPrefs()
    }

    private func actionLabel(_ action: RuleAction) -> String {
        switch action {
        case .archive: return "Archive"
        case .markRead: return "Mark as Read"
        case .markUnread: return "Mark as Unread"
        case .markJunk: return "Mark as Junk"
        }
    }

    private static func form(from account: MailAccount) -> CreateAccountRequest {
        CreateAccountRequest(
            displayName: account.displayName,
            emailAddress: account.emailAddress,
            imapHost: account.imap.host,
            imapPort: account.imap.port,
            imapSecurity: account.imap.security,
            imapUsername: account.imap.username,
            imapPassword: nil,
            smtpHost: account.smtp.host,
            smtpPort: account.smtp.port,
            smtpSecurity: account.smtp.security,
            smtpUsername: account.smtp.username,
            smtpPassword: nil,
            oauthProvider: account.oauthProvider,
            oauthClientID: nil,
            oauthClientSecret: nil,
            oauthRefreshToken: nil,
            oauthAccessToken: nil,
            oauthTokenURL: nil,
            oauthExpiresAt: nil,
            enabled: account.enabled
        )
    }

    private static func emptyAccountForm() -> CreateAccountRequest {
        CreateAccountRequest(
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
}
