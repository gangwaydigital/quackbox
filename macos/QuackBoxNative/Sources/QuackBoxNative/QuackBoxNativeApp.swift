import SwiftUI

@main
struct QuackBoxNativeApp: App {
    @StateObject private var state = MailAppState()

    var body: some Scene {
        WindowGroup {
            RootSplitView()
                .environmentObject(state)
                .task {
                    await state.loadInitialData()
                }
        }
        .defaultSize(width: 1320, height: 860)
        .commands {
            MailCommands(state: state)
        }

        Settings {
            SettingsView()
                .environmentObject(state)
                .frame(width: 1240, height: 780)
        }
    }
}
