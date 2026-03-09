import SwiftUI

struct ComposeView: View {
    @EnvironmentObject private var state: MailAppState
    @Environment(\.dismiss) private var dismiss

    @State private var accountID: Int?
    @State private var to: String = ""
    @State private var cc: String = ""
    @State private var bcc: String = ""
    @State private var subject: String = ""
    @State private var attributedBody = NSAttributedString(string: "")
    @State private var plainBody: String = ""
    @StateObject private var richTextContext = RichTextContext()

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Compose")
                .font(.title2)
                .fontWeight(.semibold)

            Picker("From", selection: Binding(
                get: { accountID ?? state.selectedAccountID },
                set: { accountID = $0 }
            )) {
                ForEach(state.accounts) { account in
                    Text("\(account.displayName) <\(account.emailAddress)>")
                        .tag(Optional(account.id))
                }
            }

            TextField("To", text: $to)
            TextField("Cc", text: $cc)
            TextField("Bcc", text: $bcc)
            TextField("Subject", text: $subject)

            if state.preferences.composeInRichText {
                HStack(spacing: 8) {
                    Button("B") { richTextContext.toggleBold() }
                        .fontWeight(.bold)
                    Button("I") { richTextContext.toggleItalic() }
                        .italic()
                    Button("U") { richTextContext.toggleUnderline() }
                        .underline()
                    Button("S") { richTextContext.toggleStrikethrough() }
                        .strikethrough()
                    Divider()
                        .frame(height: 16)
                    Button("• List") { richTextContext.insertBulletList() }
                    Button("1. List") { richTextContext.insertNumberedList() }
                    Spacer()
                }
                .buttonStyle(.bordered)

                RichTextEditor(
                    attributedText: $attributedBody,
                    context: richTextContext,
                    options: RichEditorOptions(
                        fontName: state.preferences.composeFontName,
                        fontSize: state.preferences.composeFontSize,
                        textColorHex: state.preferences.composeTextColorHex,
                        spellCheck: state.preferences.spellCheckWhileTyping,
                        autoDetectLinks: state.preferences.autoDetectLinks,
                        smartQuotes: state.preferences.smartQuotes,
                        smartDashes: state.preferences.smartDashes
                    )
                )
                .frame(minHeight: 320)
            } else {
                TextEditor(text: $plainBody)
                    .font(.system(size: state.preferences.composeFontSize))
                    .frame(minHeight: 320)
            }

            HStack {
                Spacer()
                Button("Cancel") {
                    dismiss()
                }
                Button("Send") {
                    Task {
                        await state.sendDraft(
                            ComposeDraft(
                                accountID: accountID ?? state.selectedAccountID,
                                to: to,
                                cc: cc,
                                bcc: bcc,
                                subject: subject,
                                body: state.preferences.composeInRichText ? attributedBody.string : plainBody,
                                bodyHTML: state.preferences.composeInRichText ? attributedBody.toHTMLString() : nil
                            )
                        )
                        if state.composeDraft == nil {
                            dismiss()
                        }
                    }
                }
                .keyboardShortcut(.defaultAction)
                .disabled((accountID ?? state.selectedAccountID) == nil || to.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
        .padding(20)
        .onAppear {
            accountID = state.composeDraft?.accountID ?? state.selectedAccountID
            to = state.composeDraft?.to ?? ""
            cc = state.composeDraft?.cc ?? ""
            bcc = state.composeDraft?.bcc ?? ""
            subject = state.composeDraft?.subject ?? ""
            if let html = state.composeDraft?.bodyHTML, !html.isEmpty {
                attributedBody = NSAttributedString.fromHTMLString(html)
            } else {
                attributedBody = NSAttributedString(string: state.composeDraft?.body ?? "")
            }
            plainBody = state.composeDraft?.body ?? attributedBody.string
        }
    }
}
