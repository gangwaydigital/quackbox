import SwiftUI

struct EmailDetailView: View {
    @EnvironmentObject private var state: MailAppState
    let detail: EmailDetail?

    var body: some View {
        Group {
            if let detail {
                ScrollView {
                    VStack(alignment: .leading, spacing: 14) {
                        HStack(alignment: .top) {
                            Text(detail.subject ?? "(No Subject)")
                                .font(.title2)
                                .fontWeight(.semibold)
                            Spacer()
                            HStack(spacing: 8) {
                                Button("Reply") { state.replyToCurrentEmail() }
                                Button("Forward") { state.forwardCurrentEmail() }
                                Button("Archive") { state.archiveCurrentEmail() }
                            }
                        }

                        VStack(alignment: .leading, spacing: 6) {
                            Text("From: \(detail.senderName ?? detail.senderEmail ?? "Unknown Sender")")
                            Text("Date: \(detail.dateSent ?? "")")
                            if !detail.recipients.isEmpty {
                                Text("To: \(detail.recipients.map { $0.email }.joined(separator: ", "))")
                            }
                            if let source = detail.mboxSource {
                                Text("Mailbox: \(source)")
                            }
                        }
                        .font(.callout)
                        .foregroundStyle(.secondary)

                        Divider()

                        if !state.preferences.preferPlainTextReading,
                           let html = detail.bodyHTML,
                           !html.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                            Text(AttributedString(NSAttributedString.fromHTMLString(html)))
                                .font(.system(size: state.preferences.readingFontSize))
                                .textSelection(.enabled)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        } else {
                            Text(detail.bodyText?.isEmpty == false ? detail.bodyText! : "No plain text body available.")
                                .font(.system(size: state.preferences.readingFontSize))
                                .textSelection(.enabled)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }

                        if detail.hasAttachments, !detail.attachmentNames.isEmpty {
                            Divider()
                            Text("Attachments")
                                .font(.headline)
                            ForEach(detail.attachmentNames, id: \.self) { name in
                                HStack {
                                    Label(name, systemImage: "paperclip")
                                        .font(.callout)
                                    Spacer()
                                    Button("Save As…") {
                                        state.saveAttachmentFromSelectedEmail(filename: name)
                                    }
                                }
                            }
                        }
                    }
                    .padding(22)
                }
            } else {
                ContentUnavailableView("Select an email", systemImage: "envelope.open")
            }
        }
    }
}
