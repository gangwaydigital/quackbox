import SwiftUI

struct ThreadDetailView: View {
    let detail: ThreadDetail?

    var body: some View {
        Group {
            if let detail {
                ScrollView {
                    VStack(alignment: .leading, spacing: 14) {
                        Text("Thread #\(detail.id)")
                            .font(.title2)
                            .fontWeight(.semibold)

                        Text("\(detail.messageCount) messages • \(detail.participantCount) participants")
                            .foregroundStyle(.secondary)

                        Divider()

                        ForEach(detail.emails) { email in
                            VStack(alignment: .leading, spacing: 8) {
                                Text(email.subject ?? "(No Subject)")
                                    .font(.headline)
                                Text("\(email.senderName ?? email.senderEmail ?? "Unknown") • \(email.dateSent ?? "")")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                Text(email.bodyText ?? "")
                                    .lineLimit(8)
                                    .textSelection(.enabled)

                                if email.hasAttachments, !email.attachmentNames.isEmpty {
                                    Text("Attachments: \(email.attachmentNames.joined(separator: ", "))")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                            .padding(12)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Color(nsColor: .windowBackgroundColor))
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                            .overlay(
                                RoundedRectangle(cornerRadius: 10)
                                    .stroke(Color.secondary.opacity(0.15), lineWidth: 1)
                            )
                        }
                    }
                    .padding(22)
                }
            } else {
                ContentUnavailableView("Select a thread", systemImage: "text.bubble")
            }
        }
    }
}
