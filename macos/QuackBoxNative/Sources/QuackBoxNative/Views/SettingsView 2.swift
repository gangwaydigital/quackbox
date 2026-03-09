import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var state: MailAppState

    @State private var serverURLInput: String = ""
    @State private var webURLInput: String = ""

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("QuackBox Native Settings")
                    .font(.title3)
                    .fontWeight(.semibold)

                GroupBox("Backend") {
                    VStack(alignment: .leading, spacing: 10) {
                        TextField("http://127.0.0.1:8000", text: $serverURLInput)
                            .textFieldStyle(.roundedBorder)
                        HStack {
                            Button("Apply") {
                                Task { await state.setServerURL(serverURLInput) }
                            }
                            Spacer()
                            if let stats = state.stats {
                                Text("\(stats.totalEmails) emails indexed")
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                }

                GroupBox("Web Modules") {
                    VStack(alignment: .leading, spacing: 10) {
                        TextField("http://127.0.0.1:5173", text: $webURLInput)
                            .textFieldStyle(.roundedBorder)
                        HStack {
                            Button("Apply Web URL") {
                                state.setWebBaseURL(webURLInput)
                            }
                            Spacer()
                            Text("Used for Dashboard/Search/Calendar/Timeline/Contacts/etc.")
                                .foregroundStyle(.secondary)
                                .font(.caption)
                        }
                    }
                }

                GroupBox("Add Account") {
                    VStack(alignment: .leading, spacing: 8) {
                        TextField("Display name", text: $state.accountForm.displayName)
                        TextField("Email address", text: $state.accountForm.emailAddress)
                        HStack {
                            TextField("IMAP host", text: $state.accountForm.imapHost)
                            TextField("IMAP user", text: $state.accountForm.imapUsername)
                        }
                        SecureField("IMAP password / app password", text: Binding(
                            get: { state.accountForm.imapPassword ?? "" },
                            set: { state.accountForm.imapPassword = $0 }
                        ))

                        HStack {
                            TextField("SMTP host", text: $state.accountForm.smtpHost)
                            TextField("SMTP user", text: $state.accountForm.smtpUsername)
                        }
                        SecureField("SMTP password / app password", text: Binding(
                            get: { state.accountForm.smtpPassword ?? "" },
                            set: { state.accountForm.smtpPassword = $0 }
                        ))

                        HStack {
                            Picker("IMAP Security", selection: $state.accountForm.imapSecurity) {
                                Text("SSL").tag("ssl")
                                Text("STARTTLS").tag("starttls")
                                Text("Plain").tag("plain")
                            }
                            TextField("IMAP Port", value: $state.accountForm.imapPort, format: .number)
                                .frame(width: 90)
                        }
                        HStack {
                            Picker("SMTP Security", selection: $state.accountForm.smtpSecurity) {
                                Text("SSL").tag("ssl")
                                Text("STARTTLS").tag("starttls")
                                Text("Plain").tag("plain")
                            }
                            TextField("SMTP Port", value: $state.accountForm.smtpPort, format: .number)
                                .frame(width: 90)
                        }

                        Text("OAuth (optional)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        TextField("Provider (e.g. google)", text: Binding(
                            get: { state.accountForm.oauthProvider ?? "" },
                            set: { state.accountForm.oauthProvider = $0.isEmpty ? nil : $0 }
                        ))
                        TextField("Token URL", text: Binding(
                            get: { state.accountForm.oauthTokenURL ?? "" },
                            set: { state.accountForm.oauthTokenURL = $0.isEmpty ? nil : $0 }
                        ))
                        TextField("Client ID", text: Binding(
                            get: { state.accountForm.oauthClientID ?? "" },
                            set: { state.accountForm.oauthClientID = $0.isEmpty ? nil : $0 }
                        ))
                        SecureField("Client Secret", text: Binding(
                            get: { state.accountForm.oauthClientSecret ?? "" },
                            set: { state.accountForm.oauthClientSecret = $0.isEmpty ? nil : $0 }
                        ))
                        SecureField("Refresh Token", text: Binding(
                            get: { state.accountForm.oauthRefreshToken ?? "" },
                            set: { state.accountForm.oauthRefreshToken = $0.isEmpty ? nil : $0 }
                        ))

                        Button("Save Account") {
                            Task { await state.addAccount() }
                        }
                    }
                }

                GroupBox("Accounts") {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(state.accounts) { account in
                            HStack {
                                VStack(alignment: .leading) {
                                    Text(account.displayName)
                                    Text(account.emailAddress)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                                Spacer()
                                Text(account.enabled ? "Enabled" : "Disabled")
                                    .foregroundStyle(account.enabled ? .green : .secondary)
                            }
                        }
                        if state.accounts.isEmpty {
                            Text("No accounts configured.")
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
        .onAppear {
            serverURLInput = state.serverURLString
            webURLInput = state.webBaseURLString
        }
    }
}
