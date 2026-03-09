import AppKit
import SwiftUI

struct MailCommands: Commands {
    @ObservedObject var state: MailAppState

    var body: some Commands {
        CommandGroup(replacing: .appInfo) {
            Button("About QuackBoxNative") {
                let aboutText = """
                Quackbox is project concieved by Duck.

                Duck made this a reality and the world is a better place for it.
                """
                NSApp.orderFrontStandardAboutPanel(options: [
                    .credits: NSAttributedString(string: aboutText)
                ])
                NSApp.activate(ignoringOtherApps: true)
            }
        }

        CommandMenu("Message") {
            Button("Next") { state.selectNextMessage() }
                .keyboardShortcut("j", modifiers: [])
            Button("Previous") { state.selectPreviousMessage() }
                .keyboardShortcut("k", modifiers: [])

            Divider()

            Button("Next Conversation") { state.selectNextConversation() }
                .keyboardShortcut("]", modifiers: [.command])
            Button("Previous Conversation") { state.selectPreviousConversation() }
                .keyboardShortcut("[", modifiers: [.command])

            Divider()

            Button("Archive") { state.archiveCurrentEmail() }
                .keyboardShortcut("e", modifiers: [])
        }

        CommandMenu("View") {
            Button(state.showThreadedList ? "Disable Threaded List" : "Enable Threaded List") {
                state.toggleThreadedList()
            }
            .keyboardShortcut("t", modifiers: [.command])

            Divider()

            Button("Widen Message List") { state.widenMessageList() }
                .keyboardShortcut("]", modifiers: [.command, .option])
            Button("Narrow Message List") { state.narrowMessageList() }
                .keyboardShortcut("[", modifiers: [.command, .option])

            Button("Widen Sidebar") { state.widenSidebar() }
                .keyboardShortcut("=", modifiers: [.command, .option])
            Button("Narrow Sidebar") { state.narrowSidebar() }
                .keyboardShortcut("-", modifiers: [.command, .option])
        }
    }
}
